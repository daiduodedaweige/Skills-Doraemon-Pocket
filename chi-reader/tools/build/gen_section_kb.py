from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


SECTION_RE = re.compile(r"^([A-Z]\d+(?:\.\d+)+)\s+(.+)$")
SUBSECTION_RE = re.compile(r"^([A-Z]\d+(?:\.\d+)+(?:\.\d+)*)\.?\s+(.+)$")
MULTI_SPACE_RE = re.compile(r"[ \t]+")
CAMEL_CASE_RE = re.compile(r"\b(?:[A-Z][a-z0-9]+){2,}[A-Za-z0-9]*\b")
ALL_CAPS_TERM_RE = re.compile(r"\b[A-Z]{2,}(?:[-/][A-Z]{1,})?\b")
TABLE_RE = re.compile(r"^Table\s+([A-Z]\d+(?:\.\d+)*)[:\-]?\s*(.*)$")
FIGURE_RE = re.compile(r"^Figure\s+([A-Z]\d+(?:\.\d+)*)[:\-]?\s*(.*)$")

TARGET_CHARS = 1200
OVERLAP_CHARS = 180

STOPWORDS = {
	"A",
	"An",
	"And",
	"Architecture",
	"Cache",
	"Chapter",
	"CHI",
	"Continued",
	"Data",
	"Figure",
	"Flow",
	"For",
	"From",
	"Home",
	"If",
	"In",
	"Introduction",
	"Issue",
	"Layer",
	"Link",
	"Memory",
	"Message",
	"Messages",
	"Network",
	"Node",
	"Nodes",
	"Note",
	"Overview",
	"Packet",
	"Packets",
	"Permitted",
	"Protocol",
	"Read",
	"Request",
	"Requests",
	"Requester",
	"Response",
	"Responses",
	"Section",
	"Table",
	"Tag",
	"The",
	"To",
	"Transaction",
	"Transactions",
	"With",
}

CHANNELS = {"REQ", "RSP", "SNP", "DAT"}
FIELDS = {
	"Addr",
	"AllowRetry",
	"DBID",
	"DataID",
	"DataSource",
	"DataTarget",
	"Device",
	"DoDWT",
	"Endian",
	"LPID",
	"MemAttr",
	"MPAM",
	"MEC",
	"Opcode",
	"Order",
	"PAS",
	"PGroupID",
	"PCrdType",
	"QoS",
	"Resp",
	"RespErr",
	"ReturnNID",
	"ReturnTxnID",
	"Size",
	"SrcID",
	"StashLPID",
	"Tag",
	"TagOp",
	"TraceTag",
	"TxnID",
	"TgtID",
	"TU",
}
RESPONSES = {
	"Comp",
	"CompAck",
	"CompDBIDResp",
	"CompData",
	"DBIDResp",
	"Persist",
	"ReadReceipt",
	"RespSepData",
	"RetryAck",
	"SnpResp",
	"SnpRespData",
	"SnpRespDataPtl",
}
STATES = {
	"Clean",
	"Dirty",
	"I",
	"Invalid",
	"SC",
	"SD",
	"Shared",
	"UC",
	"UCE",
	"UD",
	"UDP",
	"Unique",
}
NODE_TYPES = {
	"HN",
	"Home",
	"MN",
	"Requester",
	"RN",
	"RNF",
	"RND",
	"SN",
	"Snoopee",
	"Subordinate",
}
OPCODE_HINTS = {
	"AtomicCompare",
	"AtomicLoad",
	"AtomicStore",
	"AtomicSwap",
	"CleanInvalid",
	"CleanInvalidPoPA",
	"CleanInvalidStorage",
	"CleanShared",
	"CleanSharedPersist",
	"CleanSharedPersistSep",
	"CleanUnique",
	"DVMOp",
	"Evict",
	"MakeInvalid",
	"MakeReadUnique",
	"MakeUnique",
	"PCrdReturn",
	"PrefetchTgt",
	"ReadClean",
	"ReadNoSnp",
	"ReadNoSnpSep",
	"ReadNotSharedDirty",
	"ReadOnce",
	"ReadOnceCleanInvalid",
	"ReadOnceMakeInvalid",
	"ReadPreferUnique",
	"ReadShared",
	"ReadUnique",
	"ReqLCrdReturn",
	"StashOnceSepShared",
	"StashOnceSepUnique",
	"StashOnceShared",
	"StashOnceUnique",
	"WriteBackFull",
	"WriteBackFullCleanInv",
	"WriteBackFullCleanInvPoPA",
	"WriteBackFullCleanInvStrg",
	"WriteBackFullCleanSh",
	"WriteBackFullCleanShPerSep",
	"WriteBackPtl",
	"WriteCleanFull",
	"WriteCleanFullCleanSh",
	"WriteCleanFullCleanShPerSep",
	"WriteEvictFull",
	"WriteEvictOrEvict",
	"WriteNoSnpDef",
	"WriteNoSnpFull",
	"WriteNoSnpFullCleanInv",
	"WriteNoSnpFullCleanInvPoPA",
	"WriteNoSnpFullCleanInvStrg",
	"WriteNoSnpFullCleanSh",
	"WriteNoSnpFullCleanShPerSep",
	"WriteNoSnpPtl",
	"WriteNoSnpPtlCleanInv",
	"WriteNoSnpPtlCleanInvPoPA",
	"WriteNoSnpPtlCleanSh",
	"WriteNoSnpPtlCleanShPerSep",
	"WriteNoSnpZero",
	"WriteUniqueFull",
	"WriteUniqueFullCleanInvStrg",
	"WriteUniqueFullCleanSh",
	"WriteUniqueFullCleanShPerSep",
	"WriteUniqueFullStash",
	"WriteUniquePtl",
	"WriteUniquePtlCleanSh",
	"WriteUniquePtlCleanShPerSep",
	"WriteUniquePtlStash",
	"WriteUniqueZero",
}

