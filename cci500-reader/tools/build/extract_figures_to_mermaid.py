from __future__ import annotations

import argparse
import math
import re
from dataclasses import dataclass
from pathlib import Path

import fitz


FIGURE_CAPTION_RE = re.compile(r"(?:Figure|Fig\.?|图)\s*([A-Z]?\d+(?:\.\d+)*)\s*[:：]\s*(.+)", re.IGNORECASE)
MULTI_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class TextGroup:
	text: str
	x0: float
	y0: float
	x1: float
	y1: float

	@property
	def cx(self) -> float:
		return (self.x0 + self.x1) / 2

	@property
	def cy(self) -> float:
		return (self.y0 + self.y1) / 2

	@property
	def width(self) -> float:
		return self.x1 - self.x0

	@property
	def height(self) -> float:
		return self.y1 - self.y0


@dataclass(frozen=True)
class LineSegment:
	x0: float
	y0: float
	x1: float
	y1: float

	@property
	def dx(self) -> float:
		return self.x1 - self.x0

	@property
	def dy(self) -> float:
		return self.y1 - self.y0

	@property
	def length(self) -> float:
		return math.hypot(self.dx, self.dy)

	@property
	def midpoint(self) -> tuple[float, float]:
		return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)


@dataclass(frozen=True)
class Marker:
	x: float
	y: float


@dataclass(frozen=True)
class FigureRegion:
	caption_id: str
	caption_title: str
	caption_y0: float
	y_min: float
	y_max: float


def normalize_text(text: str) -> str:
	return MULTI_SPACE_RE.sub(" ", text.replace("\n", " ")).strip()


def safe_filename(name: str) -> str:
	name = re.sub(r'[\\/:*?"<>|]', "_", name).strip()
	return name or "figure"


def safe_mermaid_id(prefix: str, index: int) -> str:
	return f"{prefix}{index:03d}"


def escape_label(text: str) -> str:
	text = text.replace('"', "'")
	text = text.replace("\n", "<br/>")
	return text.strip()


def overlap_ratio(a0: float, a1: float, b0: float, b1: float) -> float:
	left = max(a0, b0)
	right = min(a1, b1)
	if right <= left:
		return 0.0
	shorter = max(min(a1 - a0, b1 - b0), 1.0)
	return (right - left) / shorter


def distance(x0: float, y0: float, x1: float, y1: float) -> float:
	return math.hypot(x1 - x0, y1 - y0)


def iter_text_groups(page: fitz.Page, y_min: float, y_max: float) -> list[TextGroup]:
	text_dict = page.get_text("dict")
	groups: list[TextGroup] = []

	for block in text_dict.get("blocks", []):
		if block.get("type") != 0:
			continue
		for line in block.get("lines", []):
			span_candidates = []
			for span in line.get("spans", []):
				text = normalize_text(span.get("text", ""))
				if not text:
					continue
				x0, y0, x1, y1 = span["bbox"]
				if y1 < y_min or y0 > y_max:
					continue
				span_candidates.append((text, x0, y0, x1, y1))

			if not span_candidates:
				continue

			span_candidates.sort(key=lambda item: item[1])
			current: list[tuple[str, float, float, float, float]] = []
			for span in span_candidates:
				if not current:
					current.append(span)
					continue

				prev = current[-1]
				gap = span[1] - prev[3]
				if gap <= 8:
					current.append(span)
				else:
					groups.append(collapse_group(current))
					current = [span]

			if current:
				groups.append(collapse_group(current))

	return merge_vertical_groups(groups)


def collapse_group(parts: list[tuple[str, float, float, float, float]]) -> TextGroup:
	text = " ".join(item[0] for item in parts)
	x0 = min(item[1] for item in parts)
	y0 = min(item[2] for item in parts)
	x1 = max(item[3] for item in parts)
	y1 = max(item[4] for item in parts)
	return TextGroup(text=text, x0=x0, y0=y0, x1=x1, y1=y1)


def merge_vertical_groups(groups: list[TextGroup]) -> list[TextGroup]:
	ordered = sorted(groups, key=lambda group: (group.y0, group.x0))
	merged: list[TextGroup] = []

	for group in ordered:
		if not merged:
			merged.append(group)
			continue

		prev = merged[-1]
		vertical_gap = group.y0 - prev.y1
		x_overlap = overlap_ratio(prev.x0, prev.x1, group.x0, group.x1)
		if vertical_gap <= 6 and x_overlap >= 0.45:
			merged[-1] = TextGroup(
				text=f"{prev.text}\n{group.text}",
				x0=min(prev.x0, group.x0),
				y0=min(prev.y0, group.y0),
				x1=max(prev.x1, group.x1),
				y1=max(prev.y1, group.y1),
			)
		else:
			merged.append(group)

	return merged


