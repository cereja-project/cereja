# UI events, bounded posting and timers

`cereja.ui.scheduling` implements [UI-07 / #301](https://github.com/cereja-project/cereja/issues/301)
under [design section 5](../design/cereja-ui.md#5-events-timers-cancellation-and-pressure).
Import it explicitly. Python 3.11+, stdlib-only, no workers at import time.
Ledger remains the selected direction. Widgets, domain operations and legacy
display integration belong to their own deliveries.

```python
from cereja.ui.events import ResultEvent
from cereja.ui.scheduling import EventLoop
from cereja.ui.terminal import TerminalSession
from cereja.ui.testing import VirtualBackend

backend = VirtualBackend()
with TerminalSession(backend) as session:
    received = []
    loop = EventLoop(session, received.append, clock=backend.clock)
    request = loop.begin_request("search")
    assert loop.post(ResultEvent("search", request.generation, "complete"))
    loop.turn()  # One bounded, nonblocking turn on the UI thread.
    assert received == [ResultEvent("search", request.generation, "complete")]
    loop.close()
```

## Ownership and results

Construct the loop inside an active `TerminalSession`. The session's UI thread
alone runs handlers, creates/cancels timers, changes request presentation state,
requests frames and closes the loop/session. Producer threads can call `post`,
`wait_post` and `request_shutdown`. Handlers receive normalized immutable events;
a `PasteEvent` remains a single text value, including embedded control characters.
It is never expanded into keys or shortcuts. Input errors reach the handler.

Every `ResultEvent` has a positive request generation obtained from
`begin_request(source)`. Results with unknown, superseded, forgotten or cancelled
generations are suppressed before invoking the handler. Progress for a managed
request must carry its generation too; unregistered standalone progress may use
generation zero. Coalescing includes the progress generation, so stale progress
cannot replace a current generation's slot. Generations are never reused within
a loop, even after `forget_request(source)`.

`cancel_request(source)` stops presentation only. Pass `cooperative=True` solely
when the caller has a proven safe interruption path that observes the returned
`Request.cancellation` token. `Cancellation.cancel()` signals and wakes capacity
waits; it never kills a thread. Suppression, signalling and actual worker exit are
different observations. Superseding/forgetting a request retains no old token in
the loop; the caller owns its token and worker cleanup. Close signals current
request tokens, releases queue waiters and closes the session, without joining
workers. The application must bound outstanding workers/requests and observe their
actual completion, especially for blocking synchronous services. This core starts
no worker and establishes no domain cancellation guarantee or Cancel control.

The current request registry holds at most 1,024 source entries and 1 MiB of
source-name UTF-8, independently of the posted inbox. Forget completed sources.
Each name is at most 4 KiB. Exhaustion raises `OverflowError` before replacement.

## Inbox and accounting

The default inbox admits at most **1,024 envelopes and 1 MiB of aggregate
UTF-8/raw bytes**, including coalesced slots. Constructor limits may be reduced,
never increased beyond these policies. Strings/bytes are immutable values;
subclasses and arbitrary containers, callbacks or Python object graphs are
rejected. There is no external result-reference store. Large application results
need a separate finite store with an explicit release path before such references
can be introduced. These are logical content limits, not Python-heap guarantees.

| Event | Charged variable content | Bounded fixed content |
| --- | --- | --- |
| Key | UTF-8 key, text and modifier names | Positive repeat, three supported modifiers |
| Paste | UTF-8 text (at most 1 MiB per paste) | None |
| Resize | Optional UTF-8 posting source (at most 4 KiB) | Nonnegative width/height |
| Focus | None | Exact Boolean |
| Progress | UTF-8 source and message | Nonnegative completed, optional real total, generation |
| Result | UTF-8 source plus UTF-8 text or raw bytes | Positive generation, None/Boolean/finite float/signed integer |
| Timer | UTF-8 owner | Positive identity and finite deadline/current time |
| InputError | UTF-8 message | None |
| Wake, EOF | None | No payload |
| Quit | UTF-8 reason in the reserved signal (at most 4 KiB) | No queued envelope |

Integers are bounded to signed 64-bit ranges; nonnegative fields use
`0..2**63-1`. Floats are finite. Each variable text field is checked before
encoding, and the aggregate cost is checked atomically at admission.
`payload_bytes(event)` exposes the typed accounting for verification. Unknown
event types, subclasses and invalid fields raise. Oversized inbox payloads or
saturation make `post` return false without retaining the rejected event.
The producer must handle that failure; there is no silent retry or ordered drop.

`wait_post(event, cancellation=token)` is worker-only. It sleeps on a condition
until capacity, cancellation or shutdown, without polling. Never call it from
the UI thread, even if space currently exists. Producer-owned retry payloads
remain outside the inbox budget while waiting; the caller must bound producers.
Queue consumption, smaller coalesced replacements, shutdown and token
cancellation notify capacity waiters. A single native wake signals admitted work.
An OS wake error after admission remains in `loop.wake_error`; admission stays
committed and must not be retried as a new event. A failed OS wake does not prove
a blocked native waiter resumed. Cleanup/host recovery remains necessary.

Only same-source resize and same-source/generation progress replace a queued
slot, in place, with both budgets enforced. Keys, paste, focus and results retain
FIFO order. Quit uses `request_shutdown` independently of inbox saturation;
its first bounded reason wins and new admission stops. The reserved reason is
separate from queued payloads. `post(QuitEvent(...))` uses this signal too.
Shutdown cancels pending presentation rather than draining queued actions.

## Native admission and fairness

Each turn checks shutdown and native readiness, delivers at most 64 retained
native events in order, then handles at most **64 posted events or 4 ms** of
producer callbacks. It checks shutdown between callbacks and due timers after
that bounded producer work. Timer dispatch has the same 64/4 ms work bound.
These checks do not preempt a running callback. Callbacks must return promptly.
Ordered input already ahead of a key remains ahead of it.

One finite native read is retained until delivered. POSIX reads at most 4 KiB,
with the existing parser's at-most-1-MiB partial paste and 4-KiB encoded-sequence
limits; Windows reads at most 128 records, without expanding key repeat counts.
New native admission pauses while the retained batch is nonempty. Wake/resize
notifications still work. POSIX temporarily removes input readiness from the
selector; Windows waits on just the wake handle. This preserves input order
and avoids growing the backlog via repeated OS reads. It does not promise
lossless unlimited typeahead: OS buffers are finite and overflow is reported
only where the transport exposes a detectable failure.

Windows also inspects ready records when the wake handle wins selection,
using [GetNumberOfConsoleInputEvents](https://learn.microsoft.com/en-us/windows/console/getnumberofconsoleinputevents).
Continuous producer wakes therefore cannot hide ready keyboard input. The
legacy Windows paste ambiguity remains documented in [terminal input](ui-terminal.md).
Oversized paste/sequences retain the parser's atomic rejection and consume-through
behavior, without replaying remaining bytes as shortcuts.

With no ready work, `run()` blocks until the earliest timer/render/input deadline,
or indefinitely if there is none. Plain streams use the inbox condition, without
raw input acquisition or animation. There is no periodic idle redraw or polling
timer. Native readiness checks at the start of active turns are not an idle
polling loop. `turn(block=True)` provides the same wait for embedding. The
virtual backend records an infinite wait and returns immediately for deterministic
tests, so use individual virtual turns for idle checks rather than an idle `run()`.

## Timers and output

`call_later(delay, owner=..., interval=None, decorative=False, spinner=False)`
uses a monotonic heap with insertion identity breaking deadline ties. A delayed
repeat emits one `TimerEvent` with current time, then schedules from current time
after the callback. Missed states are not replayed. Timer storage has independent
limits of 1,024 entries and 1 MiB owner-name UTF-8; cancellation eagerly removes
heap entries and releases owner references, with no long-lived tombstones.

Call `cancel_timer(id)` or `cancel_owner(name)` on removal/hiding. This is an
ownership hook, without implementing widgets. `set_reduced_motion(True)` removes
decorative timers and pending decorative frames; real progress/frames continue.
When a decorative snapshot coalesces over pending real data, the latest frame
retains the real-data obligation and survives motion-off. Plain sessions reject
decorative timers/frames. Repeated decorative timers respect
the frame ceiling; spinner additionally uses at most 8 Hz locally and 2 Hz in
low-bandwidth mode. These remain candidate ceilings. The read-only
`indicator_interval` exposes that minimum interval; `has_timer(id)` checks live
membership after cancellation. Reusable widgets are in [inline feedback](ui-feedback.md).

`request_render(frame, cursor=..., decorative=False)` keeps a UI-owned copy of
one latest complete frame. Render starts are limited to 30 Hz locally or 4 Hz
with `low_bandwidth=True`. These are initial policies, not sustained-throughput
claims. Repeated requests replace the pending frame, rather than queueing stale
frames. Rendering uses the existing [renderer transaction](ui-rendering.md): an
unchanged frame/cursor/session writes and flushes nothing, the front commits only
after complete acknowledged output and flush, and failure invalidates the screen.
No timeout is promised for an OS write that stays blocked.

`loop.metrics` is an immutable snapshot of turns, waits (including zero-time
readiness checks), blocking waits, admission pauses, native/posted/timer events,
suppressed results, render attempts, session write/flush attempts, capacity waits,
rejections and replacements. Write attempts include partial/failing acknowledgments;
flush attempts include failed flushes. Session counters exclude native acquisition
and restoration controls. Cleanup failures remain in `session.cleanup_failures`;
an initiating callback/output error retains its identity and receives cleanup notes.

## Verification and measurements

```text
python -B -S -m unittest discover -s tests -p 'test_ui_*.py' -v
python -B -S benchmarks/ui_scheduling.py --transport virtual --samples 1
python -B -S benchmarks/ui_scheduling.py --transport windows --samples 5
python -B -S benchmarks/ui_scheduling.py --transport posix --samples 5
```

The [deterministic tests](../../tests/test_ui_scheduling.py) cover all event costs,
both saturation bounds, coalesced replacement rejection, cancelled/forgotten
generations, all 10,000 ordered results, next-turn key/Quit inspection, the 4 ms
budget, timer ties/late repeats/storage release, plain/reduced motion, frame
ceilings, partial writes and cleanup failures. Existing input tests continue to
cover paste and encoded-sequence rejection without shortcut replay.

The [shared native probe](../../tests/ui_scheduling_probe.py) performs an
indefinite wait with a synchronized worker wake, 10,000 ordered results from a
capacity-waiting worker, key injection at result 64, then full-queue shutdown
with a blocked producer and pending timer. The console/PTY tests check native
resource restoration too. The [benchmark](../../benchmarks/ui_scheduling.py)
prints raw samples and counters; it asserts ordering/fairness, without setting
an absolute input-latency pass threshold.

Measured on 2026-10-09, CPython 3.14.5, Windows 11 build 26200, isolated hidden
console. Five raw samples, milliseconds:

| Sample | Native injected key to handler | Idle post to handler | 10,000-result pressure |
| --- | ---: | ---: | ---: |
| 1 | 0.5593 | 0.1924 | 71.6949 |
| 2 | 0.5270 | 0.1816 | 69.8196 |
| 3 | 0.5521 | 0.2125 | 64.3504 |
| 4 | 0.5486 | 0.1348 | 63.5615 |
| 5 | 0.5638 | 0.1397 | 67.5104 |

Key median: 0.5521 ms. Idle-post median: 0.1816 ms. Every key was inspected in
the next turn (2 to 3 or 3 to 4). The cumulative pressure snapshots had 158-159
turns, 160-163 waits, 2-4 blocking waits, 10,001 posted events (one idle focus
plus 10,000 results), 104-131 native events (including wakes), 82-119 capacity
waits and zero renders/writes/flushes. The idle phase made exactly one indefinite
wait, with zero renders/writes/flushes. Shutdown added one turn, rejected the
waiting producer, released queue/timers, signalled current tokens and observed
both test workers exit. The fake-clock probe delivered all 10,000 results in
157 pressure turns and inspected the key on the next turn, with zero output.

Instrumentation, in-process OS injection, Python thread scheduling and this
small fixed callback contribute to these measurements. They do not establish
human-keyboard, application, diverse callback, emulator, SSH or ConPTY latency,
nor cross-platform throughput. POSIX PTY integration is checked on its native
CI hosts; their performance requires separate samples. Manual emulator, SSH,
ConPTY and real-disconnection walkthroughs remain pending. The issue owns the
tested/reviewed tree, delivered commit, actual CI result and human acceptance.
