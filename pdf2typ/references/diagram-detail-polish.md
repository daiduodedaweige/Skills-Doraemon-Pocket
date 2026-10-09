# Diagram Detail Polish

Use for CeTZ circuit/layout conversions, requests for closer resemblance to a PDF, and fixes to label spacing or wire connections.

## Diagnose From The Actual Artifact

Inspect both the source PDF and the PDF the user is viewing. Confirm the source import is active and which output was last compiled. A corrected `/tmp` preview does not update project `main.pdf`.

Find the affected figure in the compiled document using its caption, pin labels, or Typst query. PDF page indices include cover and front matter; a printed page number is not necessarily the page passed to `pdftoppm`.

Render only the affected PDF page when the change is local:

```bash
pdftoppm -f 85 -l 85 -singlefile -r 240 -png main.pdf /tmp/reset-detail
```

Here `85` is an example physical PDF page index, not a fixed page for future versions. Inspect the PNG at reading scale and zoom into each revised connection. A successful compile proves syntax and layout evaluation, not visual correctness.

## Connect To The Symbol Geometry

Read the drawing helper before changing endpoints. Check vertex positions, scaling, rotation, pin labels, and draw order. A helper comment can be wrong; derive the connection from the rendered shape and its code.

For the current `pic/diagram.typ` MUX, the polygon vertices relative to `(x, y)` are:

```text
(0, -6), (5, -3), (5, 3), (0, 6)
```

Its left edge is vertical; its bottom edge is sloped. The intended connection points are:

| Connection | Coordinate |
| --- | --- |
| Upper data input | `(x, y+3)` |
| Lower data input | `(x, y-3)` |
| Output | `(x+5, y)` |
| Bottom selection at horizontal midpoint | `(x+2.5, y-4.5)` |

The bottom-edge equation is `pin-y = y-6 + 3/5 * (pin-x-x)`. Stopping at `(x+2.5, y-6)` leaves a gap of 1.5 logical units. For the two MUXes in `reset.seq.typ`, `(48, 24)` and `(127, 55)`, the selection endpoints are `(50.5, 19.5)` and `(129.5, 50.5)`. Recalculate if the shape changes; these coordinates are not universal MUX pins.

- Check selection lines as well as both data inputs and the output. Moving one class of endpoint does not fix the others.
- Use the exact boundary intersection. Only consider a tiny stroke overlap after verifying geometry; extending a line into the symbol can strike through `0/1` labels and hide a wrong endpoint.
- With transformed symbols, transform both the outline and pin coordinates consistently. Prefer existing named anchors or shared calculated coordinates when available.
- Inspect junction dots, crossings, inversion bubbles, and clock triangles against the source. A crossing must not accidentally become a junction. A wire must not bypass an inversion bubble or stop at the wrong pin.
- When wires are drawn after symbols, make sure they do not overwrite internal labels. When drawn before symbols, opaque fills must not hide an intended connection.

## Wire Crossings And Bridges

When the source uses small arches to indicate non-connected wire crossings, preserve that distinction in the editable drawing. Inspect the source topology first: junctions retain dots, while crossings without electrical connection can use bridges. Do not add an arch at every apparent intersection or at a branch endpoint.

Use `pic/dft/ram_bypass.seq.typ` and its local `crossing-wire` helper as a working CeTZ example. It splits a horizontal wire around explicitly supplied crossing coordinates and replaces each short interval with a cubic Bezier arch. For a crossing at `(x, y)` and radius `r`:

```typst
let start = (x - r, y)
let end = (x + r, y)
let c0 = (x - r, y + 1.6 * r)
let c1 = (x + r, y + 1.6 * r)
draw.on-layer(1, {
  draw.bezier(start, end, c0, c1, stroke: white + 1.8pt)
  draw.bezier(start, end, c0, c1, stroke: ink + 0.55pt)
})
```

This example uses the existing `draw` and `ink` imports. The wider background-colored stroke separates the arch from the underlying wire; the narrower foreground stroke draws the visible bridge. White is appropriate only on a white background. Adapt the masking color or drawing method for shaded regions so the bridge does not leave a white scar.

- Split the original straight wire between `x-r` and `x+r`; keeping a straight segment beneath the arch can make it look like a connected loop.
- Place bridge curves above the crossing wires so later wires do not redraw through the arch. Avoid masking nearby symbols, labels, junction dots, or colored borders.
- Sort crossing coordinates along the segment and verify they actually intersect another wire. The helper assumes a left-to-right horizontal segment; adapt geometry for other orientations.
- Choose the radius for the delivered figure size and the closest neighboring wires. The RAM Bypass example uses `0.65` logical units; neighboring bridge intervals must not overlap or extend past segment endpoints.
- Inspect both curved crossings and dotted junctions on the final document page. Each straight-to-curve join must remain continuous, each non-connected crossing visibly separate, and each intended branch connected.

