# Inline status, progress and activity

UI-12 / [#311](https://github.com/cereja-project/cereja/issues/311) adds opt-in
`cereja.ui.feedback`. Python 3.11+, standard library only. Importing it starts
no timer, worker, terminal session or operation. The
[accepted effect decisions](../design/cereja-ui-ux.md#motion-loading-and-feedback-policy)
remain in force. This is toolkit delivery, not the Ledger application.

## Public API and truthful data

- `InlineStatus(identity, state, message)` and `update(state, message)`:
  persistent textual Loading, Empty, Error, Done, Warning, Idle or Canceled.
  States are `loading/empty/error/success/warning/idle/canceled`.
  Updates replace content immediately, without auto-dismiss or focus changes.
- `ProgressBar(identity, message, completed=None, total=None, reliable_total=False)`
  and `update(message, ...)`: integer counts in 0..2**63-1. A determinate bar
  requires 0 <= completed <= total, total > 0, and explicit `reliable_total=True`
  on each update. The caller must have measured the count and established the
  denominator; this API cannot certify either. Invalid, fractional, untrusted or
  unknown totals produce no bar/percentage. Valid completed counts remain useful.
  `determinate` and integer floor `percent` (or None) are read-only. 100% of a
  count does not claim operational success. No speed, ETA or Cancel is invented.
- `ActivityIndicator(loop, identity, message, active=False, kind='spinner', motion=True)`:
  one spinner OR dots for confirmed active loading. No timer before visible paint.
  `update(state, message, active=False)` requires a fresh explicit activity
  assertion; only loading can be active. Completion/cancellation is a caller
  report, never a command to an operation.
- `set_visible(bool)`, `set_motion(bool)`, `close()` on an indicator stop its
  decorative deadline immediately. Close is idempotent. Re-show/re-enable requires
  a paint; no background poll waits for visibility to change.
- `paint(frame, rect, clip=None)` clears and paints one clipped row, returning its
  damage Rect. It uses the existing safe Unicode metrics, tab stops and whole-glyph
  cell clipping. The full message stays inspectable in `content`; a multiline
  message displays its first line. Callers allocate sufficient room for labels and
  numbers and can show the full canonical content in their existing detail surface.
- `content` is existing immutable `TextContent`, with stable identity and a new
  revision only when safe canonical text changes. Displayed bars, marker frames,
  padding, clipping and soft wrapping never enter its copy payload. Canonical
  messages preserve tabs, newlines and intentional spaces; unsafe controls are
  escaped. Admission rejects more than 64 KiB of canonical UTF-8 atomically;
  identities are at most 4096 UTF-8 bytes. These are component bounds, not a
  total application memory or retention guarantee.

Mutation and painting belong to the creating UI thread. These components own no
key handling, selection, focus, scroll, composer, suggestions or confirmation.
`handle(event)` on an indicator accepts only its current TimerEvent and returns
whether its row changed. Keep text selections bound to `content` with existing
`TextSelection/copy_action`; retain older selected revisions within the caller's
existing retention policy. Ctrl+C/copy failure behavior remains owned by the
key-owning surface. No clipboard transport or native selection detection is added.

## Scheduling, dirty rows and fallbacks

Each active, visible indicator owns one bounded decorative timer in the existing
EventLoop. `owner` is a unique timer routing key even when content IDs coincide;
`timer_id` becomes None after cancellation. Route events using an owner dictionary,
not by scanning every widget. `motion_notice` reports exhausted timer capacity.
A full scheduler leaves the truthful static state visible and retries only on
the next explicit paint.

This reuses the existing 1024-timer/1 MiB-owner limits, deterministic heap,
64-callback/4 ms turn budget and late-frame skipping. A separate group scheduler
would duplicate lifecycle/limit policy; an unbounded all-widget callback would
bypass the existing per-turn budget. Callbacks remain non-preemptive. A large
collection is bounded work, not a promise of one-turn completion.

The EventLoop now exposes `indicator_interval` (0.125 or 0.5 seconds) and
`has_timer(id)`. `spinner=True` enforces 8 Hz local/2 Hz low-bandwidth intervals.
Frame ceilings remain 30/4 Hz. These are existing candidate ceilings, not measured
optimal rates. No SSH detection is assumed; use `EventLoop(..., low_bandwidth=True)`.
`set_reduced_motion(True)` removes decorative deadlines and pending decorative-only
frames. Coalescing decoration over real data retains the pending real update.

The caller repaints only changed rows, composes its full current CellBuffer and
calls `request_render(frame, cursor=current_cursor, decorative=True)` for pure
motion. Aggregate dirty rows before submitting once per turn. Real data, visibility,
layout, motion-policy or completion changes use `decorative=False`. EventLoop still
uses its existing full-buffer diff and one latest-frame snapshot; this increment
does not change its renderer damage API. Direct Renderer users may pass returned
rectangles as damage, including old/new geometry damage on moves.

Paint on resize/policy changes to synchronize actual clipped visibility. Remove
or hide indicators explicitly when a view stops painting. Completion, cancellation,
hide, disposal and clipped-away markers remove their timers. EOF, broken output,
handler failure and loop close use EventLoop's existing terminal cleanup.
The owner of an externally closed session must also close its EventLoop.

Motion off, reduced motion, unsupported cursor capability and plain mode allocate
no animation timers. Idle views request no periodic renders or writes. Dots use a
fixed three-cell marker plus one separator; spinner shares that allocation.
Color, Unicode and motion are independent: ASCII/no-color do not imply motion off.
Use `TextPolicy(ascii_only=True)` for an ASCII-only renderer. Plain preserves
state/counts and emits only real updates; it emits no animation history or controls.
These widgets do not store frame history.

## Effect disposition and examples

| Effect | Delivery and static equivalent |
| --- | --- |
| Spinner or dots | Confirmed activity only, one indicator per activity; Loading plus message is always meaningful. Dots never reflow. |
| Determinate progress | Real counts and trusted total only; numeric state survives reduced/plain output. |
| Indeterminate bar | Optional demonstration concept, not the default and no separate API added. Spinner/dots supply the selected active-work example. |
| Pulse | Deferred. Persistent labelled state; no color-intensity timer. |
| Shimmer | Off and unimplemented pending demonstrated benefit. No shimmer-specific core API. |
| Skeleton | Static Loading placeholders only for explicitly known slots. The demo labels a synthetic CPU slot, without invented values, rows or counts. |
| Blink | Existing host cursor only. Pass the existing editor cursor on redraw; no second caret timer. Host blink/steady support remains host-owned. |
| Transitions | Immediate replacement. Composer, focus, content selection and navigation anchors are independent. |
| Success/warning/error | Persistent useful messages. No automatic dismissal, shake or flash. |
| Typewriter/stagger/glow/fade/slide | Not implemented or selected as defaults. Any later opt-in proposal still needs capability and reading-stability evidence; static full text is the fallback. |
| Temporary highlight | Optional in the design, not implemented here. Persistent Updated text needs no timer. |

The issue's broad effect list is covered by these dispositions, not authorization
to implement every effect. There is no remaining decision needed for this scope.

This executable example uses fixed, explicitly synthetic counts and exits:

```python
from cereja.ui.buffer import CellBuffer, Rect
from cereja.ui.feedback import ActivityIndicator, ProgressBar
from cereja.ui.scheduling import EventLoop
from cereja.ui.terminal import TerminalSession
from cereja.ui.testing import VirtualBackend

backend = VirtualBackend(size=(80, 3))
with TerminalSession(backend) as session:
    loop = EventLoop(session, lambda event: None, clock=backend.clock)
    try:
        loop.set_reduced_motion(True)
        activity = ActivityIndicator(loop, "demo", "Synthetic known work", active=True)
        frame = CellBuffer(80, 3)
        activity.paint(frame, Rect(0, 0, 79, 1))
        assert loop.timer_count == 0
        ProgressBar("counts", "Synthetic replay", completed=3, total=8,
                    reliable_total=True).paint(frame, Rect(0, 1, 79, 1))
        activity.update("success", "Synthetic complete")
        activity.paint(frame, Rect(0, 0, 79, 1))
        activity.close()
        loop.request_render(frame)
        loop.turn()
        assert loop.timer_count == 0
    finally:
        loop.close()
```

`python -B -S benchmarks/ui_feedback.py --demo` prints one final snapshot.
`--motion --kind dots` exercises four virtual deadlines and still prints only
the final state. `--plain` and `--low-bandwidth` are explicit. These examples
do not perform a domain operation or claim terminal/human acceptance.

## Verification and measured boundaries

`python -B -S -m unittest tests.test_ui_feedback tests.test_ui_scheduling -v`
covers truthful progress, independent interaction state, UI ownership, clipped
visibility, lifecycle, capacities, ordered input, motion switches and coalescing.

`python -B -S benchmarks/ui_feedback.py --output report.json` measures 31 samples
after three warmups for 1/16/64/256 indicators, local/low-bandwidth/off/plain and
two distinct paths: scheduler to CellBuffer and scheduler/renderer to an in-memory
sink. Each sample has four virtual intervals and an idle check after completion.
Creation, active computation, disposal, timers, paints, turns, renders, writes,
flushes and UTF-8 bytes are separate. The 256-row canvas is synthetic stress.
Median, nearest-rank p95, MAD, range and raw samples are retained in
[the frozen baseline](../../benchmarks/ui_feedback_samples/baseline-windows-py314.json).

Virtual deadlines make workload and counts deterministic. Elapsed compute uses
perf_counter_ns; it excludes real waiting. This is not a measured real-time 4 ms
budget guarantee, transport/terminal latency, human input, clipboard, accessibility,
domain/application/RSS or global memory validation. The virtual test sink retains
test output; that instrumentation is not toolkit plain-frame history. See the
baseline environment and source fingerprints for the exact measured conditions.
Real terminal widget walkthrough and human usability acceptance remain pending.
