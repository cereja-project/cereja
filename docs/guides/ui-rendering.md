# UI diff, safe encoding and output transactions

`cereja.ui.rendering` implements [UI-06 / #300](https://github.com/cereja-project/cereja/issues/300)
on the existing [cell buffers](ui-buffer.md), [Unicode 17.0 policy](ui-text.md)
and [terminal sessions](ui-terminal.md). Import it explicitly. Runtime remains
stdlib-only on Python 3.11+; the UI namespace and terminal imports defer it.
Ledger remains the selected direction. [UI-07 scheduling](ui-scheduling.md) owns
event-driven frame requests and initial frame ceilings. Widgets, the Ledger
application and legacy display adapter belong to subsequent stages.

```python
from cereja.ui.buffer import CellBuffer, Rect
from cereja.ui.rendering import Cursor, Renderer
from cereja.ui.terminal import TerminalSession
from cereja.ui.testing import VirtualBackend

backend = VirtualBackend(size=(8, 2))
with TerminalSession(backend) as session:
    renderer = Renderer(session, verify_damage=True)
    frame = CellBuffer(8, 2)
    frame.draw_text(0, 0, "界 done")
    assert renderer.render(frame, cursor=Cursor(2, 1, True))
    counts = (len(backend.writes), backend.flush_count)
    assert renderer.render(frame.copy(), damage=[], cursor=Cursor(2, 1, True))
    assert (len(backend.writes), backend.flush_count) == counts
    frame.draw_text(1, 0, "x")
    assert renderer.render(frame, damage=[Rect(1, 0, 1, 1)])
    assert renderer.screen_known
    snapshot = renderer.front  # Immutable last successful effective grid.
```

## Full reference and dirty damage

`full_diff(front, back)` compares every cell's text, effective style and
occupancy. `front=None`, changed dimensions or changed `TextPolicy` returns
full-row runs. Results are immutable tuples of one-row `Rect` values, ordered
by row/column, closed over entire old/new wide-glyph footprints.

`dirty_diff(front, back, damage)` compares a clipped union of caller-supplied
rectangles expanded by one horizontal cell on each side. Overlapping intervals
are merged before comparison. Actual changes close over both frames' complete
wide footprints, including chains of shifted wide cells. Empty rectangles are
ignored. Resize, policy change and unknown front require a full diff regardless
of damage. Width/height zero are supported.

The caller owns scene damage: include old and new bounds for changed text/style,
occupied area, movement, removed layers and affected overlap/z-order. Damage is
an optimization assertion, not inferred scene state. `Renderer.render(frame)`
uses full diff by default; supplying `damage` selects dirty diff. In tests or
debugging, `verify_damage=True` compares the result with the full reference and
rejects incomplete damage before output. A caller that omits damage with this
check disabled can desynchronize its terminal. Use the default until damage is
complete. Composition itself still produces a complete frame.

## Effective frame and trusted encoder

Frames retain the #298 display graphemes and #299 occupancy; encoding never
resegments or recomputes their widths. Control safety is checked separately
from width. Ordinary ANSI/OSC, C0/C1, DEL, malformed surrogate and source bidi
input follows the shared text policy before buffer insertion. No raw escape
API or caller-supplied control strings are accepted by `Renderer`.

Styles are resolved before comparison. At depth 0, colors become terminal
defaults while flags remain semantic SGR attributes. Depth 16 or 256 maps
unsupported RGB/palette colors to the nearest fixed xterm palette RGB value
(squared RGB distance, lowest index breaks ties); this is deterministic, not a
perceptual color guarantee or a query of an emulator's configurable palette.
Truecolor retains RGB. Color changes with identical effective styles are no-ops.
When Unicode is disabled, construct the buffer with `TextPolicy(ascii_only=True)`;
a mismatched frame is rejected before I/O instead of silently reinterpreting
Unicode or retaining incompatible widths.

The internal encoder emits only its own CAN, CUP, SGR, ED, cursor visibility,
origin-reset and scroll-margin-reset controls. Full recovery starts with CAN to
cancel a possible fragmented encoder sequence, resets styles/origin/margins,
clears the viewport with `CSI 2 J`, then paints absolute positions. Incremental
transactions hide the cursor while painting and finish with default SGR and the
requested `Cursor(x, y, visible)` position/visibility. Cursor changes alone are
transactions; unchanged frame, capabilities, session generation and cursor
produce exactly zero writes and flushes.

Interactive frame dimensions must match `backend.dimensions()` and the cursor
must fit a nonempty viewport. Call `invalidate()` after untracked external
screen mutation. Suspension, other session output/renderers, capability changes,
resize and text-policy changes require a complete redraw on the next render.
Concurrent buffer mutation is outside this single-owner contract.

## Last column and bottom-right policy

Current capabilities do not attest safe DECAWM control or delayed autowrap.
The conservative fallback reserves the **entire final column** as default styled
blanks in interactive mode. A wide glyph touching that column becomes a styled
blank at its leader and a default blank in the reserved column. Full ED clears
the reserved column; subsequent transactions never print there. Cursor positioning
there is allowed. Width-one terminals therefore render a blank viewport.

The drawable area is `(width - 1) * height` cells. This deliberately sacrifices
one column on every row so neither immediate nor delayed autowrap can be triggered
by a printable character at the right margin, including the bottom-right corner.
No newline, ECH dependency or wrap-mode mutation is needed. Plain snapshots retain
all columns. A less conservative policy requires separate emulator/backend evidence.

The control subset follows the [xterm sequence reference](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html)
and [Windows VT documentation](https://learn.microsoft.com/en-us/windows/console/console-virtual-terminal-sequences).
The model tests enforce the policy under an immediate-wrap trap. They do not
prove every terminal/font agrees with frozen Unicode widths or implements the
control subset. Use explicit ASCII/plain fallback when capabilities are unsuitable.
Manual emulator, SSH, ConPTY and real-disconnection walkthroughs remain pending.

## Commit, failure and recovery

`Renderer.front` is the last successfully committed immutable effective grid.
It is historical after a fault; `screen_known` then returns false. A nonempty
transaction marks the session unknown before attempting transport. Only positive
integer character counts in `1..len(remaining)` confirm progress; the next write
receives exactly the unacknowledged suffix. Booleans, `None`, zero, negative,
oversized and other noninteger counts fail. Attempts are bounded by the finite
encoded string length. UTF-8 byte measurement is separate from this character
acknowledgment contract.

The front updates only after all characters and a successful flush. Virtual
`commit_cells` follows flush as an optional test hook; real transports do not
need it. Flush/write/hook failures retain the previous front, mark the screen
unknown and close/unwind the session. Broken pipe returns false if cleanup
succeeds; cleanup failure remains visible. Recovery acquires a new session and
renderer with an unknown front, which forces full redraw even with `damage=[]`.
There is no retry of an unknown failed transaction and no timeout promise for
an OS write that remains blocked.

Plain mode writes safe full snapshots with newline-separated rows and a trailing
newline, never terminal escapes or styles. Wide continuations are omitted, not
printed as padding. Cursor-only changes do no I/O. Unchanged frames do no I/O;
changed frames append a complete snapshot. An empty logical snapshot can commit
without transport because it contains no output. Snapshot ownership does not
depend on subsequent source mutation.

## Verification and measurements

```text
python -B -S -m unittest discover -s tests -p test_ui_rendering.py -v
python -B -S -m unittest discover -s tests -p 'test_ui_*.py' -v
python -B -S benchmarks/ui_rendering.py --samples 31
```

The [tests](../../tests/test_ui_rendering.py) include literal expected grids,
text/style/occupancy fixtures, right-margin widths 1/2/8, injection attempts and
short/invalid acknowledgments, write/flush/broken-pipe recovery and commit timing.
An independent VT subset decoder applies emitted sequences without calling buffer
painting, the encoder or diff; only frozen Unicode metrics are shared. It traps
printing at the last column and validates full text/style/occupancy grids.

Six seeds (`0, 1, 298, 299, 300, 104729`), 100 scene states each, compare full and
dirty runs, actual full/dirty encoded output and decoded expected grids through
overlap, text/style changes, movement, removal, z changes and resize. Another
360 incremental states use seeds `300, 1700, 104729` for clipped painting,
clearing, style/occupancy changes and resize. Failures name seed and step.

The [benchmark](../../benchmarks/ui_rendering.py) measures warm ASCII/default-style
80x24 frames, 1,896 drawable cells, contiguous row-major changes, caller damage,
and a hidden cursor at (0,0). Each workload warms once before 31 samples. Its
synchronous memory sink acknowledges a whole string, counts UTF-8 bytes and
performs a no-op flush. It retains counters rather than virtual output/history.
Imports and shared caches are warm; front setup is outside the timing windows.
Painting copies the source and changes cells; composition rebuilds one opaque
layer. Preparation copies and resolves the entire frame. Full diff is timed
separately on equivalent effective inputs; render uses dirty diff without oracle
checking. Instrumentation and snapshots contribute to total render time.

Measured on 2026-10-09, CPython 3.14.5, Windows 11 build 26200, 64-bit pointers.
Medians in microseconds (individual stage medians are not additive):

| Changes | Paint | Compose | Prepare | Full diff | Dirty diff | Encode | Render total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Unchanged | 7.4 | 879.0 | 714.7 | 499.8 | 2.8 | 0.6 | 753.2 |
| One cell | 12.3 | 883.8 | 725.5 | 486.3 | 7.1 | 4.6 | 781.2 |
| One row (79) | 69.7 | 868.6 | 677.6 | 496.5 | 34.3 | 30.3 | 785.4 |
| 10% (189, rounded down) | 162.4 | 919.1 | 646.1 | 511.1 | 79.7 | 67.3 | 839.8 |
| 100% (1,896) | 1,592.1 | 878.7 | 706.4 | 716.2 | 740.1 | 645.9 | 2,160.5 |

| Changes | UTF-8 bytes | Writes | Flushes | Memory write us | No-op flush us |
| --- | ---: | ---: | ---: | ---: | ---: |
| Unchanged | 0 | 0 | 0 | 0 | 0 |
| One cell | 33 | 1 | 1 | 0.4 | 0.1 |
| One row | 111 | 1 | 1 | 0.3 | 0.1 |
| 10% | 233 | 1 | 1 | 0.4 | 0.1 |
| 100% | 2,081 | 1 | 1 | 1.0 | 0.1 |

These windows exclude OS transport/emulators, SSH/ConPTY, input/layout/widgets,
diverse Unicode/styles, cold imports and application state. Sink timings include
counter/UTF-8 work and timer granularity, not system write/flush latency. The
render total excludes paint/composition and the separately timed full reference.
Dirty diff saves comparisons here, while preparation/composition still touch the
whole frame. No application performance, frame budget or cross-platform timing
claim follows. The delivery issue records the tested revision, review, CI and
human acceptance separately.