POSITIVE_RULE_MARKERS = (
	" must ",
	" must be ",
	" shall ",
	" shall be ",
	" is required ",
	" are required ",
	" required that",
	" needs to ",
)
NEGATIVE_RULE_MARKERS = (
	" must not ",
	" shall not ",
	" cannot ",
	" can not ",
	" never ",
	" avoid ",
	" prohibited ",
	" not permitted ",
)
PERMISSION_RULE_MARKERS = (
	" permitted ",
	" allowed ",
	" may ",
	" can be returned",
	" are permitted",
	" is permitted",
)


@dataclass
class Paragraph:
	text: str
	subsection: str
	source_type: str


def parse_filename(stem: str) -> tuple[str, str, str]:
	match = SECTION_RE.match(stem.strip())
	if not match:
		return "", stem.strip(), stem.strip()
	section_id = match.group(1)
	title = match.group(2).strip()
	return section_id, title, f"{section_id} {title}".strip()


def slugify(value: str) -> str:
	cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value.strip())
	return cleaned.strip("_") or "item"


def is_noise_line(line: str) -> bool:
	stripped = line.strip()
	if not stripped:
		return True
	if re.fullmatch(r"\d+", stripped):
		return True
	if re.fullmatch(r"ARM IHI 0050[A-Za-z. ]*", stripped):
		return True
	if re.fullmatch(r"[\-_=]{3,}", stripped):
		return True
	return False


def normalize_line(line: str) -> str:
	stripped = line.strip()
	if not stripped:
		return ""
	return MULTI_SPACE_RE.sub(" ", stripped)


def normalize_text(raw: str) -> str:
	lines: list[str] = []
	blank_seen = False
	for line in raw.splitlines():
		if is_noise_line(line):
			if not blank_seen:
				lines.append("")
			blank_seen = True
			continue
		blank_seen = False
		lines.append(normalize_line(line))
	text = "\n".join(lines)
	text = re.sub(r"\n{3,}", "\n\n", text)
	return text.strip()


def classify_source_type(text: str) -> str:
	if TABLE_RE.match(text):
		return "table"
	if FIGURE_RE.match(text):
		return "figure"
	if text.startswith("Note"):
		return "note"
	return "paragraph"


