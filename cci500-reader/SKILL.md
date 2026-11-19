---
name: cci500-reader
description: "使用内置 CoreLink CCI-500 Technical Reference Manual r0p2（ARM 100023_0002_00_en）及章节知识库，回答 CCI-500 互连架构、ACE/ACE-Lite/AXI4 接口、Transaction Tracker、snoop filter 和寄存器问题。"
---

# CoreLink CCI-500 Technical Reference Manual

本 skill 是独立资料包。以本文件所在目录为 `SKILL_ROOT`，包含原文 `source/CCI-500-r0p2.pdf`、`kb/sections/`、`kb/docs/protocol_docs.json` 和 `tools/search_kb.py`。

原文为 CCI-500 r0p2 技术参考手册，文档编号 ARM 100023_0002_00_en，共 97 页；下载来源和校验值见 `source/provenance.json`。只依据该版本手册回答；涉及手册未覆盖的 AXI/ACE 通用规则或其他产品、版本时，说明证据范围并另查对应规范。

架构从 §1.5 CCI operation 开始查；接口查 §2.2 Interfaces；snoop filter 和事务处理查 §2.4 Operation；寄存器查 §3.3 Register descriptions。

## 回答

1. 在 `SKILL_ROOT` 执行 `python3 tools/search_kb.py "<问题或手册术语>" --json --top-k 8`；必要时用英文术语、`--section <章节号>` 重查，或用 `--list-sections` 查看范围。CLI 说明见 [docs/search_kb.md](docs/search_kb.md)。
2. 核对返回的 `text`、`source_page`、`matched_rules`、`matched_flows` 及 `kb/sections/<section_dir>/` 下的 `chunks.jsonl`、`rules.jsonl`、`flows.jsonl`。规则和步骤是启发式抽取，不能仅凭提取标签作为规范结论。可对照 `artifacts/split_pdfs/` 中的章节 PDF；这些文件按 PDF 目录或页组划分。
3. 先给直接结论，再解释适用条件与流程，最后列出准确的章节号、标题及 PDF 物理页码；需要时同时标明印刷页号。如果缺少证据，明确说明不能确认。本次未生成 Mermaid 图；图示、箭头和时序以原始 PDF 为准。

## 维护

原始输入与生成摘要在 `source/` 和 `artifacts/build_report.json`，本次检查结果在 `artifacts/validation_report.json`。若要重建，在新目录运行 `python3 tools/build_protocol_skill.py --input "source/CCI-500-r0p2.pdf" --name cci500-reader --title "CoreLink CCI-500 Technical Reference Manual" --output-parent <目标父目录>`；脚本不会覆盖已有目录。可用 `python3 tools/build/extract_figures_to_mermaid.py` 从矢量 PDF 生成近似图。检索器只依赖 Python 标准库；重建 PDF 需要 PyMuPDF。不要在日常问答时重建。
