from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.-]*|\d+(?:\.\d+)+")
CAMEL_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z]|[0-9]|\b)|[A-Z]?[a-z]+|[0-9]+")

RULE_HINTS = {
    "must",
    "required",
    "requirement",
    "permitted",
    "allowed",
    "forbidden",
    "cannot",
    "mustnot",
    "illegal",
    "rule",
    "rules",
    "constraint",
}
FLOW_HINTS = {
    "flow",
    "flows",
    "step",
    "steps",
    "sequence",
    "path",
    "transactionflow",
}
CHINESE_RULE_HINTS = ("必须", "不允许", "允许", "禁止", "规则", "约束")
CHINESE_FLOW_HINTS = ("流程", "步骤", "顺序", "时序")
STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "for",
    "with",
    "in",
    "on",
    "by",
    "is",
    "are",
    "be",
    "as",
    "that",
    "this",
    "from",
    "at",
    "it",
    "can",
    "all",
    "any",
    "into",
    "when",
    "where",
    "after",
    "before",
    "under",
    "between",
    "use",
    "using",
    "used",
    "request",
    "response",
    "transaction",
    "transactions",
    "message",
    "messages",
}


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in TOKEN_RE.findall(text or ""):
        token = raw.strip()
        if not token:
            continue
        lowered = token.lower()
        tokens.append(lowered)
        if any(c.isupper() for c in token) or "." in token or "_" in token or "-" in token:
            pieces = [piece.lower() for piece in CAMEL_RE.findall(token) if piece]
            for piece in pieces:
                if piece != lowered and (piece.isdigit() or len(piece) >= 4):
                    tokens.append(piece)
    return tokens


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def shorten(text: str, limit: int = 260) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


@dataclass
class SectionInfo:
    section_dir: str
    pdf_id: str
    title: str
    full_title: str
    meta: dict[str, Any]
    doc_text: str = ""
    source_file: str = ""


@dataclass
class ChunkRecord:
    chunk_id: str
    section_dir: str
    pdf_id: str
    full_title: str
    text: str
    subsection: str | None
    topics: list[str]
    keywords: list[str]
    source_type: str | None
    tokens: list[str] = field(default_factory=list)
    tf: Counter[str] = field(default_factory=Counter)
    length: int = 0


@dataclass
class MatchContext:
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    objects: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    flows: list[str] = field(default_factory=list)
    verification: list[str] = field(default_factory=list)


