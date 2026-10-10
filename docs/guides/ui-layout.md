# UI cell layout and scroll windows

`cereja.ui.layout` implements [UI-08 / #307](https://github.com/cereja-project/cereja/issues/307)
as the first increment under [#306](https://github.com/cereja-project/cereja/issues/306).
Import the module explicitly. It owns geometry, not widgets, keyboard input,
application state, content retention or terminal acquisition. Python 3.11+ and
standard-library runtime only. Existing [Rect/buffer clipping](ui-buffer.md)
and [renderer damage/resize](ui-rendering.md) remain the responsible boundaries.
No root or UI namespace re-exports are added.

## Partition and overflow contract

`Constraint(minimum=0, maximum=None, weight=1)` describes an axis in cells.
`Constraint.fixed(n)` reserves exactly n cells when space permits. Dimensions,
weights, padding and gaps are nonnegative integers; booleans are rejected.
Maximum cannot be smaller than minimum. Zero weight retains only the minimum.

`split_rows(bounds, constraints, gap=0)` partitions vertically;
`split_columns(...)` partitions horizontally. Each returns immutable `Rect`
values in input order. Nest by partitioning a returned rectangle. No layout
tree, persistent cache or content scan is required.

1. Reserve gaps, saturating their total at the available span.
2. Allocate minima in input order. Underflow clips later minima to remaining
   space; all rectangles stay inside bounds, including empty rectangles.
3. Distribute remaining cells by positive integer weight, fixing capped tracks
   first and redistributing surplus. Largest fractional remainder gets the
   spare cell; ties favor input order. Capped/zero-weight tracks may leave
   trailing unused space.

`inset(bounds, left=0, top=0, right=0, bottom=0)` applies padding. Its empty
result has an origin within the original bounds. Rectangles use zero-based,
half-open coordinates, including negative origins and zero dimensions.

## Selected Ledger allocations

Application policy reserves the final terminal column and switches to recovery
below 40x12. The generic partitioner does not enforce a product minimum.

```python
from cereja.ui.buffer import Rect
from cereja.ui.layout import Constraint, split_rows

width, height = 80, 24
header, results, pager, composer = split_rows(Rect(0, 0, width - 1, height), (
    Constraint.fixed(3), Constraint(minimum=4),
    Constraint.fixed(1), Constraint.fixed(4)))
assert results == Rect(0, 3, 79, 16)
assert pager == Rect(0, 19, 79, 1)
assert composer == Rect(0, 20, 79, 4)
```

| Size | Header | Result rows | Separate pager | Composer |
| --- | --- | --- | --- | --- |
| 120x40 | 0..2 | 3..34 (32) | 35 | 36..39 (4) |
| 80x24 | 0..2 | 3..18 (16) | 19 | 20..23 (4) |
| 40x12 | 0..2 | 3..6 (4) | 7 | 8..11 (4) |

Overlays partition the result region into title=1, fields=remaining and
actions=1, giving 30/14/2 field rows. They cannot paint into the pager/dock
when the caller passes the intersected destination clip. Padding/color/focus
choices belong to later components. Below the product minimum, preserve edit,
focus, selection and scroll state and display recovery; do not use generic
minimum clipping as the normal application layout.

## Lazy viewports and selection on resize

`Viewport(rect, content_width, content_height, scroll_x=0, scroll_y=0, clip=None)`
stores dimensions and requested cell offsets, without retaining or inspecting
content. `offset` clamps to current content/window sizes. Requested offsets are
preserved through zero/hidden dimensions so recovery can restore the anchor.
`resized(rect, clip=None)` preserves them; supply the newly computed ancestor
clip, because the old clip may belong to the previous layout.

`visible` is a content-space rectangle after ancestor clipping. `origin`
translates content to destination coordinates. `clip_rect` is the intersection
of the window and optional destination-space ancestor clip. Use these with
existing buffer painting, requesting only visible rows/items from the source:

```python
from cereja.ui.buffer import CellBuffer, Rect
from cereja.ui.layout import Viewport

frame = CellBuffer(40, 12)
view = Viewport(Rect(2, 3, 36, 4), 100, 1000000, scroll_y=71)
view = view.ensure_visible(Rect(0, 74, 1, 1))
ox, oy = view.origin
for row in range(view.visible.y, view.visible.y + view.visible.height):
    frame.draw_text(ox, oy + row, f"synthetic row {row}", clip=view.clip_rect)
assert frame.cell(2, 8).text == " "  # No painting in the composer.
```

`scrolled(dx=0, dy=0)` moves from effective offsets and clamps; an empty
destination clip is a no-op. `ensure_visible(target)` takes a content-space
rectangle within the declared content dimensions. Oversized targets align
their start. Hard ancestor clips/content bounds can prevent full exposure;
it never promises visibility of a target larger than its window.

Selection identity and logical text offsets stay with the caller. After resize,
resolve the retained selected/focused item into its current content rectangle
and call `ensure_visible`; never infer identity from terminal row coordinates.
The layout does not change drafts, carets, focus, clipboard selections or
follow-latest. Soft wrapping/reflow and key/focus traversal are later widget
responsibilities. Bound fetched row text separately; a lazy geometry window
does not make the existing text-metrics call independent of line length.

## Bounded damage and verification

`layout_damage(before, after, bounds, max_regions=64)` compares old/new geometry
by stable slot order. It returns nonempty clipped old/new rectangles, including
removed/moved regions. Duplicate rectangles are omitted; exceeding the region
limit falls back to one full bounds rectangle. The default 64 is a structural
count limit for this helper, not a measured application rendering budget.

Identical geometry returns no damage. Content, style, scrolling, layering and
replacement at unchanged geometry need caller-supplied damage. Combine those
regions and use `Renderer(verify_damage=True)` while validating components.
The existing renderer still invalidates on resize/policy changes and closes
damage over wide-glyph footprints. No idle redraw or timer is introduced.

Geometry work depends on the number of tracks/regions, not content length;
capped weighted allocation takes at most a track-count number of rounds.
Viewport geometry is constant space. No huge content buffer is allocated.

Run the bounded example (ASCII, no color, no interaction or domain execution):

```text
python -B -S benchmarks/ui_layout.py --demo --size 40x12 --selected 71
python -B -S benchmarks/ui_layout.py --demo --size 32x10
python -S -m unittest tests.test_ui_layout tests.test_ui_imports tests.test_ui_buffer tests.test_ui_rendering
python -B -S benchmarks/ui_layout.py --samples 31 --memory-samples 7 --output layout-report.json
```

The [retained baseline](../../benchmarks/ui_layout_samples/baseline-windows-py314.json)
freezes 100 iterations/sample, the three accepted sizes, 256 logical columns,
one million synthetic logical rows and target row 800071. It measures geometry
resize and target/visible/damage calculations; it constructs no million-row list.
Raw samples, dispersion, untimed traced Python memory and source fingerprints
are retained. Dirty working-tree provenance is explicit; normalized LF hashes
identify the measured sources. This is no rendering, input, clipboard, RSS,
domain, real-terminal or end-to-end latency result, and does not alter #304
budgets. Actual application/host/human acceptance remains pending under #321.
