---
name: readskill-builder
description: 将用户提供的协议规范文档（文本 PDF、DOCX、Markdown 或 TXT）生成自带原文、章节知识库、检索器和 Codex SKILL.md 的独立协议问答 skill。用于“把某份协议文档做成 chi-reader 那样的 skill”的请求。
---

# Protocol Skill Builder

从一份协议文档生成一个可直接作为 Codex skill 使用的目录，不复用 CHI 专用术语或知识库。使用本 skill 同目录的 `scripts/build_protocol_skill.py`；输出不依赖本生成器或原项目。生成物与 chi-reader 使用相同的 `source/`、`kb/sections/`、`kb/docs/`、`artifacts/split_pdfs/`、`artifacts/figures_mermaid/`、`tools/` 和 `SKILL.md` 层次。

## 工作流

1. 确认文档路径；从文件名推断协议名称和 skill 名，名称不明确时向用户确认。支持 `.pdf`、`.docx`、`.md`、`.txt`；PDF 需要可提取的文字和 PyMuPDF。扫描件先 OCR 成带文本层的 PDF，不能静默生成空知识库。
2. 默认输出到 `$CODEX_HOME/skills`（未设置时 `~/.codex/skills`）；若用户指定其他位置，用 `--output-parent`。安装到工作区外时先取得相应写入权限，不绕过权限限制。绝不覆盖已有同名 skill；新版本可使用新名称或用户明确授权的更新流程。
3. 运行：`python3 scripts/build_protocol_skill.py --input "<文档路径>" --name <小写英文名> --title "<协议名称>" --output-parent "<目录>"`。需要尝试从矢量 PDF 自动还原 Mermaid 时添加 `--with-mermaid`；这类图仅是近似表示，不能替代原文。
4. 检查生成物的 `artifacts/build_report.json`，尤其是 `pages_without_text`。运行 skill-creator 的 `quick_validate.py <新 skill 目录>`，再从**另一个工作目录**运行 `<新 skill>/tools/search_kb.py "<文档中特有术语>" --json`，核对章节、证据文本和原文页码。抽查原始 PDF 与章节 PDF 的内容一致。安装后提示新会话以 `$<skill-name>` 调用。

## 证据边界

目录书签优先用于分章；无书签的 PDF 按每九页分组。规则、步骤及图注只做启发式索引，不能当作已审定的协议语义。缺失文字层的页面会写入报告；相关问题必须核对原文或明确说明资料未覆盖。DOCX/Markdown/TXT 保留原件且生成文本章节，不伪造 PDF 或 Mermaid。完整文档与拆分结果可能较大，这是用户希望原文驻留 skill 的正常代价。
