"""Search a generated protocol skill's section knowledge base."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path


WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.-]*|\d+(?:\.\d+)*|[\u3400-\u9fff]+")
PART_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z]|\b)|[A-Z]?[a-z]+|\d+")
STOP = {"a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "of", "on", "or", "the", "to", "with"}
FLOW_HINTS = ("flow", "sequence", "steps", "流程", "步骤", "时序")
RULE_HINTS = ("rule", "must", "shall", "require", "forbidden", "规定", "必须", "禁止", "允许")


def tokenize(text: str) -> list[str]:
    terms: list[str] = []
    for match in WORD_RE.finditer(text):
        word = match.group()
        if "\u3400" <= word[0] <= "\u9fff":
            terms.extend(word[i : i + 2] for i in range(len(word) - 1))
            if len(word) == 1:
                terms.append(word)
        else:
            terms.append(word.lower())
            if word != word.lower() or any(ch in word for ch in "_.-"):
                terms.extend(part.lower() for part in PART_RE.findall(word) if len(part) > 2)
    return [term for term in terms if term not in STOP]


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def compact(text: str, limit: int = 280) -> str:
    clean = " ".join(text.split())
    return clean if len(clean) <= limit else clean[: limit - 3].rstrip() + "..."


def search(root: Path, query: str, top_k: int, filters: list[str]) -> list[dict]:
    section_root = root / "kb" / "sections"
    if not section_root.is_dir():
        raise FileNotFoundError(f"Knowledge base not found: {section_root}")
    sections: list[tuple[dict, list[dict]]] = []
    chunks: list[tuple[dict, dict, dict[str, list[dict]]]] = []
    for directory in sorted(section_root.iterdir()):
        if not directory.is_dir() or not (directory / "meta.json").exists():
            continue
        meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
        meta["section_dir"] = directory.name
        records = read_jsonl(directory / "chunks.jsonl")
        sections.append((meta, records))
        kinds = {kind: defaultdict(list) for kind in ("objects", "rules", "flows", "verification")}
        for kind, mapping in kinds.items():
            for item in read_jsonl(directory / f"{kind}.jsonl"):
                for source in item.get("sourceChunks", []):
                    mapping[source].append(item)
        for item in records:
            chunks.append((meta, item, {kind: mapping[item["chunkId"]] for kind, mapping in kinds.items()}))

    terms = tokenize(query)
    qnorm = query.casefold().strip()
    counts = Counter()
    for _, item, _ in chunks:
        counts.update(set(tokenize(item.get("text", ""))))
    avglen = sum(len(tokenize(item.get("text", ""))) for _, item, _ in chunks) / max(1, len(chunks))
    hints = {"rules": any(h in qnorm for h in RULE_HINTS), "flows": any(h in qnorm for h in FLOW_HINTS)}
    ranked = []
    for meta, item, linked in chunks:
        section = str(meta.get("pdfId", ""))
        title = str(meta.get("title", ""))
        label = f"{section} {title}".strip()
        if filters and not any(f.casefold() in (section.casefold(), title.casefold(), label.casefold(), meta["section_dir"].casefold()) for f in filters):
            continue
        text = item.get("text", "")
        term_counts = Counter(tokenize(text))
        length = max(1, sum(term_counts.values()))
        score = 0.0
        reasons = []
        for term in set(terms):
            tf = term_counts[term]
            if tf:
                idf = math.log(1 + (len(chunks) - counts[term] + 0.5) / (counts[term] + 0.5))
                score += idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * length / max(1, avglen)))
        if score:
            reasons.append("chunk term overlap")
        if qnorm and (qnorm in label.casefold() or label.casefold() in qnorm and len(label) >= 4):
            score += 5
            reasons.append("section title match")
        for kind, rows in linked.items():
            if not rows:
                continue
            relevant = hints.get(kind, False) or any(
                term in tokenize(" ".join(str(value) for value in row.values() if isinstance(value, str)))
                for row in rows for term in terms
            )
            if relevant:
                score += min(len(rows), 3) * (1.4 if hints.get(kind, False) else 0.6)
                reasons.append(f"matched {kind}")
        if score <= 0:
            continue
        def labels(kind: str) -> list[str]:
            return [str(row.get("name") or row.get("title") or row.get("requirement") or "") for row in linked[kind]][:5]
        ranked.append({
            "chunk_id": item["chunkId"], "section_dir": meta["section_dir"], "section": section,
            "title": label, "subsection": item.get("subsection"), "score": round(score, 4),
            "text": text, "snippet": compact(text), "source_type": item.get("sourceType"),
            "source_file": meta.get("sourceFile", ""), "source_page": item.get("page"),
            "matched_objects": labels("objects"), "matched_rules": labels("rules"),
            "matched_flows": labels("flows"), "matched_verification": labels("verification"),
            "reasons": reasons,
        })
    return sorted(ranked, key=lambda row: (-row["score"], row["title"], row["chunk_id"]))[:top_k]


def main() -> None:
    parser = argparse.ArgumentParser(description="Search a generated protocol skill's knowledge base.")
    parser.add_argument("query", nargs="?")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--section", action="append", default=[])
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--list-sections", action="store_true")
    args = parser.parse_args()
    if args.list_sections:
        rows = []
        for path in sorted((args.project_root / "kb" / "sections").glob("*/meta.json")):
            meta = json.loads(path.read_text(encoding="utf-8"))
            rows.append({"section_dir": path.parent.name, "section": meta["pdfId"], "title": meta["title"]})
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            for row in rows:
                print(f"{row['section']}\t{row['title']}")
        return
    if not args.query:
        parser.error("query is required unless --list-sections is used")
    results = search(args.project_root.resolve(), args.query, max(1, args.top_k), args.section)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for row in results:
            print(f"[{row['score']:.2f}] {row['title']} (p. {row['source_page']}): {row['snippet']}")


if __name__ == "__main__":
    main()