def iter_line_segments(page: fitz.Page, y_min: float, y_max: float) -> tuple[list[LineSegment], list[Marker], list[fitz.Rect]]:
	segments: list[LineSegment] = []
	markers: list[Marker] = []
	rects: list[fitz.Rect] = []

	for drawing in page.get_drawings():
		rect = drawing["rect"]
		if rect.y1 < y_min or rect.y0 > y_max:
			continue
		rects.append(rect)
		for item in drawing["items"]:
			kind = item[0]
			if kind == "l":
				p0, p1 = item[1], item[2]
				segments.append(LineSegment(x0=p0.x, y0=p0.y, x1=p1.x, y1=p1.y))
		if drawing.get("type") in {"f", "fs"} and rect.width <= 14 and rect.height <= 14:
			markers.append(Marker(x=(rect.x0 + rect.x1) / 2, y=(rect.y0 + rect.y1) / 2))

	return segments, markers, rects


def find_figure_region(page: fitz.Page) -> FigureRegion | None:
	caption_matches: list[tuple[str, str, float]] = []
	for x0, y0, x1, y1, text, *_ in page.get_text("blocks"):
		normalized = normalize_text(text)
		match = FIGURE_CAPTION_RE.search(normalized)
		if match:
			caption_matches.append((match.group(1), match.group(2).strip(), y0))

	if not caption_matches:
		return None

	caption_id, caption_title, caption_y0 = sorted(caption_matches, key=lambda item: item[2])[0]
	drawing_rects = [drawing["rect"] for drawing in page.get_drawings() if drawing["rect"].y1 <= caption_y0 + 2]
	if not drawing_rects:
		return None

	y_min = min(rect.y0 for rect in drawing_rects)
	y_max = caption_y0 - 4
	if y_max <= y_min:
		return None

	return FigureRegion(
		caption_id=caption_id,
		caption_title=caption_title,
		caption_y0=caption_y0,
		y_min=y_min,
		y_max=y_max,
	)


def detect_sequence_lifelines(segments: list[LineSegment], y_min: float, y_max: float) -> list[LineSegment]:
	figure_height = max(y_max - y_min, 1.0)
	candidates = [
		segment
		for segment in segments
		if abs(segment.dx) <= 3 and abs(segment.dy) >= max(60.0, figure_height * 0.35)
	]
	if not candidates:
		return []

	merged: list[LineSegment] = []
	for segment in sorted(candidates, key=lambda item: (item.x0 + item.x1) / 2):
		if not merged:
			merged.append(segment)
			continue

		prev = merged[-1]
		prev_x = (prev.x0 + prev.x1) / 2
		curr_x = (segment.x0 + segment.x1) / 2
		if abs(prev_x - curr_x) <= 8:
			merged[-1] = LineSegment(
				x0=(prev_x + curr_x) / 2,
				y0=min(prev.y0, segment.y0),
				x1=(prev_x + curr_x) / 2,
				y1=max(prev.y1, segment.y1),
			)
		else:
			merged.append(segment)

	return merged if 2 <= len(merged) <= 8 else []


def find_participants(groups: list[TextGroup], lifelines: list[LineSegment]) -> list[tuple[str, float]]:
	line_top = min(line.y0 for line in lifelines)
	top_band = sorted(
		[
			group
			for group in groups
			if line_top - 28 <= group.cy <= line_top + 4
			and len(group.text) <= 40
			and (len(group.text) >= 3 or "-" in group.text)
		],
		key=lambda group: group.cx,
	)
	if len(top_band) >= len(lifelines):
		return [(group.text, line.x0) for group, line in zip(top_band, sorted(lifelines, key=lambda item: item.x0))]

	participants: list[tuple[str, float]] = []
	used_texts: set[str] = set()

	for line in sorted(lifelines, key=lambda item: item.x0):
		line_x = (line.x0 + line.x1) / 2
		candidates = [
			group
			for group in groups
			if group.cy <= line_top + 12 and abs(group.cx - line_x) <= 60
		]
		if not candidates:
			continue
		best = min(candidates, key=lambda group: (abs(group.cx - line_x), line_top - group.cy))
		if best.text in used_texts:
			continue
		participants.append((best.text, line_x))
		used_texts.add(best.text)

	return participants