def build_paragraphs(text: str) -> list[Paragraph]:
	paragraphs: list[Paragraph] = []
	current_subsection = ""
	for block in re.split(r"\n\s*\n", text):
		paragraph = block.strip()
		if not paragraph:
			continue
		lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
		if not lines:
			continue
		heading_match = SUBSECTION_RE.match(lines[0])
		if heading_match:
			current_subsection = f"{heading_match.group(1)} {heading_match.group(2).strip()}".strip()
		paragraphs.append(
			Paragraph(
				text="\n".join(lines),
				subsection=current_subsection,
				source_type=classify_source_type(lines[0]),
			)
		)
	return paragraphs


def split_chunks(section_id: str, paragraphs: list[Paragraph]) -> list[dict]:
	chunks: list[dict] = []
	current_parts: list[Paragraph] = []
	current_len = 0

	def flush() -> None:
		nonlocal current_parts, current_len
		if not current_parts:
			return
		text = "\n\n".join(part.text for part in current_parts).strip()
		if not text:
			current_parts = []
			current_len = 0
			return
		chunk_index = len(chunks) + 1
		chunk_id = f"{slugify(section_id)}_C{chunk_index:03d}"
		subsection = next((part.subsection for part in current_parts if part.subsection), "")
		source_type = current_parts[0].source_type if len({part.source_type for part in current_parts}) == 1 else "mixed"
		chunks.append(
			{
				"chunkId": chunk_id,
				"pageStart": None,
				"pageEnd": None,
				"section": section_id,
				"subsection": subsection or None,
				"text": text,
				"sourceType": source_type,
			}
		)

		if len(text) > OVERLAP_CHARS:
			overlap = text[-OVERLAP_CHARS:].strip()
			current_parts = [Paragraph(text=overlap, subsection=subsection, source_type="paragraph")]
			current_len = len(overlap)
		else:
			current_parts = []
			current_len = 0

	for paragraph in paragraphs:
		length = len(paragraph.text)
		if length > TARGET_CHARS:
			flush()
			pieces = [paragraph.text[i : i + TARGET_CHARS] for i in range(0, length, TARGET_CHARS - OVERLAP_CHARS)]
			for piece in pieces:
				piece_text = piece.strip()
				if not piece_text:
					continue
				chunk_id = f"{slugify(section_id)}_C{len(chunks) + 1:03d}"
				chunks.append(
					{
						"chunkId": chunk_id,
						"pageStart": None,
						"pageEnd": None,
						"section": section_id,
						"subsection": paragraph.subsection or None,
						"text": piece_text,
						"sourceType": paragraph.source_type,
					}
				)
			continue

		extra = 2 if current_parts else 0
		if current_len + extra + length <= TARGET_CHARS:
			current_parts.append(paragraph)
			current_len += extra + length
		else:
			flush()
			current_parts.append(paragraph)
			current_len = length

	flush()
	return chunks


def tokenize_title(title: str) -> list[str]:
	parts = re.split(r"[^A-Za-z0-9]+", title)
	return [part for part in parts if part and part not in STOPWORDS]


def detect_terms(text: str, title: str) -> list[str]:
	terms: set[str] = set()
	for token in CAMEL_CASE_RE.findall(f"{title} {text}"):
		if token not in STOPWORDS and len(token) > 2:
			terms.add(token)
	for token in ALL_CAPS_TERM_RE.findall(f"{title} {text}"):
		if token not in STOPWORDS and len(token) > 1:
			terms.add(token)
	for token in tokenize_title(title):
		if token in OPCODE_HINTS or token in RESPONSES or token in FIELDS or token in CHANNELS:
			terms.add(token)
	return sorted(terms)


def infer_transaction_class(term: str, title: str, section_id: str) -> str | None:
	name = f"{term} {title} {section_id}"
	if "Read" in name:
		return "Read"
	if "Write" in name:
		return "Write"
	if "Snoop" in name or "Snp" in name:
		return "Snoop"
	if "Atomic" in name:
		return "Atomic"
	if "Stash" in name:
		return "Stash"
	if "DVM" in name:
		return "DVM"
	return None