## Space Labels At The Delivered Size

Use the source PDF's text-to-symbol proportions as a reference, not its absolute font sizes: a standalone PDF and a figure embedded in the document may have different physical widths. Inspect the final page before choosing sizes.

For multiline box descriptions, center both the text block and its individual lines when the source uses centered text. The shared `box` helper centers the content anchor but does not itself center multiline text; pass `body: align(center, [...])` where needed. Check the longest word against the available box width and leave visible side padding. Prefer a modest local box-width adjustment over text that touches the outline or an unnecessarily small font. Keep box text, signal labels, and explanatory notes proportionate rather than forcing one size on all three.

Check labels inside each symbol as well as surrounding signal names. `Clk` and `CDN` must remain distinct at the figure's actual width in the full document, with room for the clock triangle and reset connection.

Prefer moving labels or enlarging the affected symbol over shrinking text until it is difficult to read. If a shared helper needs configurable offsets, preserve its defaults for other diagrams and opt in only in the figure being refined. Keep wire pin positions separate from text offsets so moving a label does not move a connection.

For narrow stacked abbreviations such as `B / I / S / R`, default paragraph leading can make the text taller than the box even when each letter fits horizontally. Place letters at explicit, evenly spaced centers within the existing box, or set suitable leading and enlarge the box when needed. Keep top/bottom padding and wire-entry clearance; do not reduce font size as the first fix. In `pic/dft/repair.seq.typ`, the local `bisr` helper places 5pt letters at offsets `8.5`, `6.2`, `3.8`, and `1.5` in a 10-unit-high box. Recalculate for other box sizes or final figure widths.

## Preserve Arrow Styles

Distinguish thin wires or annotation arrows from hollow thick bus arrows when the source uses both. The shared `wire(..., both: true)` produces a thin double-ended line, not a hollow thick arrow. For a hollow bus, use a closed CeTZ polygon with a background-colored fill, a colored outline, and distinct arrowheads at the required ends. Keep shaft thickness and head dimensions consistent across related buses, including long and short segments; retain thin arrowheads for explanatory callouts.

See the local `bus-arrow` helper in `pic/dft/mbist_clockgate.seq.typ` for a double-ended hollow-arrow example. Reuse its construction when appropriate, but choose dimensions for the new figure's scale and spacing. Keep figure-specific styling local unless a shared primitive genuinely needs extension.

## Center Signal Labels On Wires

Place a signal description near the midpoint of the relevant uninterrupted wire segment, not at an arbitrary bend or endpoint. On a vertical segment, horizontal text can be centered on the wire with a small background-colored mask, as in the local `signal-label` helper in `pic/dft/mbist_clockgate.seq.typ`. On a horizontal segment, center the label above or below the segment with a consistent small offset. A mask is a visual interruption only: keep the underlying wire continuous in the source.

Choose a readable signal-label size that fits the available spacing. Stagger adjacent labels or adjust local routing when needed so a label does not mask a neighboring wire, symbol, or junction. Do not change electrical topology merely to center text. Inspect both the segment midpoint and the full label bounding area in the rendered document.

## Route Buses Outside Functional Blocks

Use free corridors between rows for shared buses. Branches must stop at the facing boundary of each destination, not continue across its interior to the far edge. For a bus between two RAM rows, connect upward to the bottom of the upper RAM and downward to the top of the lower RAM. In `repair.seq.typ`, the bus is at `sy + 16`; the upper-row pins are at `ry`, while the lower-row pins are at `ry + 10` for 10-unit-high RAMs.

- Draw a shared trunk once, then its branches; avoid drawing the same trunk again for every destination.
- Inspect the whole polyline against every intervening functional box and label, not only its endpoints. Route around obstacles with clearance; opaque fills or draw order must not conceal a through-box route.
- Distinguish functional symbols from enclosing slice/hierarchy or dashed grouping frames. A bus can enter its destination's enclosing group, but must not pass through unrelated functional symbols. Preserve the source topology and intentional boundary entries.
- Retain non-connected crossing bridges and intended junctions when rerouting. Check both repeated slices or rows, since a loop can reproduce the same endpoint error throughout the figure.

## Final Visual Acceptance

After the last geometry change:

1. Compile to the requested output path; use `/tmp` for previews when no project PDF update was requested.
2. Render the affected page from that output, not a stale preview. Check every changed endpoint at enlarged scale and all labels at reading scale, including box padding, multiline alignment, wire-label centering, and the distinction between thin and hollow thick arrows.
3. Verify caption, cross-reference, width, and page placement in the full document. If a shared helper's default behavior changed, inspect the other figures that use it.
4. Finish only after the reported visual defect is resolved in the delivered artifact. State what was verified and any remaining limitation without claiming pixel-identical reproduction from a compile alone.
