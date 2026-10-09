# ZhuJiang Sequence Typst Style

Use this reference when converting transaction sequence PDF diagrams to `.seq.typ` files.

## Canonical Examples

Authoritative conversions in this repo:

- `pic/transaction/zj_allocate_read_structure.pdf` -> `pic/transaction/zj_allocate_read_structure.seq.typ`
- `pic/transaction/zj_non_allocate_read_structure.pdf` -> `pic/transaction/zj_non_allocate_read_structure.seq.typ`

When a new diagram resembles these examples, inspect those `.seq.typ` files and copy their structure and formatting style.

## File Template

```typst
// Source: pic/transaction/<name>.pdf
// Uses the SEQ_DIAGRAM DSL imported from @local/redrisc-doc:0.1.0.

#import "@local/redrisc-doc:0.1.0": *

#let <name> = [
  #let R = PARTICIPANT("Requester", 0.09)
  #let H = PARTICIPANT("Home", 0.40)
  #let D = PARTICIPANT("Subordinate", 0.68)
  #let S = PARTICIPANT("Snoopee", 0.90)
  #figure(
    SEQ_DIAGRAM((
      SET_CANVAS_WIDTH(125),
      SCALE_FRONT(2.0),
      MSG(R, H, REQ, [VisibleLabel @ REQ]),
      ALT(
        BRANCH("1. Branch title", (
          MSG(H, R, DAT, [CompData @ DAT]),
        )),
      ),
    )),
    kind: image,
    supplement: [图],
    caption: [Readable Title 事务结构图],
  ) <fig-readable_label>
]
```

## Participants

Common participant mapping:

| Diagram name | Variable | Position |
| --- | --- | --- |
| Requester | `R` | `0.09` |
| Home | `H` | `0.40` |
| Subordinate | `D` | `0.68` |
| Snoopee | `S` | `0.90` |

For a different lane count, keep left-to-right spacing visually similar and use short mnemonic variables.

## Message Channels

Choose the channel from the protocol role, then annotate the label with the same channel:

- Request opcodes: `REQ`, e.g. `ReadNoSnp`, `ReadOnce`, `ReadUnique`, `MakeReadUnique`.
- Snoop opcodes: `SNP`, e.g. `Snp*Fwd`.
- Response-only opcodes: `RSP`, e.g. `ReadReceipt`, `Comp`, `CompAck`, `SnpResp`, `SnpRespFwded`.
- Data-bearing opcodes: `DAT`, e.g. `CompData`, `SnpRespData`, `SnpRespDataFwded`.

Examples:

```typst
MSG(H, D, REQ, [ReadNoSnp @ REQ]),
MSG(S, H, RSP, [SnpRespFwded @ RSP]),
MSG(S, H, DAT, [SnpRespDataFwded @ DAT]),
```

For long request lists, keep the example wrapping style:

```typst
MSG(R, H, REQ, [ReadNotSharedDirty, ReadUnique, \ ReadPreferUnique, MakeReadUnique @ REQ]),
```

## Known Read Diagram Normalizations

The two checked-in read diagrams intentionally normalize the visual PDF into the DSL:

- Visible `Allocate Read` becomes `[ReadNotSharedDirty, ReadUnique, \ ReadPreferUnique, MakeReadUnique @ REQ]`.
- Visible `Non-Allocate Read` becomes `[ReadNoSnp, ReadOnce @ REQ]`.
- In the forwarding-snoop region, the visual "response or data to Home" alternatives become separate nested branches:
  - `BRANCH("3.a with response to Home", (... SnpRespFwded @ RSP ...))`
  - `BRANCH("4.a with data to Home", (... SnpRespDataFwded @ DAT ...))`
- `ExpCompAck == 1` is represented with `OPT("ExpCompAck == 1", (...))`.
- `Ordered request` is represented with `OPT("Ordered request", (... ReadReceipt ...))`.

Prefer these normalized forms when handling related diagrams.

## Caption And Label Style

Use Chinese figure captions matching the section language:

- `zj_allocate_read_structure` -> `caption: [Read Allocating 事务结构图]`, label `<fig-alloc_rd_txn>`.
- `zj_non_allocate_read_structure` -> `caption: [Read Non-Allocating 事务结构图]`, label `<fig-non_alloc_rd_txn>`.

For new diagrams, derive:

- `#let`: exact snake_case basename.
- caption: readable transaction name plus `事务结构图`.
- label: concise `fig-..._txn` or an existing label referenced by the section.

## Visual Reading Checklist

Before writing the file, record mentally:

- Lane order and participant names.
- Every arrow's source, destination, visible label, and channel.
- Shaded top-level branches and their titles.
- Nested branches or optional conditions.
- Messages before and after branch groups, such as final `CompAck`.

After writing the file, compare the code against this checklist and compile the document when possible.