def infer_object_type(term: str, section_id: str, title: str) -> str:
	if term in CHANNELS:
		return "Channel"
	if term in FIELDS:
		return "Field"
	if term in RESPONSES:
		return "Response"
	if term in STATES:
		return "State"
	if term in NODE_TYPES:
		return "NodeType"
	if section_id.startswith("C4") or term in OPCODE_HINTS:
		return "Opcode"
	if "field" in title.lower():
		return "Field"
	if "response" in title.lower():
		return "Response"
	if "channel" in title.lower():
		return "Channel"
	if "state" in title.lower():
		return "State"
	return "Concept"


def find_context_sentence(text: str, term: str) -> str:
	for sentence in split_sentences(text):
		if term in sentence:
			return sentence
	return ""


def split_sentences(text: str) -> list[str]:
	lines: list[str] = []
	for raw_line in text.splitlines():
		line = raw_line.strip()
		if not line:
			continue
		if line.startswith(("•", "-", "*", "–")):
			lines.append(line.lstrip("•-*– "))
		else:
			lines.append(line)

	sentences: list[str] = []
	for line in lines:
		parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", line)
		for part in parts:
			cleaned = part.strip(" -")
			if len(cleaned) >= 20:
				sentences.append(cleaned)
	return sentences


def top_keywords(text: str, title: str, limit: int = 8) -> list[str]:
	counter: Counter[str] = Counter()
	for term in detect_terms(text, title):
		counter[term] += 3
	for token in tokenize_title(title):
		counter[token] += 2
	for word in re.findall(r"\b[A-Za-z][A-Za-z0-9_-]{2,}\b", text):
		if word in STOPWORDS or word.lower() in {"the", "and", "with", "that", "from", "into"}:
			continue
		if word[0].isupper() or word in CHANNELS or word in FIELDS:
			counter[word] += 1
	return [item for item, _ in counter.most_common(limit)]


def derive_topics(title: str, keywords: list[str]) -> list[str]:
	topics: list[str] = []
	for token in tokenize_title(title):
		if token not in topics:
			topics.append(token)
	for keyword in keywords:
		if keyword not in topics:
			topics.append(keyword)
		if len(topics) >= 8:
			break
	return topics


def extract_objects(section_id: str, title: str, text: str, chunks: list[dict]) -> list[dict]:
	terms = detect_terms(text, title)
	primary_term = title.strip().split()[0] if title.strip() else ""
	if primary_term and primary_term not in terms and (section_id.startswith("C4") or primary_term in OPCODE_HINTS):
		terms.insert(0, primary_term)
	objects: list[dict] = []
	seen: set[str] = set()
	for term in terms:
		object_type = infer_object_type(term, section_id, title)
		object_id = f"{slugify(section_id)}_{slugify(object_type)}_{slugify(term)}"
		if object_id in seen:
			continue
		seen.add(object_id)
		context = find_context_sentence(text, term)
		related = [other for other in terms if other != term and other in context][:6]
		source_chunks = [chunk["chunkId"] for chunk in chunks if term in chunk["text"]][:3]
		properties: dict[str, object] = {}
		transaction_class = infer_transaction_class(term, title, section_id)
		if term in CHANNELS:
			properties["role"] = "CHI channel"
		if transaction_class:
			properties["transactionClass"] = transaction_class
		if term in RESPONSES:
			properties["messageKind"] = "completion-or-response"
		if term in FIELDS:
			properties["fieldKind"] = "protocol-field"
		if term in STATES:
			properties["stateKind"] = "cache-state"
		objects.append(
			{
				"objectId": object_id,
				"pdfId": section_id,
				"objectType": object_type,
				"name": term,
				"channel": term if term in CHANNELS else None,
				"transactionClass": transaction_class,
				"description": context or f"Mentioned in {title}.",
				"properties": properties,
				"validValues": None,
				"relatedObjects": related,
				"sourceChunks": source_chunks,
				"confidence": "medium" if context else "low",
				"notes": None,
			}
		)
		if len(objects) >= 20:
			break
	return objects


def infer_rule_type(sentence: str) -> str:
	lower = f" {sentence.lower()} "
	if "txn" in lower or " id" in lower:
		return "IDMatching"
	if "state" in lower or any(state.lower() in lower for state in STATES):
		return "State"
	if "order" in lower:
		return "Ordering"
	if "credit" in lower or "retry" in lower:
		return "FlowControl"
	if "response" in lower or "completion" in lower or "compdata" in lower:
		return "Completion"
	return "ProtocolRule"