def nearest_marker_direction(markers: list[Marker], p0: tuple[float, float], p1: tuple[float, float]) -> tuple[float, float] | None:
	best: tuple[float, float] | None = None
	d0 = min((distance(marker.x, marker.y, p0[0], p0[1]) for marker in markers), default=1e9)
	d1 = min((distance(marker.x, marker.y, p1[0], p1[1]) for marker in markers), default=1e9)
	if d0 <= 10 and d0 < d1:
		best = p0
	elif d1 <= 10 and d1 < d0:
		best = p1
	return best


def nearest_label(groups: list[TextGroup], segment: LineSegment, x_pad: float = 18, y_pad: float = 16) -> str:
	mx, my = segment.midpoint
	left = min(segment.x0, segment.x1) - x_pad
	right = max(segment.x0, segment.x1) + x_pad
	candidates = [
		group
		for group in groups
		if left <= group.cx <= right and abs(group.cy - my) <= y_pad
	]
	if not candidates:
		return ""
	best = min(candidates, key=lambda group: (abs(group.cy - my), abs(group.cx - mx)))
	return best.text


def sanitize_participant(label: str, index: int) -> tuple[str, str]:
	alias = re.sub(r"[^A-Za-z0-9_]", "_", label).strip("_")
	if not alias or alias[0].isdigit():
		alias = f"P{index}"
	return alias, label


def build_sequence_mermaid(region: FigureRegion, groups: list[TextGroup], segments: list[LineSegment], markers: list[Marker]) -> str | None:
	lifelines = detect_sequence_lifelines(segments, region.y_min, region.y_max)
	if not lifelines:
		return None

	participants = find_participants(groups, lifelines)
	if len(participants) < 2:
		return None

	participant_ids = []
	for index, (label, line_x) in enumerate(participants, start=1):
		alias, display = sanitize_participant(label, index)
		participant_ids.append((alias, display, line_x))

	message_segments = [
		segment
		for segment in segments
		if segment.length >= 24 and abs(segment.dx) >= 24 and abs(segment.dy) <= max(abs(segment.dx) * 0.5, 28)
	]
	messages: list[tuple[float, str, str, str]] = []
	seen: set[tuple[str, str, str, int]] = set()

	for segment in message_segments:
		start_idx = min(range(len(participant_ids)), key=lambda idx: abs(participant_ids[idx][2] - segment.x0))
		end_idx = min(range(len(participant_ids)), key=lambda idx: abs(participant_ids[idx][2] - segment.x1))
		if start_idx == end_idx:
			continue

		p0 = (segment.x0, segment.y0)
		p1 = (segment.x1, segment.y1)
		arrow_at = nearest_marker_direction(markers, p0, p1)
		if arrow_at == p0:
			sender = participant_ids[end_idx][0]
			receiver = participant_ids[start_idx][0]
		elif arrow_at == p1:
			sender = participant_ids[start_idx][0]
			receiver = participant_ids[end_idx][0]
		else:
			sender = participant_ids[start_idx][0]
			receiver = participant_ids[end_idx][0]

		label = nearest_label(groups, segment)
		key = (sender, receiver, label, round(segment.midpoint[1]))
		if key in seen:
			continue
		seen.add(key)
		messages.append((segment.midpoint[1], sender, receiver, label))

	if not messages:
		return None

	lines = [
		"sequenceDiagram",
	]
	for alias, display, _ in participant_ids:
		lines.append(f'    participant {alias} as {escape_label(display)}')

	for _, sender, receiver, label in sorted(messages, key=lambda item: item[0]):
		if label:
			lines.append(f'    {sender}->>{receiver}: {escape_label(label)}')
		else:
			lines.append(f"    {sender}->>{receiver}")

	return "\n".join(lines) + "\n"