class ChiRetriever:
    def __init__(self, project_root: Path, json_dir: Path, docs_path: Path | None = None) -> None:
        self.project_root = project_root
        self.json_dir = json_dir
        self.docs_path = docs_path

        self.sections: dict[str, SectionInfo] = {}
        self.chunks: dict[str, ChunkRecord] = {}
        self.chunk_df: Counter[str] = Counter()
        self.avg_chunk_len = 0.0

        self.objects: list[dict[str, Any]] = []
        self.rules: list[dict[str, Any]] = []
        self.flows: list[dict[str, Any]] = []
        self.verification: list[dict[str, Any]] = []
        self.relations: list[dict[str, Any]] = []

        self.objects_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.objects_by_term: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.rules_by_term: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.flows_by_term: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.verification_by_term: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.relations_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)

        self._load()

    def _load(self) -> None:
        docs_by_section = self._load_docs()
        chunk_lengths: list[int] = []

        for section_dir in sorted(p for p in self.json_dir.iterdir() if p.is_dir()):
            meta_path = section_dir / "meta.json"
            if not meta_path.exists():
                continue
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            pdf_id = meta.get("pdfId") or ""
            title = meta.get("title") or section_dir.name
            full_title = f"{pdf_id} {title}".strip()
            doc_info = docs_by_section.get(pdf_id, {})
            source_file = meta.get("sourceFile") or doc_info.get("source", "")
            self.sections[section_dir.name] = SectionInfo(
                section_dir=section_dir.name,
                pdf_id=pdf_id,
                title=title,
                full_title=full_title,
                meta=meta,
                doc_text=doc_info.get("text", ""),
                source_file=source_file,
            )

            for row in self._read_jsonl(section_dir / "chunks.jsonl"):
                chunk_id = row.get("chunkId")
                if not chunk_id:
                    continue
                tokens = [token for token in tokenize(row.get("text", "")) if token not in STOPWORDS]
                tf = Counter(tokens)
                chunk = ChunkRecord(
                    chunk_id=chunk_id,
                    section_dir=section_dir.name,
                    pdf_id=pdf_id,
                    full_title=full_title,
                    text=row.get("text", ""),
                    subsection=row.get("subsection"),
                    topics=row.get("topics", []),
                    keywords=row.get("keywords", []),
                    source_type=row.get("sourceType"),
                    tokens=tokens,
                    tf=tf,
                    length=max(1, len(tokens)),
                )
                self.chunks[chunk_id] = chunk
                chunk_lengths.append(chunk.length)
                for term in tf:
                    self.chunk_df[term] += 1

            for row in self._read_jsonl(section_dir / "objects.jsonl"):
                row["_section_dir"] = section_dir.name
                row["_full_title"] = full_title
                row["_search_blob"] = " ".join(
                    [
                        row.get("name", ""),
                        row.get("objectType", ""),
                        row.get("transactionClass", "") or "",
                        row.get("description", "") or "",
                        " ".join(row.get("relatedObjects", []) or []),
                    ]
                )
                self.objects.append(row)
                norm = normalize_name(row.get("name", ""))
                if norm:
                    self.objects_by_name[norm].append(row)
                for term in set(tokenize(row["_search_blob"])):
                    if term not in STOPWORDS:
                        self.objects_by_term[term].append(row)

            for row in self._read_jsonl(section_dir / "rules.jsonl"):
                row["_section_dir"] = section_dir.name
                row["_full_title"] = full_title
                row["_search_blob"] = " ".join(
                    [
                        row.get("title", ""),
                        row.get("requirement", "") or "",
                        row.get("condition", "") or "",
                        " ".join(row.get("forbidden", []) or []),
                        " ".join(row.get("appliesTo", []) or []),
                        " ".join(row.get("relatedObjects", []) or []),
                    ]
                )
                self.rules.append(row)
                for term in set(tokenize(row["_search_blob"])):
                    if term not in STOPWORDS:
                        self.rules_by_term[term].append(row)

            for row in self._read_jsonl(section_dir / "flows.jsonl"):
                row["_section_dir"] = section_dir.name
                row["_full_title"] = full_title
                step_text = " ".join(
                    " ".join(
                        [
                            str(step.get("step", "")),
                            step.get("from", "") or "",
                            step.get("to", "") or "",
                            step.get("channel", "") or "",
                            step.get("message", "") or "",
                            step.get("condition", "") or "",
                        ]
                    )
                    for step in (row.get("steps", []) or [])
                )
                row["_search_blob"] = " ".join(
                    [
                        row.get("name", ""),
                        row.get("flowType", ""),
                        " ".join(row.get("appliesTo", []) or []),
                        " ".join(row.get("participants", []) or []),
                        row.get("completionCondition", "") or "",
                        step_text,
                    ]
                )
                self.flows.append(row)
                for term in set(tokenize(row["_search_blob"])):
                    if term not in STOPWORDS:
                        self.flows_by_term[term].append(row)

            for row in self._read_jsonl(section_dir / "verification.jsonl"):
                row["_section_dir"] = section_dir.name
                row["_full_title"] = full_title
                row["_search_blob"] = " ".join(
                    [
                        row.get("title", ""),
                        row.get("objective", "") or "",
                        row.get("stimulus", "") or "",
                        row.get("expectedBehavior", "") or "",
                        row.get("method", "") or "",
                        " ".join(row.get("relatedObjects", []) or []),
                        " ".join(row.get("relatedRules", []) or []),
                    ]
                )
                self.verification.append(row)
                for term in set(tokenize(row["_search_blob"])):
                    if term not in STOPWORDS:
                        self.verification_by_term[term].append(row)

            for row in self._read_jsonl(section_dir / "relations.jsonl"):
                row["_section_dir"] = section_dir.name
                row["_full_title"] = full_title
                self.relations.append(row)
                for key in (row.get("from"), row.get("to")):
                    norm = normalize_name(str(key or ""))
                    if norm:
                        self.relations_by_name[norm].append(row)

        self.avg_chunk_len = sum(chunk_lengths) / len(chunk_lengths) if chunk_lengths else 1.0

    def _load_docs(self) -> dict[str, dict[str, Any]]:
        if not self.docs_path or not self.docs_path.exists():
            return {}
        payload = json.loads(self.docs_path.read_text(encoding="utf-8"))
        documents = payload.get("documents", [])
        docs_by_section: dict[str, dict[str, Any]] = {}
        for doc in documents:
            section_id = doc.get("section_id") or ""
            if section_id:
                docs_by_section[section_id] = doc
        return docs_by_section

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        return rows

    def search(
        self,
        query: str,
        top_k: int = 5,
        section_filters: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        query_tokens = [token for token in tokenize(query) if token not in STOPWORDS]
        if not query_tokens and not query.strip():
            return []

        section_filter_set = self._resolve_section_filters(section_filters or [])
        query_norm = normalize_name(query)
        if not section_filter_set:
            section_filter_set = self._implicit_route_filters(query_norm, query_tokens)
        wants_rules, wants_flows = self._detect_intent(query, query_tokens)

        matches: dict[str, MatchContext] = defaultdict(MatchContext)

        self._score_section_routes(query_norm, query_tokens, matches, section_filter_set)
        self._score_chunks(query_tokens, matches, section_filter_set)
        self._score_objects(query_tokens, query_norm, matches, section_filter_set)
        self._score_rules(query_tokens, query_norm, matches, section_filter_set, wants_rules)
        self._score_flows(query_tokens, query_norm, matches, section_filter_set, wants_flows)
        self._score_verification(query_tokens, matches, section_filter_set, wants_rules, wants_flows)
        self._expand_relations(matches, section_filter_set)

        ranked = []
        for chunk_id, ctx in matches.items():
            chunk = self.chunks.get(chunk_id)
            if not chunk:
                continue
            ranked.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "section_dir": chunk.section_dir,
                    "section": chunk.pdf_id,
                    "title": chunk.full_title,
                    "subsection": chunk.subsection,
                    "score": round(ctx.score, 4),
                    "text": chunk.text,
                    "snippet": shorten(chunk.text),
                    "topics": chunk.topics,
                    "keywords": chunk.keywords,
                    "source_type": chunk.source_type,
                    "source_file": self.sections[chunk.section_dir].source_file,
                    "matched_objects": dedupe_keep_order(ctx.objects),
                    "matched_rules": dedupe_keep_order(ctx.rules),
                    "matched_flows": dedupe_keep_order(ctx.flows),
                    "matched_verification": dedupe_keep_order(ctx.verification),
                    "reasons": dedupe_keep_order(ctx.reasons),
                }
            )

        ranked.sort(key=lambda item: (-item["score"], item["title"], item["chunk_id"]))
        return ranked[:top_k]

    def _resolve_section_filters(self, raw_filters: list[str]) -> set[str]:
        if not raw_filters:
            return set()
        resolved: set[str] = set()
        for raw in raw_filters:
            raw_norm = normalize_name(raw)
            if not raw_norm:
                continue
            for section_dir, section in self.sections.items():
                candidates = {
                    normalize_name(section_dir),
                    normalize_name(section.pdf_id),
                    normalize_name(section.title),
                    normalize_name(section.full_title),
                }
                if raw_norm in candidates:
                    resolved.add(section_dir)
                elif raw_norm in normalize_name(section.full_title):
                    resolved.add(section_dir)
        return resolved

    def _detect_intent(self, query: str, query_tokens: list[str]) -> tuple[bool, bool]:
        token_set = set(query_tokens)
        wants_rules = bool(token_set & RULE_HINTS) or any(hint in query for hint in CHINESE_RULE_HINTS)
        wants_flows = bool(token_set & FLOW_HINTS) or any(hint in query for hint in CHINESE_FLOW_HINTS)
        return wants_rules, wants_flows

    def _section_matches_query(self, section: SectionInfo, query_norm: str, token_set: set[str]) -> bool:
        title_norm = normalize_name(section.title)
        full_title_norm = normalize_name(section.full_title)
        main_topics = [normalize_name(topic) for topic in section.meta.get("mainTopics", []) or []]
        exact_title = any(topic and topic in query_norm for topic in [title_norm, full_title_norm])
        exact_topic = any(topic and len(topic) >= 10 and (topic in token_set or topic in query_norm) for topic in main_topics)
        return exact_title or exact_topic

    def _implicit_route_filters(self, query_norm: str, query_tokens: list[str]) -> set[str]:
        token_set = set(query_tokens)
        routed: set[str] = set()
        for section in self.sections.values():
            if not self._section_matches_query(section, query_norm, token_set):
                continue
            if section.meta.get("contentTypes", {}).get("hasChunks"):
                continue
            for related in self._related_section_dirs(section):
                if related.meta.get("contentTypes", {}).get("hasChunks"):
                    routed.add(related.section_dir)
        return routed

    def _section_allowed(self, section_dir: str, section_filter_set: set[str]) -> bool:
        return not section_filter_set or section_dir in section_filter_set

    def _score_section_routes(
        self,
        query_norm: str,
        query_tokens: list[str],
        matches: dict[str, MatchContext],
        section_filter_set: set[str],
    ) -> None:
        for section in self.sections.values():
            if not self._section_allowed(section.section_dir, section_filter_set):
                continue
            if not self._section_matches_query(section, query_norm, set(query_tokens)):
                continue

            chunk_ids = [chunk.chunk_id for chunk in self.chunks.values() if chunk.section_dir == section.section_dir]
            if chunk_ids:
                for chunk_id in chunk_ids:
                    ctx = matches[chunk_id]
                    ctx.score += 4.0
                    ctx.reasons.append(f"section title match: {section.full_title}")
                continue

            for related in self._related_section_dirs(section):
                if not self._section_allowed(related.section_dir, section_filter_set):
                    continue
                for chunk in self.chunks.values():
                    if chunk.section_dir != related.section_dir:
                        continue
                    ctx = matches[chunk.chunk_id]
                    ctx.score += 2.5
                    ctx.reasons.append(
                        f"routed from empty section: {section.full_title} -> {related.full_title}"
                    )

    def _related_section_dirs(self, section: SectionInfo) -> list[SectionInfo]:
        labels = [
            *section.meta.get("relatedSections", []),
            *section.meta.get("dependsOn", []),
        ]
        related: list[SectionInfo] = []
        for label in labels:
            label_norm = normalize_name(str(label))
            if not label_norm:
                continue
            for candidate in self.sections.values():
                if candidate.section_dir == section.section_dir:
                    continue
                title_norm = normalize_name(candidate.title)
                full_title_norm = normalize_name(candidate.full_title)
                if label_norm == title_norm or label_norm in full_title_norm:
                    related.append(candidate)
        return related

    def _bm25(self, chunk: ChunkRecord, query_terms: list[str], k1: float = 1.5, b: float = 0.75) -> float:
        score = 0.0
        n_chunks = max(1, len(self.chunks))
        for term in query_terms:
            tf = chunk.tf.get(term, 0)
            if not tf:
                continue
            df = self.chunk_df.get(term, 0)
            idf = math.log(1 + (n_chunks - df + 0.5) / (df + 0.5))
            denom = tf + k1 * (1 - b + b * chunk.length / max(1.0, self.avg_chunk_len))
            score += idf * (tf * (k1 + 1) / denom)
        return score

    def _score_chunks(
        self,
        query_tokens: list[str],
        matches: dict[str, MatchContext],
        section_filter_set: set[str],
    ) -> None:
        for chunk in self.chunks.values():
            if not self._section_allowed(chunk.section_dir, section_filter_set):
                continue
            score = self._bm25(chunk, query_tokens)
            if score <= 0:
                continue
            ctx = matches[chunk.chunk_id]
            ctx.score += score
            overlap = sorted(set(query_tokens) & set(chunk.tokens))
            if overlap:
                ctx.reasons.append(f"chunk term overlap: {', '.join(overlap[:6])}")

    def _score_objects(
        self,
        query_tokens: list[str],
        query_norm: str,
        matches: dict[str, MatchContext],
        section_filter_set: set[str],
    ) -> None:
        candidates: dict[str, dict[str, Any]] = {}
        for term in query_tokens:
            for row in self.objects_by_term.get(term, []):
                candidates[row["objectId"]] = row
        for row in self.objects_by_name.get(query_norm, []):
            candidates[row["objectId"]] = row

        exact_names = {normalize_name(token) for token in query_tokens}
        if query_norm:
            exact_names.add(query_norm)

        for row in candidates.values():
            if not self._section_allowed(row["_section_dir"], section_filter_set):
                continue
            name_norm = normalize_name(row.get("name", ""))
            overlap = set(query_tokens) & set(tokenize(row["_search_blob"]))
            score = float(len(overlap)) * 1.5
            if name_norm in exact_names:
                score += 8.0
            if row.get("transactionClass") and normalize_name(str(row["transactionClass"])) in exact_names:
                score += 2.0
            if score <= 0:
                continue
            for chunk_id in row.get("sourceChunks", []) or []:
                ctx = matches[chunk_id]
                ctx.score += score
                ctx.objects.append(f"{row.get('name')} ({row.get('objectType')})")
                ctx.reasons.append(f"object match: {row.get('name')}")

    def _score_rules(
        self,
        query_tokens: list[str],
        query_norm: str,
        matches: dict[str, MatchContext],
        section_filter_set: set[str],
        wants_rules: bool,
    ) -> None:
        candidates: dict[str, dict[str, Any]] = {}
        for term in query_tokens:
            for row in self.rules_by_term.get(term, []):
                candidates[row["ruleId"]] = row

        for row in candidates.values():
            if not self._section_allowed(row["_section_dir"], section_filter_set):
                continue
            row_tokens = set(tokenize(row["_search_blob"]))
            overlap = set(query_tokens) & row_tokens
            if not overlap:
                continue
            score = float(len(overlap)) * 1.8
            if wants_rules:
                score += 2.5
            title_norm = normalize_name(row.get("title", ""))
            if query_norm and query_norm in title_norm:
                score += 2.0
            for chunk_id in row.get("sourceChunks", []) or []:
                ctx = matches[chunk_id]
                ctx.score += score
                rule_text = row.get("requirement") or row.get("title") or row.get("ruleId")
                ctx.rules.append(shorten(rule_text, 120))
                ctx.reasons.append(f"rule match: {shorten(row.get('title') or row.get('ruleId'), 80)}")

    def _score_flows(
        self,
        query_tokens: list[str],
        query_norm: str,
        matches: dict[str, MatchContext],
        section_filter_set: set[str],
        wants_flows: bool,
    ) -> None:
        candidates: dict[str, dict[str, Any]] = {}
        for term in query_tokens:
            for row in self.flows_by_term.get(term, []):
                candidates[row["flowId"]] = row

        for row in candidates.values():
            if not self._section_allowed(row["_section_dir"], section_filter_set):
                continue
            row_tokens = set(tokenize(row["_search_blob"]))
            overlap = set(query_tokens) & row_tokens
            if not overlap:
                continue
            score = float(len(overlap)) * 1.6
            if wants_flows:
                score += 3.0
            name_norm = normalize_name(row.get("name", ""))
            if query_norm and query_norm in name_norm:
                score += 1.5
            for chunk_id in row.get("sourceChunks", []) or []:
                ctx = matches[chunk_id]
                ctx.score += score
                ctx.flows.append(f"{row.get('name')} -> {', '.join((row.get('appliesTo') or [])[:6])}")
                ctx.reasons.append(f"flow match: {row.get('name')}")

    def _score_verification(
        self,
        query_tokens: list[str],
        matches: dict[str, MatchContext],
        section_filter_set: set[str],
        wants_rules: bool,
        wants_flows: bool,
    ) -> None:
        candidates: dict[str, dict[str, Any]] = {}
        for term in query_tokens:
            for row in self.verification_by_term.get(term, []):
                candidates[row["verificationId"]] = row

        for row in candidates.values():
            if not self._section_allowed(row["_section_dir"], section_filter_set):
                continue
            overlap = set(query_tokens) & set(tokenize(row["_search_blob"]))
            if not overlap:
                continue
            score = float(len(overlap)) * 0.8
            if wants_rules and row.get("relatedRules"):
                score += 1.0
            if wants_flows and row.get("method") == "cover":
                score += 0.5
            for chunk_id in row.get("sourceChunks", []) or []:
                ctx = matches[chunk_id]
                ctx.score += score
                ctx.verification.append(f"{row.get('method')}: {shorten(row.get('title', ''), 90)}")
                ctx.reasons.append(f"verification hint: {row.get('method')}")

    def _expand_relations(
        self,
        matches: dict[str, MatchContext],
        section_filter_set: set[str],
    ) -> None:
        relation_hits: list[tuple[str, dict[str, Any]]] = []
        for ctx in matches.values():
            for obj in ctx.objects:
                key = normalize_name(obj.split(" (", 1)[0])
                for relation in self.relations_by_name.get(key, []):
                    relation_hits.append((key, relation))

        for key, relation in relation_hits:
            section_dir = relation.get("_section_dir")
            if section_dir and not self._section_allowed(section_dir, section_filter_set):
                continue
            relation_type = relation.get("relationType") or "related"
            for chunk_id in relation.get("sourceChunks", []) or []:
                ctx = matches[chunk_id]
                ctx.score += 0.35
                ctx.reasons.append(
                    f"relation expansion: {relation.get('from')} {relation_type} {relation.get('to')}"
                )

    def list_sections(self) -> list[dict[str, Any]]:
        rows = []
        for section in sorted(self.sections.values(), key=lambda item: item.pdf_id):
            rows.append(
                {
                    "section_dir": section.section_dir,
                    "section": section.pdf_id,
                    "title": section.title,
                    "full_title": section.full_title,
                    "content_types": section.meta.get("contentTypes", {}),
                }
            )
        return rows


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search CHI section knowledge files with chunk retrieval plus structured boosts."
    )
    parser.add_argument("query", nargs="?", help="Search query.")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json-dir", type=Path, default=None, help="Knowledge directory. Default: <project>/kb/sections")
    parser.add_argument(
        "--docs-path",
        type=Path,
        default=None,
        help="Optional document index path. Default: <project>/kb/docs/chi_docs.json",
    )
    parser.add_argument("--top-k", type=int, default=5, help="How many results to return.")
    parser.add_argument(
        "--section",
        action="append",
        default=[],
        help="Filter by section id, title, or full title. Repeatable.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--list-sections", action="store_true", help="List searchable sections and exit.")
    return parser


