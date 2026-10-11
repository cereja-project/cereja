# Read-only collections and generic trees

UI-11 / [#310](https://github.com/cereja-project/cereja/issues/310) adds opt-in
`cereja.ui.collections`, using the existing [Unicode](ui-text.md),
[cell](ui-buffer.md), [layout](ui-layout.md), [editing/copy](ui-editing.md) and
focus contracts. Python 3.11+, standard library only. Importing the module
acquires no terminal and starts no worker, timer, domain service or operation.

## Public API

- `Row(identity, cells, content=None)`: immutable stable ID, tuple of 1..32
  single-line display cells and optional explicit safe `TextContent`.
- `Column(label, constraint=Constraint())`: immutable table heading and
  existing fixed/weighted column geometry. A table has 1..32 columns.
- `SelectableList(identity, rows, limits=CollectionLimits(), state='complete',
  message='')`: exactly one display cell per row.
- `Table(identity, columns, rows, ...)`: read-only rows with matching arity,
  pinned heading and fixed/weighted widths. Row navigation is also supported.
- `TreeNode(identity, label, parent=None, branch=False, state='complete',
  message='', content=None)`: generic parent-linked node. No filesystem type
  or rendered-tree parsing. `branch` declares children even before loading;
  known retained children and non-complete states also make a node expandable.
- `TreeView(identity, nodes, ...)`: admits nodes with each parent preceding
  its children. Siblings retain input order; navigation is preorder. This flat
  input avoids recursively retaining a caller's unbounded nested graph.
- `CollectionLimits(max_items=4096, max_bytes=1048576, max_depth=128)`: per-widget
  admission policy. Tree depth counts edges; a root is depth zero.
- `CollectionStatus`: `source_state`, `node_state`, `state`, `complete`,
  `retained_count`, `retained_bytes`, `examined_count`, `limit`, `message`.
- `CollectionAction`: `kind`, `reason`, `identity`, `content`, `selection`.
- `CollectionView`: `viewport`, `visible_ids`, `painted_rows`,
  `formatted_cells`, `status`. Counts describe the painted body, not headings.

Each surface exposes read-only `identity`, `limits`, `targets`, `selected`,
`order`, `scroll_y`, `status`, `text_selection` and `selection_notice`.
`targets` integrates with an existing `FocusManager`; the caller owns focus
and passes `focused=False` when another surface receives keys. `order` is the
bounded navigation projection, not the frame's visible slice.
`item(identity)` returns full retained typed data. Table `columns` and tree
`expanded` are read-only; `expanded` is a frozenset snapshot.

`update(items, state='complete', message='')` atomically replaces a snapshot.
Duplicate IDs, invalid hierarchy/arity/state or iterator exceptions reject the
update and leave previous selection/content intact. A tree rejects missing,
later or cyclic parents. ID stability across snapshots is the caller's contract.

`select(identity)` requires an ID in the navigation projection.
`scroll(dy)` changes the scroll anchor independently. Selection survives
reorder and focus changes. If the selected item disappears, choose the next
survivor in the last displayed order, then the previous survivor, then the first
new item or empty state. This row policy stays local to collections: focus-scope
restoration has different eligibility and does not construct per-row controls.

## Keys, painting and state

Up/Down select, Home/End select bounds, PageUp/PageDown move by the last visible
body height. Repeats are bounded index arithmetic. Navigation reveals selection
on the next paint. Manual scroll can inspect another region without moving it.
Right expands a tree branch or selects its first child; Left collapses or selects
the parent. Collapsing an ancestor of the selected node selects that ancestor.
`expand(identity)` and `collapse(identity)` are explicit tree mutations.

Enter yields `inspect` with stable identity and optional canonical content.
Inspect full data with `item(identity)`; the consumer owns a detail surface.
Right on an incomplete/error branch can yield `load` with its ID. Loading is
a static state and does not request another load. Intents do not enumerate,
launch work, acknowledge completion or create an automatic queue. Consumers
route asynchronous results through existing scheduling/generation contracts
and verify snapshot identity before applying a replacement update.

`paint(frame, rect, focused=True, clip=None)` paints only cell buffers, clearing
its clipped area. Tables reserve a heading row; every surface reserves a status
row. Focus `>` and navigation selection `*` remain textual in no-color mode.
Whole graphemes use existing metrics and safe clipping; ellipsis is `…` or
`...` in ASCII mode (shortened when necessary). Full retained labels/content
remain inspectable; visual ellipsis does not mean source results are incomplete.
Tabs in display cells use existing tab stops; multiline copy content is separate.

The actual ancestor-clipped body is the scroll window; hidden headings/footers
are not formatted. Zero geometry preserves state. Resize keeps requested scroll
anchors, selected/expanded IDs and canonical text selection; temporary effective
clamping on a larger viewport does not erase the smaller viewport's anchor.
A selected row already visible remains revealed when the body shrinks; a manually
hidden selection does not force scrolling back.
No animation or timer is involved, including reduced-motion use. Callers still
reserve the renderer's final column and compose the persistent composer separately.

## Complete, incomplete and truncated

Source and child enumeration states are `complete`, `incomplete`, `loading`
or `error`. An empty complete collection says Empty; incomplete/error/loading
never claim no matches. Tree status aggregates all retained node states,
including collapsed nodes, with error before loading before incomplete.

Admission stops at the first item, payload-byte or depth limit and keeps only
the admitted prefix. At most `max_items + 1` values are pulled; a value beyond
the count cap is only a lookahead sentinel, not validated/retained. The original
iterator is not stored or automatically closed. A depth cutoff stops the whole
prefix, including later siblings; the consumer must provide a better bounded
snapshot to expose them. Limit reasons are `items`, `bytes` or `depth`.

`state='truncated'` and `complete=False` identify a local cutoff; the original
`source_state` and aggregated `node_state` remain available separately.
The status row names the limit and retained count. Unknown omitted counts and
unread suffix errors are not inferred. Exact-cap exhausted input is complete
only when its supplied source/node states are complete.

`retained_bytes` conservatively sums safe UTF-8 IDs, parent IDs, labels/cells,
node messages and explicit canonical text/identity (shared payloads count per
item). It is not Python heap/RSS. Independent hard metadata caps are 16 KiB per
field, 32 cells per row and 32 columns; the surface ID/status message and table
headings have their own bounded overhead outside the item payload cap.
Caller input graphs, prebuilt canonical metrics, iterator generation time,
shared Unicode caches, frames and transient replacement snapshots are not
bounded by this byte count. No generator/callback is preempted. Total application
retention remains the consumer's responsibility; Ledger's 20-results/2-MiB
candidate is unchanged and is not a global memory guarantee.

Snapshot indexing and expansion changes can visit all admitted nodes, with
iterative traversal and bounded dictionaries/ID projections. Painting indexes
only the visible slice and formats only visible row/cell labels, plus visible
headings/status. Text work also depends on the bounded label lengths. This
distinction is measured below; virtual checks do not certify application latency.

## Canonical copy

Display cells and tree decoration are never a copy representation.
Supply explicit `TextContent` from typed data before layout, with safe/redacted
source, stable identity and revision. `set_text_selection(item_id, anchor, caret)`
uses logical grapheme offsets. The selection is independent of row/node selection,
scroll, focus and tree expansion. `clear_text_selection()` explicitly clears it.

Ctrl+C on the focused/key-owning collection uses existing `copy_action`.
An active textual selection yields a copy request, not a clipboard acknowledgement.
Copy only its canonical range, preserving tabs, indentation, blank lines and
intentional spaces. Exclude focus/branch markers, alignment, truncation, padding
and visual wraps. Copy failure/unavailability must retain this selection and
must never cause exit; repeated Ctrl+C keeps requesting the same safe payload.

A replaced/removed canonical identity, revision or text clears the selection
with `selection_notice`. Subsequent Ctrl+C yields `rejected`, never exit,
until an explicit clear or new valid textual selection. A collapsed node's text
can stay selected while its retained content still exists. With no active or
invalidated text selection, Ctrl+C yields an exit intent for the consumer's
job-aware lifecycle; a selected row/node alone is navigation. Clipboard transport,
native terminal-selection detection and application exit are not implemented here.

## Runnable bounded example

```python
from cereja.ui.buffer import CellBuffer, Rect
from cereja.ui.collections import Column, Row, Table
from cereja.ui.editing import TextContent
from cereja.ui.events import KeyEvent

source = TextContent('snippet', 1, '  code\t  \n\n  final\n')
table = Table('results', (Column('Name'), Column('Preview')),
              (Row('row-1', ('Synthetic', 'short preview'), source),))
frame = CellBuffer(40, 12)
view = table.paint(frame, Rect(1, 1, 37, 6))
table.set_text_selection('row-1', 0, len(source.text))
request = table.handle(KeyEvent('c', modifiers=frozenset({'ctrl'})))
assert request.kind == 'copy' and request.selection.text == source.text
assert view.painted_rows == 1
```

From a source checkout, these bounded synthetic demos print at most 40 rows
without acquiring a terminal, reading a path or executing a domain operation:

```text
python -B -S benchmarks/ui_collections.py --demo --kind tree --state incomplete --size 40x12
python -B -S benchmarks/ui_collections.py --demo --kind table --state truncated --size 80x24
python -B -S benchmarks/ui_collections.py --demo --kind list --state empty --size 120x40
```

The example keeps a separate composer, static states and explicit canonical copy.
It is a cell-buffer demonstration, not the Ledger app or official `cereja ui`.

## Verification and measurements

[Tests](../../tests/test_ui_collections.py) cover empty/error states, invalid
updates, stable next/previous fallback, Unicode/ASCII, clipping, resize, broad/deep
bounds, textual copy and existing scheduler/focus integration.
[Benchmark](../../benchmarks/ui_collections.py) separates admission, projection
setup and End-event-to-buffer time at 120x40, 80x24 and 40x12.
[Windows/Python 3.14 baseline](../../benchmarks/ui_collections_samples/baseline-windows-py314.json)
retains raw samples, conditions, environment and Git/LF source fingerprints.

Workloads cover 64/4096 lists, 4096 three-column rows, a broad 4096-node tree,
100000 generated nodes cut at 4096, a 10000-deep chain cut at 129 nodes and a
canonical-byte cutoff using a shared immutable payload counted per item.
Untimed tracemalloc windows keep widget/frame/view alive through measurement.
These are Python traced bytes/blocks and peaks, not global retention or RSS.

At 40x12, 31 samples per workload (three warmups), median/p95 End-event-to-buffer:

| Fixture | Body rows painted | Retained / examined | Median / p95 (microseconds) |
| --- | ---: | ---: | ---: |
| List, 64 rows | 11 | 64 / 64 | 598.2 / 1408.3 |
| List, 4096 rows | 11 | 4096 / 4096 | 514.3 / 1574.6 |
| Table, three columns | 10 | 4096 / 4096 | 765.0 / 2103.1 |
| Broad tree | 11 | 4096 / 4096 | 593.4 / 1634.7 |
| 100000-node source, count cutoff | 11 | 4096 / 4097 | 621.3 / 1575.2 |
| 10000-deep source, depth cutoff | 11 | 129 / 130 | 854.3 / 1675.4 |
| Canonical-byte cutoff | 11 | 23 / 24 | 553.8 / 1316.1 |

Broad count-capped admission median was 29.767 ms; its single root expansion
was 332.4 microseconds. Deep admission was
783.4 microseconds; 129 explicit expansions together took
1.793 ms. These windows differ from visible repaint.
The canonical-byte fixture admits 1036866 bytes but has a median
5467127 traced bytes retained and 6279250 peak, demonstrating why
payload caps are not heap caps. Three separate memory samples per case; shared
immutable fixture text is counted once in Python objects but per row in
conservative payload accounting. Background load, affinity and power were
uncontrolled; p95 dispersion does not establish a latency budget or cross-host comparison.

No scheduler pacing, renderer/output acknowledgement, real widget terminal trial,
human input, clipboard roundtrip, domain/application latency, accessibility or
usability claim follows. Existing automated native transport checks and this
virtual widget evidence remain separate from pending real-task acceptance.
