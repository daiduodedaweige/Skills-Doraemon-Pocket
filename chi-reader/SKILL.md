---
name: chi-reader
description: 使用内置 AMBA CHI IHI0050H 原始 PDF、章节 PDF、结构化知识库和检索器回答协议定义、事务流程、字段与规则问题；也可按需查看 Mermaid 图或重建资料。仅适用于该版 CHI 协议资料。
---

# CHI Reader

此 skill 内置原始规范 `source/IHI0050H_amba_chi_architecture_spec.pdf`、章节 PDF、知识库、Mermaid 图和原项目脚本；无需访问原项目。以本 `SKILL.md` 所在目录作为 `SKILL_ROOT`（如果通过符号链接加载，先解析真实路径），在该目录下运行以下命令；或用 `SKILL_ROOT` 的绝对路径访问同名文件。不要重新实现检索器。

## 协议问答

1. 区分定义、流程、规则、对比或字段问题，保留用户给出的 opcode、字段名和版本限定。按 [CHI_EXPERT.md](CHI_EXPERT.md) 的问答约定，先检索再回答。
2. 在 `SKILL_ROOT` 运行 `python3 tools/search_kb.py "<用户问题>" --json --top-k 8`。对于具体事务，可同时以精确英文名加 `flow`、`rules`、字段名等重查。需要限定章节时用可重复的 `--section <章节号>`；查询目录用 `--list-sections`。完整参数及返回字段见 [docs/search_kb.md](docs/search_kb.md)。检索器只依赖 Python 标准库。
3. 从 `text`、`matched_flows`、`matched_rules`、`matched_objects` 和 `source_file` 核对证据；需要细节时读取 `kb/sections/<section_dir>/` 下对应 `chunks.jsonl`、`flows.jsonl`、`rules.jsonl`、`objects.jsonl`、`verification.jsonl`、`tables.jsonl` 或 `figures.jsonl`。`kb/docs/chi_docs.json` 是补充索引；`artifacts/chi_chunks.jsonl` 不是当前检索器的数据源。
4. 对仅有 `meta.json` 的空壳章节，跟随 `relatedSections` / `dependsOn` 查找有正文的章节。不要把空壳章节当作事实依据，也不要仅凭检索分数或自动抽取的规则/流程推断规范要求；有歧义时核对 `artifacts/split_pdfs/` 对应章节或 `source/IHI0050H_amba_chi_architecture_spec.pdf` 原文。
5. 先直接回答，再根据问题类型解释必要的条件、步骤或差异，最后列出有证据支持的相关章节（章节号和标题）。对流程变体分别说明适用前提，不将 DMT / DCT / separate response 当作所有事务的必经步骤。证据不足时明确说“当前检索证据不足以确认这一点”，并标明尚待核对的章节。

## 图与源文件

需要说明图示时，先查 `kb/sections/<section_dir>/figures.jsonl` 的 figure 编号，再找 `artifacts/figures_mermaid/<section 名称>__<figure 编号>.mmd` 和 `artifacts/split_pdfs/<section 名称>.pdf`。Mermaid 是自动近似重建，涉及箭头方向、消息顺序或复杂分支时以 PDF 为准；找不到图文件就查 PDF，不假定所有 figure 都已有 Mermaid。

## 数据维护（仅在用户要求时）

- 拆分原始 PDF：`python3 tools/build/chapter_split.py`；逐页提取矢量图到 Mermaid：`python3 tools/build/extract_figures_to_mermaid.py`，可通过 `--pdf <文件>` 限定。两者依赖 PyMuPDF (`fitz`)。
- 从已提取的 Markdown 重建文档索引与章节知识库：`python3 tools/build/gen_json.py --source <markdown目录> --output <输出目录>`、`python3 tools/build/gen_section_kb.py --source <markdown目录> --target <输出目录>`。默认的 `artifacts/out_md/` 未随资料包提供；不要假设仅凭 PDF 就能重建这些 JSON/JSONL。
- 先检查输入和 `--help`，将实验输出放在单独目录。生成脚本可能覆盖同名文件，不在普通问答时运行，也不覆盖现有知识库或人工修订的图。

本 skill 不包含独立的外部服务；项目中未纳入 CHI 问答与构建链路的 `llm_wiki/` 未打包。