def print_text_results(results: list[dict[str, Any]]) -> None:
    if not results:
        print("No results.")
        return

    for idx, result in enumerate(results, start=1):
        print(f"[{idx}] {result['title']}  score={result['score']:.3f}")
        print(f"chunk: {result['chunk_id']}")
        if result.get("subsection"):
            print(f"subsection: {result['subsection']}")
        print(f"source: {result['source_file']}")
        print(f"snippet: {result['snippet']}")
        if result["matched_objects"]:
            print(f"objects: {', '.join(result['matched_objects'][:4])}")
        if result["matched_rules"]:
            print(f"rules: {', '.join(result['matched_rules'][:3])}")
        if result["matched_flows"]:
            print(f"flows: {', '.join(result['matched_flows'][:2])}")
        if result["matched_verification"]:
            print(f"verification: {', '.join(result['matched_verification'][:2])}")
        print(f"reasons: {', '.join(result['reasons'][:4])}")
        print()


def main() -> None:
    args = build_arg_parser().parse_args()
    project_root = args.project_root.resolve()
    json_dir = args.json_dir.resolve() if args.json_dir else (project_root / "kb" / "sections")
    docs_path = args.docs_path.resolve() if args.docs_path else (project_root / "kb" / "docs" / "chi_docs.json")

    retriever = ChiRetriever(project_root=project_root, json_dir=json_dir, docs_path=docs_path)

    if args.list_sections:
        payload = retriever.list_sections()
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            for row in payload:
                print(f"{row['section']}\t{row['full_title']}")
        return

    if not args.query:
        raise SystemExit("query is required unless --list-sections is used")

    results = retriever.search(query=args.query, top_k=max(1, args.top_k), section_filters=args.section)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print_text_results(results)


if __name__ == "__main__":
    main()
