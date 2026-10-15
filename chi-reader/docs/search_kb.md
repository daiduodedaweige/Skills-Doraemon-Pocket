# CHI 检索器说明

`tools/search_kb.py` 是这个仓库里的一个本地检索脚本，用来基于 `kb/sections/` 和 `kb/docs/` 下已经生成好的 CHI 结构化数据做查询。

它的目标不是只做“字符串 grep”，而是把：

- 原文 chunk
- 对象抽取 `objects.jsonl`
- 规则抽取 `rules.jsonl`
- 流程抽取 `flows.jsonl`
- 验证点 `verification.jsonl`
- 关系 `relations.jsonl`

一起利用起来，给出更像“协议知识检索”的结果。

## 1. 依赖的数据

脚本默认读取以下路径：

- `kb/sections/`
- `kb/docs/chi_docs.json`

其中：

- `kb/sections/` 是按 section 拆分后的结构化知识库
- `kb/docs/chi_docs.json` 是聚合后的文档级信息，主要用于补充 section 元信息

`kb/sections/` 目录下每个 section 一般包含：

- `meta.json`
- `chunks.jsonl`
- `objects.jsonl`
- `rules.jsonl`
- `flows.jsonl`
- `verification.jsonl`
- `relations.jsonl`
- `tables.jsonl`
- `figures.jsonl`

## 2. 检索思路

`tools/search_kb.py` 不是单一路径检索，而是几层叠加：

1. 对 `chunks.jsonl` 做轻量全文召回。
2. 对 `objects/rules/flows/verification` 做结构化匹配加权。
3. 如果命中对象名，再用 `relations.jsonl` 做一跳关系扩展。
4. 如果用户查的是某个精确事务名，但该章节在 `kb/sections/` 里是空壳 section，脚本会根据 `meta.json` 里的 `relatedSections` 和 `dependsOn` 自动路由到相关章节。

这样做的好处是：

- 普通问题可以靠 chunk 召回
- `must / permitted / forbidden` 这类规则问题更容易命中 `rules`
- `flow / steps / sequence` 这类问题更容易命中 `flows`
- CamelCase 事务名和字段名更容易命中 `objects`

## 3. 适合解决什么问题

比较适合：

- “`RetryAck` 的要求是什么”
- “`AllowRetry` 在什么情况下必须是 0”
- “`WriteUniqueFullCleanSh` 应该看哪几节”
- “某个事务流程怎么走”
- “某个 opcode/field/response 在哪里被定义或约束”

不太适合：

- 生成最终自然语言答案
- 推理跨很多章节的复杂结论
- 替代人工核对原文

它更适合作为后续 RAG 或问答系统的“检索层”。

## 4. 快速开始

在仓库根目录运行：

```bash
python tools/search_kb.py "RetryAck requirements"
```

限制到某个 section：

```bash
python tools/search_kb.py "RetryAck requirements" --section B2.10 --top-k 3
```

查询事务流程：

```bash
python tools/search_kb.py "WriteUniqueFullCleanSh flow" --top-k 5
```

输出 JSON：

```bash
python tools/search_kb.py "What must AllowRetry be?" --json
```

列出所有可检索 section：

```bash
python tools/search_kb.py --list-sections
```

## 5. 参数说明

`tools/search_kb.py` 支持以下常用参数：

- `query`
  要查询的文本
- `--top-k`
  返回结果条数，默认 `5`
- `--section`
  限定搜索范围，可重复传入
- `--json`
  输出机器可读 JSON
- `--list-sections`
  列出可检索章节并退出
- `--json-dir`
  指定结构化知识库目录，默认是 `<project>/kb/sections`
- `--docs-path`
  指定文档级索引，默认是 `<project>/kb/docs/chi_docs.json`

## 6. 输出结果说明

文本模式下，每条结果通常包含：

- section 标题
- chunk id
- subsection
- source 文件
- snippet
- 命中的对象
- 命中的规则
- 命中的流程
- 命中的验证点
- 命中原因

JSON 模式下，每条结果主要字段包括：

- `chunk_id`
- `section_dir`
- `section`
- `title`
- `subsection`
- `score`
- `text`
- `snippet`
- `topics`
- `keywords`
- `source_type`
- `source_file`
- `matched_objects`
- `matched_rules`
- `matched_flows`
- `matched_verification`
- `reasons`

## 7. 一个典型用法

如果你后面要接 LLM，推荐流程是：

1. 先调用：

```bash
python tools/search_kb.py "RetryAck requirements" --json
```

2. 取前几条结果中的：

- `snippet`
- `matched_rules`
- `matched_flows`
- `matched_objects`
- `source_file`

3. 再把这些结果交给模型生成最终答案。

这样比直接把整本 CHI 文档喂给模型更稳，也更容易做引用和追溯。

## 8. 已知限制

当前版本有几个现实限制：

- `kb/sections/` 里有一部分 section 是空壳元数据，没有正文 chunk
- `flows/rules/objects` 是从 markdown 规则抽取出来的，质量取决于原始抽取效果
- 目前是纯标准库实现，没有外部向量库，也没有 embedding 检索
- 结果分数是启发式加权，不代表严格概率

因此：

- 它适合做“候选证据召回”
- 不建议把它当成最终裁决器

## 9. 后续可扩展方向

后面如果继续演进，这几个方向最有价值：

- 给 `chunks` 增加 embedding 检索
- 把 `tables/figures` 也纳入排序
- 增加 Python API，而不只是一层 CLI
- 增加结果高亮
- 增加“按对象名精确召回”的专门模式
- 在输出里补 section 间跳转建议

## 10. 文件位置

- 检索脚本：[tools/search_kb.py](../tools/search_kb.py)
- 结构化知识库目录：[kb/sections](../kb/sections)
- 聚合文档索引：[kb/docs/chi_docs.json](../kb/docs/chi_docs.json)
