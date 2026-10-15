from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path


SECTION_RE = re.compile(r"^([A-Z]\d+(?:\.\d+)+)\s+(.+)$")
CHAPTER_RE = re.compile(r"^Chapter\s+([A-Z]\d+(?:\.\d+)*)\.?\s*(.*)$", re.IGNORECASE)
MULTI_SPACE_RE = re.compile(r"[ \t]+")


@dataclass
class Chunk:
	chunk_id: str
	text: str
	start_char: int
	end_char: int


def parse_filename(stem: str) -> tuple[str, str, str]:
	"""Return (section_id, title, full_title) from a markdown filename stem."""
	m = SECTION_RE.match(stem.strip())
	if m:
		section_id = m.group(1)
		title = m.group(2).strip()
		return section_id, title, f"{section_id} {title}".strip()
	return "", stem.strip(), stem.strip()


def is_noise_line(line: str) -> bool:
	s = line.strip()
	if not s:
		return True
	if re.fullmatch(r"\d+", s):
		return True
	if re.fullmatch(r"[\-_=]{3,}", s):
		return True
	return False


def normalize_line(line: str) -> str:
	# Keep bullets and punctuation, but normalize repeated spaces.
	return MULTI_SPACE_RE.sub(" ", line.strip())


def normalize_text(raw: str) -> str:
	lines: list[str] = []
	blank_count = 0
	for line in raw.splitlines():
		if is_noise_line(line):
			blank_count += 1
			if blank_count <= 1:
				lines.append("")
			continue
		blank_count = 0
		lines.append(normalize_line(line))

	text = "\n".join(lines)
	text = re.sub(r"\n{3,}", "\n\n", text)
	return text.strip()


def split_into_chunks(text: str, target_chars: int = 1000, overlap_chars: int = 150) -> list[Chunk]:
	if not text:
		return []

	paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
	chunks: list[Chunk] = []
	current_parts: list[str] = []
	current_len = 0
	global_offset = 0

	def flush_chunk() -> None:
		nonlocal current_parts, current_len, global_offset
		if not current_parts:
			return

		chunk_text = "\n\n".join(current_parts).strip()
		if not chunk_text:
			current_parts = []
			current_len = 0
			return

		start = global_offset
		end = start + len(chunk_text)
		chunk_id = f"c{len(chunks) + 1:04d}"
		chunks.append(Chunk(chunk_id=chunk_id, text=chunk_text, start_char=start, end_char=end))

		# Build overlap context from the end of current chunk.
		overlap_text = chunk_text[-overlap_chars:].strip() if overlap_chars > 0 else ""
		if overlap_text:
			current_parts = [overlap_text]
			current_len = len(overlap_text)
			global_offset = max(0, end - len(overlap_text))
		else:
			current_parts = []
			current_len = 0
			global_offset = end

	for para in paragraphs:
		para_len = len(para)

		if para_len > target_chars:
			flush_chunk()
			start = 0
			while start < para_len:
				end = min(start + target_chars, para_len)
				piece = para[start:end].strip()
				if piece:
					piece_id = f"c{len(chunks) + 1:04d}"
					piece_start = global_offset
					piece_end = piece_start + len(piece)
					chunks.append(
						Chunk(
							chunk_id=piece_id,
							text=piece,
							start_char=piece_start,
							end_char=piece_end,
						)
					)
					global_offset = piece_end
				if end >= para_len:
					break
				start = max(0, end - overlap_chars)
			continue

		extra_sep = 2 if current_parts else 0
		if current_len + extra_sep + para_len <= target_chars:
			current_parts.append(para)
			current_len += extra_sep + para_len
		else:
			flush_chunk()
			current_parts.append(para)
			current_len = len(para)

	flush_chunk()
	return chunks


def load_markdown(path: Path) -> str:
	return path.read_text(encoding="utf-8", errors="ignore")


