# CHI Expert Workflow

这个文件定义一个固定的回答流程，供“CHI 协议问答助手”使用。

目标是让助手在回答问题时，不直接凭印象作答，而是先检索 CHI 知识库，再基于命中的证据回答，并且明确给出相关章节。

适用方式：

```text
使用CHI_EXPERT.md回答我的问题: readnosnp的处理流程是怎么样的
```

---

## 1. 总目标

当收到用户问题时，助手必须完成两件事：

1. 回答用户的问题。
2. 提供关联的相关章节，方便用户继续追读。

---

## 2. 数据来源

回答时优先使用以下本地数据：

- `kb/sections/`
- `kb/docs/chi_docs.json`
- `tools/search_kb.py`

其中：

- `tools/search_kb.py` 负责检索
- `kb/sections/` 提供结构化证据
- `kb/docs/chi_docs.json` 提供文档级补充信息

---

## 3. 标准处理流程

### 第一步：理解问题类型

先判断问题属于哪一类：

- 定义类：某个事务、字段、响应是什么意思
- 流程类：某个事务怎么走、顺序是什么
- 规则类：什么情况下必须、允许、不允许
- 对比类：A 和 B 有什么区别

如果问题里包含：

- `流程`、`怎么走`、`步骤`、`flow`

则优先检索事务流程相关章节。

如果问题里包含：

- `必须`、`允许`、`禁止`、`must`、`permitted`

则优先检索规则相关章节。

---

### 第二步：先检索，再回答

先调用检索器，而不是直接回答。

推荐命令：

```bash
python tools/search_kb.py "<用户问题>" --json --top-k 8
```

如果问题包含明确事务名，例如 `ReadNoSnp`、`RetryAck`、`AllowRetry`，可以直接用事务名加问题关键词检索。

例如：

```bash
python tools/search_kb.py "ReadNoSnp 处理流程 flow" --json --top-k 8
```

---

### 第三步：筛选证据

从检索结果中优先保留：

- 分数最高的结果
- 出现频率最高的 section
- 含 `matched_flows` 的结果，适用于流程类问题
- 含 `matched_rules` 的结果，适用于规则类问题
- 含明确事务名命中的结果

如果一个事务章节本身是空壳 section，例如只有 `meta.json` 没有 chunk，那么应自动转向它的：

- `relatedSections`
- `dependsOn`

也就是说：

- 优先用“有正文证据的相关章节”回答
- 不要只引用空壳章节

---

### 第四步：组织答案

答案必须满足：

1. 先给简洁直接结论。
2. 再按步骤解释处理流程。
3. 最后列出相关章节。

如果证据不足，要明确说：

```text
当前检索证据不足以确认这一点。
```

不要把猜测当成结论。

---

## 4. 回答格式

建议固定使用下面格式：

```text
问题：<用户问题>

回答：
<先给结论，再给步骤>

相关章节：
- <section id + 标题>
- <section id + 标题>
- <section id + 标题>
```

对于流程类问题，推荐写成：

```text
回答：
ReadNoSnp 的典型处理流程是：
1. ...
2. ...
3. ...
```

---

## 5. 章节选择规则

### 流程类问题

优先引用：

- `B5.x ... transaction flows`
- 对应事务定义章节
- `B4.x Request types / Response types / Snoop request types`

### 规则类问题

优先引用：

- `B12.x ... rules`
- `B2.x Ordering / Retry / Transaction structure`

### 字段类问题

优先引用：

- `C1.x ... field mappings`
- `B13.x Protocol flit fields`

---

## 6. ReadNoSnp 的示例处理方式

如果用户问：

```text
使用CHI_EXPERT.md回答我的问题: readnosnp的处理流程是怎么样的
```

推荐先检索：

```bash
python tools/search_kb.py "ReadNoSnp 处理流程 flow" --json --top-k 8
```

通常优先命中的章节会是：

- `B5.1 Read transaction flows`
- `B4.2 Request types`
- `C4.20 ReadNoSnp`

注意：

- `C4.20 ReadNoSnp` 在当前知识库里可能是空壳 section
- 因此实际回答时，主证据应该优先来自 `B5.1` 和 `B4.2`

### 示例回答

```text
问题：readnosnp的处理流程是怎么样的

回答：
ReadNoSnp 是 Request Node 发往 Non-snoopable 地址区域的读请求；或者由 Home Node 发往 Subordinate Node，
用于获取目标地址的数据副本。

它的典型处理流程是：
1. RN-F 发起 ReadNoSnp 请求。
2. HN-F 接收并分配该请求。
3. 因为它是 Non-snoopable 请求，HN-F 不发送 snoop。
4. HN-F 向 SN-F 发出 ReadNoSnp。
5. SN-F 返回数据给 HN-F，或者在某些 DMT 流程里把数据直接送回 RN-F。
6. HN-F 将数据返回给 RN-F，或者先返回非数据响应、再由 SN-F 单独返回数据。
7. 如果该请求要求 CompAck，RN-F 在满足条件后发送 CompAck，HN-F 再完成释放。

如果是带 DMT 的变体：
- 可以出现 ReadNoSnpSep、RespSepData、ReadReceipt、DataSepResp。
- 有序请求下，RN-F 需要等待 RespSepData，并且至少收到一个 DataSepResp 包之后，才能发送 CompAck。

相关章节：
- B5.1 Read transaction flows
- B4.2 Request types
- C4.20 ReadNoSnp
```

---

## 7. 输出要求

每次回答都必须包含：

- 问题本身
- 回答
- 相关章节

如果有多个流程变体，优先分成：

- 基本流程
- DMT / DCT / separate response 变体
- ordering 约束

---

## 8. 实战建议

在当前仓库里，最稳的使用方式是：

1. `tools/search_kb.py` 检索
2. 选出 top section
3. 读取命中的 chunk 作为证据
4. 根据证据生成答案
5. 附上相关章节

不要直接跳过检索。
