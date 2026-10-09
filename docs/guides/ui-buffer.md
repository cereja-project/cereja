# UI cell buffers and composition

The independent `cereja.ui.buffer` module implements [UI-05 / #299](https://github.com/cereja-project/cereja/issues/299).
It uses the [frozen shared text policy](ui-text.md) for every grapheme and width.
Import it explicitly; importing `cereja`, `cereja.ui` or terminal transports
does not load buffers or Unicode data.

```python
from cereja.ui.buffer import CellBuffer, Layer, Rect, Style, compose

result = CellBuffer(8, 1)
result.draw_text(0, 0, "界 done", style=Style(foreground=2))
overlay = CellBuffer(1, 1)
overlay.draw_text(0, 0, "x")
frame = compose(8, 1, [Layer(result), Layer(overlay, x=1, z=1)])
assert frame.cell(0, 0).text == " "  # Replacing the continuation clears the leader.
assert frame.cell(1, 0).text == "x"
assert frame.size == (8, 1)
snapshot = frame.rows  # Immutable tuples of immutable Cell values.
```

## Cell and style values

`Cell.text`, `Cell.width` and `Cell.style` together define cell equality:

| Occupancy | Text | Width |
| --- | --- | --- |
| Narrow leader | Complete safe display grapheme | 1 |
| Wide leader | Complete safe display grapheme | 2 |
| Continuation immediately after a wide leader | Empty string | 0 |
| Blank | One ASCII space | 1 |

Continuations have the same effective style as their leader and are not
printable. `Cell` values are snapshots; buffer operations accept text or other
buffers, never caller-supplied cells or widths. Blitting copies the measured
display and occupancy directly, avoiding remeasurement of fallback text or
dotted-circle marks.

`Style` is immutable and fully resolved: `foreground` and `background` are
`None` (terminal default), palette indices 0..255, or RGB integer tuples with
components 0..255. `bold`, `dim`, `italic`, `underline`, `reverse` and
`strikethrough` are booleans. No field accepts a raw ANSI string. Composition
replaces the entire style; the caller resolves theme/inheritance first.
Capability fallback and escape encoding belong to the [renderer](ui-rendering.md).

Effective styles and immutable blank cells are shared through caches of at most
256 entries each. Live buffers keep their own references; equality is by value,
and object identity after cache eviction is not a public contract. Frame storage
is a flat owned list; repeated blanks share one immutable cell. Snapshots allocate
row tuples; `copy()` owns a separate storage list. Neither operation allows a
later mutation to alter an earlier snapshot or another buffer.

Dimensions are nonnegative integers (booleans are rejected). Zero-width frames
have `height` empty rows; zero-height frames have no rows, retaining their width
in `size`. `cell(x, y)` requires an in-bounds integer coordinate. `resized(width,
height, style=...)` returns an owned copy of the old intersection, preserving its
policy and styles and filling new area with the requested blank style. A cut
wide glyph becomes a blank with that glyph's style.

## Painting and clipping

`draw_text(x, y, text, style=..., clip=..., tab_size=4)` normalizes and measures
through `text_metrics` using the buffer's immutable `TextPolicy`. Controls,
source bidi visibility, isolated marks, ASCII fallback, ambiguous width and
RGI emoji therefore have exactly the #298 behavior.

Painting uses logical ordering without automatic wrapping. Coordinates may be
negative. LF advances one row and resets to the supplied x origin; TAB advances
to the next stop relative to each text line's column zero. These are layout
operations, never raw cells or terminal controls. This is the shared metrics'
zero-based text layout translated to the destination origin.

`Rect(x, y, width, height)` defines a half-open cell rectangle. Its origin may be
negative; its dimensions may be zero. The optional clip is in destination
coordinates and intersects the frame bounds. A grapheme intersecting either
horizontal clip edge becomes styled blanks in its visible cells. Clipping never
stores a partial cluster or an orphan continuation. Whole combining/ZWJ clusters
always travel with their shared-metrics display unit.

Replacing either half of an existing wide glyph first blanks its entire old
footprint with its previous style. The incoming content then writes its own
visible cells. This necessary occupancy cleanup can clear the neighboring cell
outside the requested clip; it does not paint the incoming glyph there.
`clear(clip=..., style=...)` obeys the same rule and writes opaque blanks.

`blit(source, x=0, y=0, clip=...)` copies an opaque source buffer. Source blanks
overwrite lower content. Source and destination policies must match; differences
raise `ValueError` instead of silently reinterpreting Unicode. A self-blit reads
a stable source snapshot, including when the rectangles overlap.

## Complete-frame composition

`Layer(buffer, x=0, y=0, z=0, clip=None)` places a buffer in destination space.
`compose(width, height, layers, policy=..., style=...)` creates a fresh background
and paints layers in ascending integer z order. Ties preserve iterable order;
later layers overwrite earlier layers, including their blanks. Every layer must
use the frame policy. There is no transparency or style blending.

Scene ownership remains with the caller. Move a layer by changing its placement,
remove it from the iterable, or change frame dimensions, then compose again.
Recomposition starts from the background, so removed/moved layers reveal the
remaining scene without retaining previous pixels. Do not mutate source buffers
concurrently with composition. Snapshots include the complete dimensions,
text, effective styles and occupancy required for subsequent full-frame diffing.

This stage does not write a terminal, track dirty regions, encode cursor state,
commit a front buffer or prevent emulator autowrap. The [renderer](ui-rendering.md)
owns those concerns. Ledger
and the independent core remain the approved direction; legacy display and
application features are unchanged.

## Verification and allocation baseline

```text
python -B -S -m unittest discover -s tests -p test_ui_buffer.py -v
python -B -S benchmarks/ui_buffers.py --samples 5
```

The [tests](../../tests/test_ui_buffer.py) include expected grids and a separate
sparse-glyph oracle with set-based visibility and whole-glyph removal. The oracle
shares only the approved Unicode metrics; it does not call buffer painting or
composition. It compares full text/style/occupancy grids at every step:

- 720 scene states: seeds `0, 1, 299, 298, 1700, 104729`, 120 steps each, including
  overlap, moves, removals, z-order changes and frame resize.
- 360 incremental states: seeds `299, 1700, 104729`, 120 steps each, including
  clipped painting, clearing and buffer resize.
- 3,360 exhaustive small overlap/clip geometries, plus named Unicode, zero-size,
  style, self-blit and immutable virtual-backend snapshot fixtures.

Failures identify the seed/step or geometry through unittest subtests. These
establish composition under the frozen policy, not emulator/font agreement.

Measured on 2026-10-09 with CPython 3.14.5, Windows 11 build 26200, 64-bit pointers.
The [benchmark](../../benchmarks/ui_buffers.py) reports median retained / peak
Python bytes from five separate `tracemalloc` windows. Imports and metrics/style
caches are warm before tracing; each sample collects garbage first. Blank frames
share immutable blank cells; dense ASCII paints every cell with `x` using one
default style. The two-frame workload allocates two independent blank buffers.

| Dimensions | One blank (retained / peak bytes) | Two blanks (retained / peak bytes) | Dense ASCII (retained / peak bytes) |
| --- | --- | --- | --- |
| 80x24 | 15,800 / 15,808 | 31,280 / 31,288 | 123,720 / 123,941 |
| 120x40 | 38,840 / 38,848 | 77,360 / 77,368 | 308,040 / 308,301 |
| 240x80 | 154,040 / 154,048 | 307,760 / 307,768 | 1,229,640 / 1,230,021 |

The baseline covers these isolated allocation workloads. It excludes cold imports,
cache initialization, snapshots, diverse text/styles, widgets, transport and
application state. Traced Python allocation is not process RSS, throughput,
frame latency or application performance. Other Python versions/platforms may
allocate differently; no application performance conclusion follows.