def sentence_markers(sentence: str) -> tuple[str | None, str]:
	lower = f" {sentence.lower()} "
	for marker in NEGATIVE_RULE_MARKERS:
		if marker in lower:
			return "negative", marker.strip()
	for marker in POSITIVE_RULE_MARKERS:
		if marker in lower:
			return "positive", marker.strip()
	for marker in PERMISSION_RULE_MARKERS:
		if marker in lower:
			return "permission", marker.strip()
	return None, ""


def extract_rules(section_id: str, title: str, text: str, chunks: list[dict], objects: list[dict]) -> list[dict]:
	object_names = [obj["name"] for obj in objects]
	rules: list[dict] = []
	for sentence in split_sentences(text):
		kind, marker = sentence_markers(sentence)
		if not kind:
			continue
		related = [name for name in object_names if name in sentence][:8]
		source_chunks = [chunk["chunkId"] for chunk in chunks if sentence[:40] in chunk["text"] or sentence in chunk["text"]][:3]
		if not source_chunks:
			source_chunks = [chunk["chunkId"] for chunk in chunks if any(name in chunk["text"] for name in related)][:2]
		rule_index = len(rules) + 1
		rule_id = f"{slugify(section_id)}_rule_{rule_index:03d}"
		requirement = sentence if kind in {"positive", "permission"} else ""
		forbidden = [sentence] if kind == "negative" else []
		verification_use = ["assert"]
		if kind == "permission":
			verification_use = ["cover", "scoreboard"]
		elif infer_rule_type(sentence) in {"Completion", "IDMatching"}:
			verification_use = ["assert", "scoreboard"]
		rules.append(
			{
				"ruleId": rule_id,
				"pdfId": section_id,
				"ruleType": infer_rule_type(sentence),
				"title": sentence[:100],
				"appliesTo": related or ([title.split()[0]] if title.split() else []),
				"condition": sentence if sentence.startswith(("When", "If", "For ", "In the case")) else "",
				"requirement": requirement,
				"forbidden": forbidden,
				"exceptions": [],
				"relatedObjects": related,
				"verificationUse": verification_use,
				"sourceChunks": source_chunks,
				"confidence": "medium",
				"needsCrossCheck": kind == "permission" and "or" in sentence,
				"crossCheckTopics": [marker] if marker else [],
			}
		)
		if len(rules) >= 25:
			break
	return rules


def extract_tables(section_id: str, text: str, chunks: list[dict]) -> list[dict]:
	tables: list[dict] = []
	lines = [line.strip() for line in text.splitlines() if line.strip()]
	for index, line in enumerate(lines):
		match = TABLE_RE.match(line)
		if not match:
			continue
		title = match.group(2).strip() or match.group(1)
		related_chunk = next((chunk["chunkId"] for chunk in chunks if line in chunk["text"]), None)
		tables.append(
			{
				"tableId": f"{slugify(section_id)}_table_{len(tables) + 1:03d}",
				"pdfId": section_id,
				"label": match.group(1),
				"title": title,
				"sourceChunks": [related_chunk] if related_chunk else [],
				"rawHeader": lines[index + 1] if index + 1 < len(lines) else "",
			}
		)
	return tables


def extract_figures(section_id: str, text: str, chunks: list[dict]) -> list[dict]:
	figures: list[dict] = []
	for line in [line.strip() for line in text.splitlines() if line.strip()]:
		match = FIGURE_RE.match(line)
		if not match:
			continue
		related_chunk = next((chunk["chunkId"] for chunk in chunks if line in chunk["text"]), None)
		figures.append(
			{
				"figureId": f"{slugify(section_id)}_figure_{len(figures) + 1:03d}",
				"pdfId": section_id,
				"label": match.group(1),
				"title": match.group(2).strip() or match.group(1),
				"sourceChunks": [related_chunk] if related_chunk else [],
			}
		)
	return figures


