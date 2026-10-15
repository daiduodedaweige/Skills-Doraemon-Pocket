---
name: axi-ace-reader
description: "使用内置 AMBA AXI and ACE Protocol Specification (ARM IHI 0022D; AXI3, AXI4, AXI4-Lite, ACE and ACE-Lite) 协议原文及本地章节知识库回答该协议的定义、流程、字段与规则问题；需要查询 AMBA AXI and ACE Protocol Specification (ARM IHI 0022D; AXI3, AXI4, AXI4-Lite, ACE and ACE-Lite) 资料时使用。"
---

# AMBA AXI and ACE Protocol Specification (ARM IHI 0022D; AXI3, AXI4, AXI4-Lite, ACE and ACE-Lite)

本 skill 是独立资料包。以本文件所在目录为 `SKILL_ROOT`，包含原文 `source/AXI4_specification.pdf`、`kb/sections/`、`kb/docs/protocol_docs.json` 和 `tools/search_kb.py`。只回答该文档实际覆盖的协议及版本；不要套用其他协议的术语或规则。

## 回答

1. 在 `SKILL_ROOT` 执行 `python3 tools/search_kb.py "<问题或协议术语>" --json --top-k 8`；必要时用英文术语、`--section <章节号>` 重查，或用 `--list-sections` 查看范围。CLI 说明见 [docs/search_kb.md](docs/search_kb.md)。
2. 核对返回的 `text`、`source_page`、`matched_rules`、`matched_flows` 及 `kb/sections/<section_dir>/` 下的 `chunks.jsonl`、`rules.jsonl`、`flows.jsonl`。规则和步骤是启发式抽取，不能仅凭提取标签作为规范结论。可对照 `artifacts/split_pdfs/` 中的章节 PDF；这些文件按 PDF 目录或页组划分。
3. 先给直接结论，再解释适用条件与流程，最后列出准确的章节号、标题及 PDF 页码（如有）。如果缺少证据或原文是扫描页，明确说明不能确认。引用图片时以原文为准；`artifacts/figures_mermaid/` 只有成功识别的近似图，不保证完整或准确。

## 维护

原始输入与生成摘要在 `source/` 和 `artifacts/build_report.json`。若要重建，在新目录运行 `python3 tools/build_protocol_skill.py --input "source/AXI4_specification.pdf" --name axi-ace-reader --output-parent <目标父目录>`；脚本不会覆盖已有目录。可用 `python3 tools/build/extract_figures_to_mermaid.py` 从矢量 PDF 生成近似图。检索器只依赖 Python 标准库；重建 PDF 需要 PyMuPDF。不要在日常问答时重建。
