"""Build a self-contained Codex protocol-reader skill from a document."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree


HEAD = re.compile(r"^(?:#{1,3}\s+(.+)|([A-Za-z]?\d+(?:\.\d+)+\s+.+))$")
IDENT = re.compile(r"^(?:Section\s+)?([A-Za-z]?\d+(?:\.\d+)*)(?:[.\s]+)(.*)$", re.I)
RULE = re.compile(r"\b(?:must(?:\s+not)?|shall(?:\s+not)?|may(?:\s+not)?|required|prohibited)\b|必须|应当|不得|可以|禁止|允许", re.I)
OBJECT = re.compile(r"\b(?:[A-Z][a-z]+(?:[A-Z][a-z0-9]+)+|[A-Z][A-Z0-9_]{2,})\b|`([^`]+)`")
CAPTION = re.compile(r"^(?P<kind>Figure|Fig\.?|Table|图|表)\s*(?P<label>[A-Za-z]?\d+(?:[.-]\d+)*)\s*[:.\s-]+(?P<title>.+)$", re.I)
SECTION_HEADING = re.compile(r"^(?:Section\s+)?[A-Za-z]?\d+\.\d+(?![.\d])(?:\s|$)", re.I)
STEP = re.compile(r"^\s*(?P<number>\d+)[.)、]\s+(?P<text>.+)")
DOCX_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


@dataclass
class Section:
    title: str
    pages: list[tuple[int | None, str]]
    start: int | None = None
    end: int | None = None


def slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return text[:55].strip("-") or "protocol-reader"


def safe_title(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().replace("\x00", "")[:120]


def file_part(value: str) -> str:
    text = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", safe_title(value))
    return text[:90].strip(" .") or "section"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for part in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def pdf_sections(source: Path) -> tuple[list[Section], list[int]]:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PDF input requires PyMuPDF: install the 'pymupdf' package") from exc
    with fitz.open(source) as doc:
        if doc.is_encrypted:
            raise ValueError("Encrypted PDF: provide a readable, decrypted document")
        if doc.page_count == 0:
            raise ValueError("PDF has no pages")
        pages = [page.get_text("text", sort=True).strip() for page in doc]
        if not any(pages):
            raise ValueError("No extractable PDF text; OCR the document first, then retry")
        unreadable = [i + 1 for i, text in enumerate(pages) if not text]
        toc = [(level, safe_title(label), page) for level, label, page in doc.get_toc() if 1 <= page <= doc.page_count]
        levels = sorted({level for level, _, _ in toc})
        numbered = [(level, label, page) for level, label, page in toc if SECTION_HEADING.match(label)]
        if numbered:
            chosen_level = max(levels, key=lambda level: sum(entry[0] == level for entry in numbered))
            chosen = [(label, page - 1) for level, label, page in numbered if level == chosen_level]
        else:
            chosen_level = levels[1] if len(levels) > 1 else (levels[0] if levels else None)
            chosen = [(label, page - 1) for level, label, page in toc if level == chosen_level]
        if chosen:
            # A numbered final section must not absorb trailing appendices or glossary pages.
            last_start = chosen[-1][1]
            chosen.extend((label, page - 1) for level, label, page in toc
                          if level == 1 and page - 1 > last_start)
            sections = []
            if chosen[0][1] > 0:
                sections.append(Section("Front matter", [(i + 1, pages[i]) for i in range(chosen[0][1])], 0, chosen[0][1]))
            for index, (title, start) in enumerate(chosen):
                next_start = chosen[index + 1][1] if index + 1 < len(chosen) else len(pages)
                end = max(start + 1, next_start)
                sections.append(Section(title, [(i + 1, pages[i]) for i in range(start, end)], start, end))
        else:
            sections = [Section(f"Pages {i + 1}-{min(i + 9, len(pages))}",
                                [(j + 1, pages[j]) for j in range(i, min(i + 9, len(pages)))],
                                i, min(i + 9, len(pages))) for i in range(0, len(pages), 9)]
        return sections, unreadable


def text_sections(source: Path) -> tuple[list[Section], list[int]]:
    if source.suffix.lower() == ".docx":
        with zipfile.ZipFile(source) as archive:
            tree = ElementTree.fromstring(archive.read("word/document.xml"))
        paragraphs = []
        for paragraph in tree.findall(".//w:body//w:p", DOCX_NS):
            text = "".join(node.text or "" for node in paragraph.findall(".//w:t", DOCX_NS)).strip()
            if not text:
                continue
            style = paragraph.find("./w:pPr/w:pStyle", DOCX_NS)
            if style is not None and "heading" in style.get(f"{{{DOCX_NS['w']}}}val", "").lower():
                text = "## " + text
            paragraphs.append(text)
        raw = "\n\n".join(paragraphs)
    else:
        raw = source.read_text(encoding="utf-8-sig").strip()
    if not raw:
        raise ValueError("Document contains no extractable text")
    lines = raw.splitlines()
    headings = []
    for i, line in enumerate(lines):
        found = HEAD.match(line.strip())
        if found and len(line) < 180:
            headings.append((i, safe_title(found.group(1) or found.group(2))))
    if not headings:
        return [Section(source.stem, [(None, raw)])], []
    sections = []
    if headings[0][0]:
        sections.append(Section("Introduction", [(None, "\n".join(lines[:headings[0][0]]))]))
    for index, (start, title) in enumerate(headings):
        end = headings[index + 1][0] if index + 1 < len(headings) else len(lines)
        sections.append(Section(title, [(None, "\n".join(lines[start:end]))]))
    return sections, []


def chunk_text(text: str, size: int = 1100, overlap: int = 160) -> list[str]:
    clean = text.strip()
    chunks = []
    start = 0
    while start < len(clean):
        end = min(len(clean), start + size)
        if end < len(clean):
            point = clean.rfind("\n", start + size // 2, end)
            if point > start + size // 2:
                end = point
        piece = clean[start:end].strip()
        if piece:
            chunks.append(piece)
        if end == len(clean):
            break
        start = max(start + 1, end - overlap)
    return chunks


def linked_chunks(chunks: list[dict], text: str) -> list[str]:
    needle = text.strip()[:45]
    return [chunk["chunkId"] for chunk in chunks if needle in chunk["text"]][:2]


def extract_records(section_id: str, text: str, chunks: list[dict]) -> dict[str, list[dict]]:
    rows: dict[str, list[dict]] = {kind: [] for kind in ("objects", "rules", "flows", "verification", "relations", "tables", "figures")}
    seen = set()
    for match in OBJECT.finditer(text):
        name = (match.group(1) or match.group()).strip()
        if name in seen or len(name) > 64:
            continue
        seen.add(name)
        rows["objects"].append({"objectId": f"{section_id}_obj_{len(seen):03d}", "name": name,
                                "objectType": "term", "description": "Extracted term (unverified)",
                                "sourceChunks": linked_chunks(chunks, name)})
        if len(seen) >= 120:
            break
    for sentence in re.split(r"(?<=[.!?。！？])\s+|\n+", text):
        sentence = " ".join(sentence.split())
        if len(sentence) > 18 and RULE.search(sentence):
            rows["rules"].append({"ruleId": f"{section_id}_rule_{len(rows['rules']) + 1:03d}",
                                  "title": sentence[:100], "requirement": sentence,
                                  "sourceChunks": linked_chunks(chunks, sentence), "confidence": "heuristic"})
    current = []
    for line in text.splitlines() + [""]:
        match = STEP.match(line)
        if match:
            current.append({"step": int(match.group("number")), "message": match.group("text").strip()})
        else:
            if len(current) > 1:
                steps_text = " ".join(step["message"] for step in current)
                rows["flows"].append({"name": f"Steps in {section_id}", "flowType": "numbered-list",
                                      "steps": current, "sourceChunks": linked_chunks(chunks, current[0]["message"]),
                                      "confidence": "heuristic"})
            current = []
        caption = CAPTION.match(line.strip())
        if caption:
            kind = "tables" if caption.group("kind").lower() in {"table", "表"} else "figures"
            rows[kind].append({"label": caption.group("label"), "title": caption.group("title"),
                               "sourceChunks": linked_chunks(chunks, line.strip())})
    return rows


def render_skill(name: str, title: str, original: str, is_pdf: bool) -> str:
    description = f"使用内置 {title} 协议原文及本地章节知识库回答该协议的定义、流程、字段与规则问题；需要查询 {title} 资料时使用。"
    desc = json.dumps(description, ensure_ascii=False)
    pdf_note = "可对照 `artifacts/split_pdfs/` 中的章节 PDF；这些文件按 PDF 目录或页组划分。" if is_pdf else "此输入不是 PDF，章节 PDF 目录为空；对照 `source/` 中的原文。"
    return f'''---
name: {name}
description: {desc}
---

# {title}

本 skill 是独立资料包。以本文件所在目录为 `SKILL_ROOT`，包含原文 `source/{original}`、`kb/sections/`、`kb/docs/protocol_docs.json` 和 `tools/search_kb.py`。只回答该文档实际覆盖的协议及版本；不要套用其他协议的术语或规则。

## 回答

1. 在 `SKILL_ROOT` 执行 `python3 tools/search_kb.py "<问题或协议术语>" --json --top-k 8`；必要时用英文术语、`--section <章节号>` 重查，或用 `--list-sections` 查看范围。CLI 说明见 [docs/search_kb.md](docs/search_kb.md)。
2. 核对返回的 `text`、`source_page`、`matched_rules`、`matched_flows` 及 `kb/sections/<section_dir>/` 下的 `chunks.jsonl`、`rules.jsonl`、`flows.jsonl`。规则和步骤是启发式抽取，不能仅凭提取标签作为规范结论。{pdf_note}
3. 先给直接结论，再解释适用条件与流程，最后列出准确的章节号、标题及 PDF 页码（如有）。如果缺少证据或原文是扫描页，明确说明不能确认。引用图片时以原文为准；`artifacts/figures_mermaid/` 只有成功识别的近似图，不保证完整或准确。

## 维护

原始输入与生成摘要在 `source/` 和 `artifacts/build_report.json`。若要重建，在新目录运行 `python3 tools/build_protocol_skill.py --input "source/{original}" --name {name} --output-parent <目标父目录>`；脚本不会覆盖已有目录。可用 `python3 tools/build/extract_figures_to_mermaid.py` 从矢量 PDF 生成近似图。检索器只依赖 Python 标准库；重建 PDF 需要 PyMuPDF。不要在日常问答时重建。
'''


def build(source: Path, destination: Path, title: str, name: str, with_mermaid: bool) -> dict:
    is_pdf = source.suffix.lower() == ".pdf"
    sections, unreadable = pdf_sections(source) if is_pdf else text_sections(source)
    stage = Path(tempfile.mkdtemp(prefix=f".{name}-", dir=destination.parent))
    try:
        for directory in ("source", "tools/build", "docs", "kb/sections", "kb/docs", "artifacts/split_pdfs", "artifacts/figures_mermaid"):
            (stage / directory).mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, stage / "source" / source.name)
        tool_dir = Path(__file__).resolve().parent
        shutil.copy2(tool_dir / "search_kb.py", stage / "tools" / "search_kb.py")
        shutil.copy2(tool_dir / "build_protocol_skill.py", stage / "tools" / "build_protocol_skill.py")
        (stage / "docs" / "search_kb.md").write_text(
            "# Protocol search\n\nRun `python3 tools/search_kb.py \"query\" --json --top-k 8` "
            "from this skill directory. Use repeatable `--section ID` to filter or "
            "`--list-sections` to list sections. JSON results include `text`, `source_file`, "
            "`source_page`, `matched_rules`, `matched_flows`, and `score`. Scores rank "
            "candidate evidence, not protocol truth; verify normative claims in `source/`.\n",
            encoding="utf-8",
        )
        figure_tool = tool_dir / "extract_figures_to_mermaid.py"
        if not figure_tool.exists():
            figure_tool = tool_dir / "build" / "extract_figures_to_mermaid.py"
        if with_mermaid and is_pdf and not figure_tool.exists():
            raise FileNotFoundError(f"Figure extraction tool not found: {figure_tool}")
        if figure_tool.exists():
            shutil.copy2(figure_tool, stage / "tools" / "build" / figure_tool.name)

        docs = []
        ids: set[str] = set()
        figure_count = 0
        chunk_count = 0
        with (nullcontext() if not is_pdf else open_pdf(source)) as pdf:
            for index, section in enumerate(sections, start=1):
                heading = safe_title(section.title) or f"Section {index}"
                parsed = IDENT.match(heading)
                section_id = parsed.group(1) if parsed else f"S{index:03d}"
                heading = parsed.group(2).strip() if parsed and parsed.group(2).strip() else heading
                base_id = section_id
                suffix = 2
                while section_id in ids:
                    section_id = f"{base_id}-{suffix}"
                    suffix += 1
                ids.add(section_id)
                label = file_part(f"{section_id} {heading}")
                section_dir = stage / "kb" / "sections" / label
                section_dir.mkdir()
                if is_pdf:
                    import fitz
                    split = fitz.open()
                    split.insert_pdf(pdf, from_page=section.start, to_page=section.end - 1)
                    split.save(stage / "artifacts" / "split_pdfs" / f"{label}.pdf")
                    split.close()

                full_text = "\n\n".join(text for _, text in section.pages if text).strip()
                chunks = []
                for page, text in section.pages:
                    for piece in chunk_text(text):
                        chunks.append({"chunkId": f"{section_id}_C{len(chunks) + 1:04d}",
                                       "pdfId": section_id, "text": piece, "subsection": heading,
                                       "sourceType": "pdf" if is_pdf else "document", "page": page,
                                       "topics": [], "keywords": []})
                records = extract_records(section_id, full_text, chunks)
                meta = {"pdfId": section_id, "title": heading, "sourceFile": f"source/{source.name}",
                        "pageStart": section.start + 1 if is_pdf else None,
                        "pageEnd": section.end if is_pdf else None,
                        "contentTypes": {"hasChunks": bool(chunks), "hasObjects": bool(records["objects"]),
                                         "hasRules": bool(records["rules"]), "hasFlows": bool(records["flows"]),
                                         "hasVerificationPoints": False, "hasTables": bool(records["tables"]),
                                         "hasFigures": bool(records["figures"])},
                        "processingStatus": {"extracted": bool(chunks), "reviewed": False,
                                             "quality": "automatic; check source for normative claims"},
                        "recordStats": {"chunks": len(chunks), **{kind: len(rows) for kind, rows in records.items()}}}
                write_json(section_dir / "meta.json", meta)
                write_jsonl(section_dir / "chunks.jsonl", chunks)
                for kind, rows in records.items():
                    write_jsonl(section_dir / f"{kind}.jsonl", rows)
                docs.append({"section_id": section_id, "title": heading, "source": meta["sourceFile"],
                             "page_start": meta["pageStart"], "page_end": meta["pageEnd"],
                             "section_dir": label, "text": full_text})
                figure_count += len(records["figures"])
                chunk_count += len(chunks)

        write_json(stage / "kb" / "docs" / "protocol_docs.json", {"documents": docs})
        if with_mermaid and is_pdf and figure_tool.exists():
            subprocess.run([sys.executable, str(stage / "tools" / "build" / figure_tool.name),
                            "--input-dir", "artifacts/split_pdfs", "--output-dir", "artifacts/figures_mermaid"],
                           cwd=stage, check=True, stdout=subprocess.DEVNULL)
        report = {"title": title, "name": name, "source": f"source/{source.name}",
                  "sha256": file_hash(source),
                  "sections": len(docs), "chunks": chunk_count, "figure_captions": figure_count,
                  "mermaid_files": len(list((stage / "artifacts" / "figures_mermaid").glob("*.mmd"))),
                  "pages_without_text": unreadable}
        write_json(stage / "artifacts" / "build_report.json", report)
        (stage / "SKILL.md").write_text(render_skill(name, title, source.name, is_pdf), encoding="utf-8")
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"Refusing to replace existing skill: {destination}")
        stage.rename(destination)
        return report
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def open_pdf(source: Path):
    import fitz
    return fitz.open(source)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a self-contained protocol-reader Codex skill.")
    parser.add_argument("--input", type=Path, required=True, help="Text PDF, Markdown, TXT or DOCX protocol document")
    parser.add_argument("--name", help="Skill name: lowercase letters, digits and hyphens")
    parser.add_argument("--title", help="Protocol title shown in the generated skill")
    parser.add_argument("--output-parent", type=Path,
                        default=Path(os.getenv("CODEX_HOME", Path.home() / ".codex")) / "skills")
    parser.add_argument("--with-mermaid", action="store_true", help="Attempt approximate vector-PDF figure conversion")
    args = parser.parse_args()
    source = args.input.expanduser().resolve()
    if not source.is_file() or source.suffix.lower() not in {".pdf", ".md", ".txt", ".docx"}:
        parser.error("--input must be an existing PDF, Markdown, TXT or DOCX file")
    if args.with_mermaid and source.suffix.lower() != ".pdf":
        parser.error("--with-mermaid requires a PDF input")
    name = args.name or slug(source.stem)
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) >= 64:
        parser.error("--name must use lowercase letters, digits and hyphens (under 64 characters)")
    title = safe_title(args.title or source.stem)
    parent = args.output_parent.expanduser().resolve()
    destination = parent / name
    if destination.exists() or destination.is_symlink():
        parser.error(f"output exists: {destination}")
    parent.mkdir(parents=True, exist_ok=True)
    try:
        report = build(source, destination, title, name, args.with_mermaid)
    except (ValueError, FileNotFoundError, RuntimeError, zipfile.BadZipFile, KeyError, UnicodeError) as exc:
        parser.error(str(exc))
    print(json.dumps({"skill_path": str(destination), **report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