def extract_flows(section_id: str, title: str, text: str, chunks: list[dict], objects: list[dict], rules: list[dict]) -> list[dict]:
	is_flow_section = any(keyword in title.lower() for keyword in ("flow", "transaction", "handshake", "sequence")) or section_id.startswith("B5")
	if not is_flow_section:
		return []

	participants = [obj["name"] for obj in objects if obj["objectType"] in {"NodeType", "Channel", "Opcode", "Response"}][:6]
	steps: list[dict] = []
	for sentence in split_sentences(text):
		lower = sentence.lower()
		if not any(keyword in lower for keyword in ("issue", "send", "return", "respond", "receive", "transfer", "complete")):
			continue
		step_index = len(steps) + 1
		steps.append(
			{
				"step": step_index,
				"from": "Requester" if "request" in lower or "issue" in lower else None,
				"to": "Completer" if "response" in lower or "return" in lower else None,
				"channel": next((channel for channel in CHANNELS if channel in sentence), None),
				"message": next((obj["name"] for obj in objects if obj["name"] in sentence and obj["objectType"] in {"Opcode", "Response"}), title),
				"condition": sentence,
			}
		)
		if len(steps) >= 6:
			break

	if not steps:
		return []

	return [
		{
			"flowId": f"{slugify(section_id)}_flow_001",
			"pdfId": section_id,
			"name": title,
			"flowType": "TransactionFlow" if "transaction" in title.lower() or section_id.startswith("B5") else "ProtocolFlow",
			"appliesTo": [obj["name"] for obj in objects if obj["objectType"] == "Opcode"][:6] or [title],
			"participants": participants,
			"steps": steps,
			"completionCondition": rules[0]["title"] if rules else "Flow completes when the permitted message sequence is observed.",
			"possibleVariants": [],
			"relatedRules": [rule["ruleId"] for rule in rules[:6]],
			"sourceChunks": [chunk["chunkId"] for chunk in chunks[:3]],
			"confidence": "medium",
		}
	]


def extract_verification(section_id: str, title: str, rules: list[dict], flows: list[dict]) -> list[dict]:
	verification: list[dict] = []
	for rule in rules:
		method = rule["verificationUse"][0] if rule["verificationUse"] else "assert"
		verification.append(
			{
				"verificationId": f"{slugify(section_id)}_vp_{len(verification) + 1:03d}",
				"pdfId": section_id,
				"title": rule["title"],
				"objective": rule["requirement"] or (rule["forbidden"][0] if rule["forbidden"] else rule["title"]),
				"method": method,
				"stimulus": rule["condition"] or f"Exercise {title} under the documented preconditions.",
				"expectedBehavior": rule["requirement"] or (rule["forbidden"][0] if rule["forbidden"] else rule["title"]),
				"relatedRules": [rule["ruleId"]],
				"relatedObjects": rule["relatedObjects"],
				"sourceChunks": rule["sourceChunks"],
			}
		)
		if len(verification) >= 25:
			break
	for flow in flows:
		verification.append(
			{
				"verificationId": f"{slugify(section_id)}_vp_{len(verification) + 1:03d}",
				"pdfId": section_id,
				"title": f"Cover {flow['name']}",
				"objective": "Cover the representative protocol flow extracted from the section.",
				"method": "cover",
				"stimulus": f"Generate a scenario that exercises {flow['name']}.",
				"expectedBehavior": flow["completionCondition"],
				"relatedRules": flow["relatedRules"],
				"relatedObjects": flow["appliesTo"],
				"sourceChunks": flow["sourceChunks"],
			}
		)
	return verification


