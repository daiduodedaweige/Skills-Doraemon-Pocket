---
name: pdf2typ
description: Convert ZhuJiang NG PDF diagrams into editable Typst .seq.typ source and refine their visual details. Use for sequence/transaction diagrams via the local redrisc-doc SEQ_DIAGRAM DSL, or circuit/layout diagrams via CeTZ, including fixes to labels, wire connections, and document integration.
---

# PDF To Typst

## Overview

Reconstruct PDF diagrams as editable Typst source, or refine an existing conversion. Treat the PDF as a visual source: many Skia whiteboard PDFs have no extractable text, so render and inspect the page image before writing code.

For transaction sequence diagrams, read [references/zj-seq-typ-style.md](references/zj-seq-typ-style.md). For circuit/layout diagrams, requests for closer visual fidelity, or label/connection fixes, read [references/diagram-detail-polish.md](references/diagram-detail-polish.md).

## Choose The Drawing Method

- Prefer `SEQ_DIAGRAM` for protocol sequences that match the existing transaction examples. Steps 3-5 below apply to this mode.
- Use CeTZ for circuit/layout diagrams. Reuse `pic/diagram.typ` and `pic/home_layout.typ` where appropriate; inspect their actual geometry before deriving pin coordinates.
- When the user requests fidelity to the original, account for sloped arrows, separate side notes, shaded regions, and participant colors. The current `MSG` API draws horizontal arrows with channel colors; use CeTZ when those constraints prevent the requested layout. Do not represent a decorative background as `ALT`/`OPT` unless it has that protocol meaning.
- For a refinement request, preserve the existing method and edit the affected geometry or labels unless changing methods is necessary to achieve the user's request.

## Workflow

1. Identify the source PDF and target `.seq.typ` path.
   - Place `<stem>.seq.typ` beside the source PDF, using the actual repository basename.
   - Use `#let <stem> = [` where `<stem>` is the PDF basename without extension.
   - Add source comments at the top, matching the existing examples.

2. Render the PDF for inspection.
   - Run:

```bash
python .codex/skills/pdf2typ/scripts/prepare_pdf_seq.py pic/transaction/example.pdf --out /tmp/pdf-seq/example
```

   - Inspect the generated PNG(s) visually. Use text extraction only as a bonus; for these Skia whiteboard PDFs it is usually empty.

3. Infer participants from left to right.
   - Use short variables for repeated names: `R` Requester, `H` Home, `D` Subordinate, `S` Snoopee.
   - For the common four-lane layout, use positions `0.09`, `0.40`, `0.68`, `0.90`.
   - Keep participant names exactly as shown in the diagram unless the existing Typst examples use a normalized spelling.

4. Translate arrows into DSL messages.
   - Direction comes from the arrow head: `MSG(source, destination, CHANNEL, [Label @ CHANNEL])`.
   - Use channel constants by protocol role: `REQ` for requests, `SNP` for snoops, `RSP` for response-only messages, `DAT` for data-bearing messages.
   - Preserve top-to-bottom message order inside each branch.
   - When a visible high-level label represents a known request family, expand it to the concrete request op list used by the examples.

5. Translate shaded regions into structure.
   - Top-level mutually exclusive bands become one `ALT(...)` containing `BRANCH("title", (...))` entries.
   - Nested mutually exclusive bands become nested `ALT(...)`.
   - Truly optional conditional regions become `OPT("condition", (...))`.
   - If the PDF draws small `Opt:` bars inside a known mutually exclusive response/data choice, follow the existing `.seq.typ` style and normalize them into separate `BRANCH` entries when that better matches the DSL.

6. Add the figure wrapper.
   - Import `@local/redrisc-doc:0.1.0`.
   - Wrap the DSL or CeTZ drawing in `#figure(..., kind: image, supplement: [图], caption: [...]) <label>`.
   - For the sequence DSL, use `SET_CANVAS_WIDTH(125)` and `SCALE_FRONT(2.0)` unless the new diagram clearly needs a different width.
   - Derive the caption and label from nearby section text if available; otherwise use the PDF title/stem and a stable `fig-...` label.

7. Integrate and validate.
   - If replacing an image in a section, update that section to import and use the new `#let`.
   - Preserve existing captions and labels, and follow nearby `outdent` and cross-reference conventions.
   - Run `typst compile main.typ /tmp/zj-ng-doc.pdf` when the repo is available. If the user asks to regenerate or correct project `main.pdf`, compile to that exact path and inspect that artifact.
   - Render and inspect the affected page of the full document, at normal reading scale and enlarged around revised details. A standalone preview does not verify the final page layout; compilation alone does not verify connections or legibility.
   - Fix observed gaps, overlaps, clipped labels, and incorrect topology; recompile and inspect after the last edit. Follow the detail reference for circuit-specific checks and PDF page selection.

## Quality Bar

- Produce Typst source, not an embedded `image(...)` of the PDF.
- Preserve the source's distinction between thin annotation arrows and hollow thick bus arrows. Check box text alignment, padding, and signal-label placement at the delivered figure size; see the detail reference for implementation guidance.
- Prefer existing sequence examples for protocol normalization; honor explicit requests for closer visual fidelity.
- Verify every affected pin, including data inputs, output, clock/reset pins, and MUX selection wires. Wire endpoints must meet the actual outline, not merely the symbol's bounding box.
- Check stacked labels for internal padding at the delivered size, and route wires outside functional blocks to the facing pin boundary. See the detail reference for narrow BISR labels and inter-row bus routing.
- Preserve the source's distinction between junction dots and non-connected crossings. When bridges are needed, follow the CeTZ arch and layering guidance in `references/diagram-detail-polish.md`.
- Report the delivered artifact path and affected chapter/figure when integration is part of the task. Distinguish a `/tmp` preview from an updated project PDF.
- Keep indentation and trailing commas consistent with the checked-in `.seq.typ` files.
- Do not invent missing branches or protocol operations. If a label is ambiguous after visual inspection and neighboring sections do not clarify it, preserve the visible label and state the uncertainty.