def build_flowchart_mermaid(region: FigureRegion, groups: list[TextGroup], segments: list[LineSegment], markers: list[Marker]) -> str | None:
	nodes = [
		group
		for group in groups
		if group.text and not FIGURE_CAPTION_RE.search(group.text) and len(group.text) <= 120
	]
	if not nodes:
		return None

	node_ids: dict[int, str] = {}
	lines = [
		"flowchart LR",
	]

	for index, node in enumerate(sorted(nodes, key=lambda group: (group.y0, group.x0)), start=1):
		node_id = safe_mermaid_id("N", index)
		node_ids[index - 1] = node_id
		lines.append(f'    {node_id}["{escape_label(node.text)}"]')

	edges: set[tuple[str, str, str]] = set()
	for segment in segments:
		if segment.length < 18:
			continue
		if abs(segment.dx) <= 2 and abs(segment.dy) >= 40:
			continue

		start_idx = nearest_node_index(nodes, segment.x0, segment.y0)
		end_idx = nearest_node_index(nodes, segment.x1, segment.y1)
		if start_idx is None or end_idx is None or start_idx == end_idx:
			continue

		start_node = node_ids[start_idx]
		end_node = node_ids[end_idx]
		arrow_at = nearest_marker_direction(markers, (segment.x0, segment.y0), (segment.x1, segment.y1))
		if arrow_at == (segment.x0, segment.y0):
			edge = (end_node, start_node, "-->")
		elif arrow_at == (segment.x1, segment.y1):
			edge = (start_node, end_node, "-->")
		else:
			edge = (start_node, end_node, "---")
		edges.add(edge)

	for start_node, end_node, connector in sorted(edges):
		lines.append(f"    {start_node} {connector} {end_node}")

	return "\n".join(lines) + "\n"


def nearest_node_index(nodes: list[TextGroup], x: float, y: float) -> int | None:
	best_idx: int | None = None
	best_distance = 1e9
	for index, node in enumerate(nodes):
		dx = 0.0
		if x < node.x0:
			dx = node.x0 - x
		elif x > node.x1:
			dx = x - node.x1
		dy = 0.0
		if y < node.y0:
			dy = node.y0 - y
		elif y > node.y1:
			dy = y - node.y1
		limit = min(max(node.height * 2.0, 18.0), 28.0)
		dist = math.hypot(dx, dy)
		if dist <= limit and dist < best_distance:
			best_distance = dist
			best_idx = index
	return best_idx


def extract_mermaid(page: fitz.Page) -> tuple[FigureRegion | None, str | None]:
	region = find_figure_region(page)
	if region is None:
		return None, None

	groups = iter_text_groups(page, region.y_min - 10, region.y_max)
	segments, markers, _ = iter_line_segments(page, region.y_min - 10, region.y_max)
	if not segments:
		return region, None

	sequence_code = build_sequence_mermaid(region, groups, segments, markers)
	if sequence_code:
		return region, sequence_code

	flowchart_code = build_flowchart_mermaid(region, groups, segments, markers)
	return region, flowchart_code


def iter_pdf_paths(project_root: Path, input_dir: Path, pdf_args: list[str]) -> list[Path]:
	if pdf_args:
		paths = []
		for raw_path in pdf_args:
			path = Path(raw_path)
			if not path.is_absolute():
				path = project_root / path
			paths.append(path)
		return sorted(paths)
	return sorted(path for path in input_dir.rglob("*.pdf") if path.is_file())


def main() -> None:
	parser = argparse.ArgumentParser(description="Extract Mermaid approximations from figure PDFs.")
	parser.add_argument("--input-dir", default="artifacts/split_pdfs", help="Directory containing split PDF files.")
	parser.add_argument("--output-dir", default="artifacts/figures_mermaid", help="Directory for generated Mermaid files.")
	parser.add_argument("--pdf", action="append", default=[], help="Optional PDF path to process. Repeat for multiple files.")
	args = parser.parse_args()

	project_root = Path(__file__).resolve().parents[2]
	input_dir = project_root / args.input_dir
	output_dir = project_root / args.output_dir
	output_dir.mkdir(parents=True, exist_ok=True)

	pdf_paths = iter_pdf_paths(project_root, input_dir, args.pdf)
	generated = 0
	skipped = 0

	for pdf_path in pdf_paths:
		if not pdf_path.exists():
			print(f"Missing: {pdf_path}")
			skipped += 1
			continue

		generated_for_pdf = 0
		with fitz.open(pdf_path) as document:
			for page_index, page in enumerate(document, start=1):
				region, mermaid = extract_mermaid(page)
				if region is None or not mermaid:
					continue

				output_name = safe_filename(f"{pdf_path.stem}__{region.caption_id}") + ".mmd"
				output_path = output_dir / output_name
				if output_path.exists():
					output_name = safe_filename(f"{pdf_path.stem}__{region.caption_id}__p{page_index}") + ".mmd"
					output_path = output_dir / output_name
				output_path.write_text(mermaid, encoding="utf-8")
				print(f"Generated: {pdf_path.name} -> {output_path.name} [{region.caption_id} p{page_index}]")
				generated += 1
				generated_for_pdf += 1

		if generated_for_pdf == 0:
			print(f"Skipped: {pdf_path.name}")
			skipped += 1

	print(f"Done. Generated {generated} file(s), skipped {skipped} file(s).")


if __name__ == "__main__":
	main()