def extract_relations(section_id: str, objects: list[dict], rules: list[dict], flows: list[dict], verification: list[dict]) -> list[dict]:
	relations: list[dict] = []
	for obj in objects:
		for related in obj["relatedObjects"]:
			relations.append(
				{
					"relationId": f"{slugify(section_id)}_rel_{len(relations) + 1:03d}",
					"pdfId": section_id,
					"from": obj["name"],
					"to": related,
					"relationType": "co-mentioned",
					"sourceChunks": obj["sourceChunks"],
				}
			)
	for rule in rules:
		for related in rule["relatedObjects"]:
			relations.append(
				{
					"relationId": f"{slugify(section_id)}_rel_{len(relations) + 1:03d}",
					"pdfId": section_id,
					"from": rule["ruleId"],
					"to": related,
					"relationType": "applies-to",
					"sourceChunks": rule["sourceChunks"],
				}
			)
	for flow in flows:
		for rule_id in flow["relatedRules"]:
			relations.append(
				{
					"relationId": f"{slugify(section_id)}_rel_{len(relations) + 1:03d}",
					"pdfId": section_id,
					"from": flow["flowId"],
					"to": rule_id,
					"relationType": "governed-by",
					"sourceChunks": flow["sourceChunks"],
				}
			)
	for point in verification:
		for rule_id in point["relatedRules"]:
			relations.append(
				{
					"relationId": f"{slugify(section_id)}_rel_{len(relations) + 1:03d}",
					"pdfId": section_id,
					"from": point["verificationId"],
					"to": rule_id,
					"relationType": "verifies",
					"sourceChunks": point["sourceChunks"],
				}
			)
	return relations


def derive_depends_on(objects: list[dict], title: str) -> list[str]:
	depends_on: list[str] = []
	object_types = {obj["objectType"] for obj in objects}
	if "Field" in object_types:
		depends_on.append("Channel fields")
	if "Channel" in object_types:
		depends_on.append("Channel semantics")
	if "State" in object_types or "state" in title.lower():
		depends_on.append("Cache state rules")
	if any(obj["objectType"] == "Opcode" for obj in objects):
		depends_on.append("Transaction flows")
	if any(obj["name"] in {"TxnID", "DBID", "ReturnTxnID"} for obj in objects):
		depends_on.append("Outstanding transaction tracking")
	return depends_on


def derive_related_sections(section_id: str, title: str, objects: list[dict]) -> list[str]:
	related: list[str] = []
	transaction_classes = {obj["transactionClass"] for obj in objects if obj["transactionClass"]}
	if "Read" in transaction_classes or "read" in title.lower():
		related.extend(["Request types", "Read transaction flows"])
	if "Write" in transaction_classes or "write" in title.lower():
		related.extend(["Request types", "Write transaction flows"])
	if "Snoop" in transaction_classes or "snoop" in title.lower():
		related.extend(["Snoop request types", "Response types"])
	if "field" in title.lower():
		related.append("Message field mappings")
	if section_id.startswith("B13") or section_id.startswith("B14"):
		related.append("Link layer signaling")
	unique_related: list[str] = []
	for item in related:
		if item not in unique_related:
			unique_related.append(item)
	return unique_related


def write_json(path: Path, payload: object) -> None:
	path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
	with path.open("w", encoding="utf-8") as handle:
		for row in rows:
			handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_meta(section_id: str, title: str, source_file: str, keywords: list[str], objects: list[dict], chunks: list[dict], rules: list[dict], flows: list[dict], verification: list[dict], tables: list[dict], figures: list[dict], has_source: bool) -> dict:
	quality = "generated-from-markdown" if has_source else "empty-source"
	notes = "Generated from extracted markdown with heuristic structure." if has_source else "Source markdown is empty; only metadata and empty record files were generated."
	return {
		"pdfId": section_id,
		"sourceFile": source_file,
		"title": title,
		"chiVersion": "IHI0050H",
		"pageStart": None,
		"pageEnd": None,
		"mainTopics": derive_topics(title, keywords),
		"contentTypes": {
			"hasChunks": bool(chunks),
			"hasObjects": bool(objects),
			"hasRules": bool(rules),
			"hasFlows": bool(flows),
			"hasVerificationPoints": bool(verification),
			"hasTables": bool(tables),
			"hasFigures": bool(figures),
		},
		"dependsOn": derive_depends_on(objects, title),
		"relatedSections": derive_related_sections(section_id, title, objects),
		"processingStatus": {
			"extracted": has_source,
			"reviewed": False,
			"quality": quality,
			"notes": notes,
		},
		"recordStats": {
			"chunks": len(chunks),
			"objects": len(objects),
			"rules": len(rules),
			"flows": len(flows),
			"verification": len(verification),
			"relations": 0,
			"tables": len(tables),
			"figures": len(figures),
		},
	}