def build_document(md_path: Path, source_root: Path, target_chars: int, overlap_chars: int) -> dict:
	raw_text = load_markdown(md_path)
	normalized = normalize_text(raw_text)

	section_id, title, full_title = parse_filename(md_path.stem)
	relative = md_path.relative_to(source_root).as_posix()
	doc_id = md_path.with_suffix("").relative_to(source_root).as_posix().replace("/", "::")

	# Best effort: use first chapter line as fallback title when filename is weak.
	if not section_id:
		for line in normalized.splitlines():
			match = CHAPTER_RE.match(line)
			if match:
				section_id = match.group(1).strip()
				chapter_title = match.group(2).strip()
				if chapter_title:
					title = chapter_title
					full_title = f"{section_id} {title}".strip()
				else:
					full_title = section_id
				break

	chunks = split_into_chunks(normalized, target_chars=target_chars, overlap_chars=overlap_chars)
	chunk_items = [
		{
			"chunk_id": ch.chunk_id,
			"text": ch.text,
			"start_char": ch.start_char,
			"end_char": ch.end_char,
			"char_count": len(ch.text),
		}
		for ch in chunks
	]

	return {
		"doc_id": doc_id,
		"source": relative,
		"section_id": section_id,
		"title": title,
		"full_title": full_title,
		"text": normalized,
		"char_count": len(normalized),
		"chunks": chunk_items,
	}


def collect_markdown_files(source_root: Path) -> list[Path]:
	return sorted(p for p in source_root.rglob("*.md") if p.is_file())


def export_documents(
	source_root: Path,
	output_dir: Path,
	target_chars: int,
	overlap_chars: int,
	docs_name: str,
	chunks_name: str,
) -> tuple[Path, Path, int, int]:
	md_files = collect_markdown_files(source_root)
	documents: list[dict] = []
	total_chunks = 0

	for md in md_files:
		doc = build_document(
			md_path=md,
			source_root=source_root,
			target_chars=target_chars,
			overlap_chars=overlap_chars,
		)
		if not doc["text"]:
			continue
		documents.append(doc)
		total_chunks += len(doc["chunks"])

	output_dir.mkdir(parents=True, exist_ok=True)
	docs_path = output_dir / docs_name
	chunks_path = output_dir / chunks_name

	docs_payload = {
		"dataset": "CHI_markdown",
		"source_dir": source_root.as_posix(),
		"doc_count": len(documents),
		"chunk_count": total_chunks,
		"documents": documents,
	}
	docs_path.write_text(json.dumps(docs_payload, ensure_ascii=False, indent=2), encoding="utf-8")

	with chunks_path.open("w", encoding="utf-8") as f:
		for doc in documents:
			for chunk in doc["chunks"]:
				row = {
					"id": f"{doc['doc_id']}::{chunk['chunk_id']}",
					"doc_id": doc["doc_id"],
					"chunk_id": chunk["chunk_id"],
					"section_id": doc["section_id"],
					"title": doc["title"],
					"full_title": doc["full_title"],
					"source": doc["source"],
					"text": chunk["text"],
					"char_count": chunk["char_count"],
				}
				f.write(json.dumps(row, ensure_ascii=False) + "\n")

	return docs_path, chunks_path, len(documents), total_chunks


def build_arg_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Convert CHI markdown files to retrieval-ready JSON.")
	parser.add_argument("--source", type=Path, default=None, help="Markdown root directory. Default: <project>/artifacts/out_md")
	parser.add_argument("--output", type=Path, default=None, help="Output directory. Default: <project>/kb/docs")
	parser.add_argument("--target-chars", type=int, default=1000, help="Target chunk size in characters.")
	parser.add_argument("--overlap-chars", type=int, default=150, help="Chunk overlap size in characters.")
	parser.add_argument("--docs-name", default="chi_docs.json", help="Filename for document-level JSON.")
	parser.add_argument("--chunks-name", default="chi_chunks.jsonl", help="Filename for chunk-level JSONL.")
	return parser


def main() -> None:
	parser = build_arg_parser()
	args = parser.parse_args()

	project_root = Path(__file__).resolve().parents[2]
	source_root = args.source if args.source else (project_root / "artifacts" / "out_md")
	output_dir = args.output if args.output else (project_root / "kb" / "docs")

	if not source_root.exists():
		raise FileNotFoundError(f"Source markdown directory not found: {source_root}")

	docs_path, chunks_path, doc_count, chunk_count = export_documents(
		source_root=source_root,
		output_dir=output_dir,
		target_chars=max(200, args.target_chars),
		overlap_chars=max(0, args.overlap_chars),
		docs_name=args.docs_name,
		chunks_name=args.chunks_name,
	)

	print(f"Done. documents={doc_count}, chunks={chunk_count}")
	print(f"Document JSON: {docs_path}")
	print(f"Chunk JSONL:   {chunks_path}")


if __name__ == "__main__":
	main()