def enrich_chunks(chunks: list[dict], title: str) -> None:
	for chunk in chunks:
		keywords = top_keywords(chunk["text"], title, limit=8)
		chunk["topics"] = derive_topics(title, keywords)[:6]
		chunk["keywords"] = keywords
		chunk["confidence"] = "medium" if len(chunk["text"]) >= 200 else "low"


def build_section(md_path: Path, target_root: Path) -> dict:
	section_id, title, _ = parse_filename(md_path.stem)
	normalized = normalize_text(md_path.read_text(encoding="utf-8", errors="ignore"))
	has_source = bool(normalized)
	paragraphs = build_paragraphs(normalized) if has_source else []
	chunks = split_chunks(section_id, paragraphs) if has_source else []
	enrich_chunks(chunks, title)
	objects = extract_objects(section_id, title, normalized, chunks) if has_source else []
	rules = extract_rules(section_id, title, normalized, chunks, objects) if has_source else []
	tables = extract_tables(section_id, normalized, chunks) if has_source else []
	figures = extract_figures(section_id, normalized, chunks) if has_source else []
	flows = extract_flows(section_id, title, normalized, chunks, objects, rules) if has_source else []
	verification = extract_verification(section_id, title, rules, flows) if has_source else []
	relations = extract_relations(section_id, objects, rules, flows, verification) if has_source else []
	keywords = top_keywords(normalized, title, limit=10) if has_source else tokenize_title(title)
	meta = build_meta(
		section_id=section_id,
		title=title,
		source_file=md_path.name,
		keywords=keywords,
		objects=objects,
		chunks=chunks,
		rules=rules,
		flows=flows,
		verification=verification,
		tables=tables,
		figures=figures,
		has_source=has_source,
	)
	meta["recordStats"]["relations"] = len(relations)

	target_dir = target_root / md_path.stem
	target_dir.mkdir(parents=True, exist_ok=True)
	write_json(target_dir / "meta.json", meta)
	write_jsonl(target_dir / "chunks.jsonl", chunks)
	write_jsonl(target_dir / "objects.jsonl", objects)
	write_jsonl(target_dir / "rules.jsonl", rules)
	write_jsonl(target_dir / "flows.jsonl", flows)
	write_jsonl(target_dir / "verification.jsonl", verification)
	write_jsonl(target_dir / "relations.jsonl", relations)
	write_jsonl(target_dir / "tables.jsonl", tables)
	write_jsonl(target_dir / "figures.jsonl", figures)

	return {
		"sectionId": section_id,
		"title": title,
		"hasSource": has_source,
		"chunks": len(chunks),
		"objects": len(objects),
		"rules": len(rules),
		"flows": len(flows),
		"verification": len(verification),
	}


def build_arg_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Populate per-section CHI JSON/JSONL knowledge files from markdown.")
	parser.add_argument("--source", type=Path, default=None, help="Markdown source directory. Default: <project>/artifacts/out_md")
	parser.add_argument("--target", type=Path, default=None, help="Target knowledge directory. Default: <project>/kb/sections")
	return parser


def main() -> None:
	args = build_arg_parser().parse_args()
	project_root = Path(__file__).resolve().parents[2]
	source_root = args.source if args.source else (project_root / "artifacts" / "out_md")
	target_root = args.target if args.target else (project_root / "kb" / "sections")
	if not source_root.exists():
		raise FileNotFoundError(f"Source markdown directory not found: {source_root}")

	results = []
	for md_path in sorted(source_root.glob("*.md")):
		results.append(build_section(md_path, target_root))

	summary = {
		"sourceRoot": source_root.as_posix(),
		"targetRoot": target_root.as_posix(),
		"sectionCount": len(results),
		"nonEmptySections": sum(1 for item in results if item["hasSource"]),
		"emptySections": sum(1 for item in results if not item["hasSource"]),
		"totalChunks": sum(item["chunks"] for item in results),
		"totalObjects": sum(item["objects"] for item in results),
		"totalRules": sum(item["rules"] for item in results),
		"totalFlows": sum(item["flows"] for item in results),
		"totalVerification": sum(item["verification"] for item in results),
		"sections": results,
	}
	write_json(target_root / "_summary.json", summary)
	print(json.dumps({k: v for k, v in summary.items() if k != "sections"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
	main()
