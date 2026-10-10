# Background operation lifecycle

APP-00 / [#312](https://github.com/cereja-project/cereja/issues/312) adds opt-in
`cereja.ui.operations`. Python 3.11+, standard library only. Importing it starts
no threads or terminal resources. This is a toolkit bridge and bounded synthetic
demonstration; the Ledger application and official `cereja ui` remain unimplemented.

## Public API and ownership

Create one `OperationBridge(loop, source)` for the application's single operation
slot. The source is nonempty, at most 4096 UTF-8 bytes, and belongs exclusively to
that bridge. All controller methods/properties belong to the creating UI thread.

- `start(name, operation, cleanup=None, cancellation=None)` starts an explicit
  operation and returns its request generation. A second start raises
  `OperationBusy` while work, cleanup or final delivery owns the slot. There is
  no job queue and no automatic retry/start after completion.
- `operation(context)` runs on the domain worker and returns only exact
  str/bytes/int/float/bool/None values. Integers fit signed 64 bits and floats
  must be finite. Collections, arbitrary objects and subclasses are rejected.
  Adapt structured domain results explicitly into bounded values in a later
  integration; the bridge does not accept external result-store references.
- `cleanup()`, if supplied, executes once on the same worker after operation
  success, failure or cooperative stop. It must resolve only owned resources and
  report failures. A worker that never started acquired no adapter resources and
  does not invoke cleanup. The adapter owns resource acquisition and cleanup
  completeness; the bridge cannot inspect domain resources.
- `OperationContext.running()` reports completed adapter validation and actual
  work beginning. `committing()` reports entry into an actually observed commit
  phase, excluding cancellation atomically. Do not call it when a service exposes
  no such boundary. Returning without observing Running is a Failed contract.
- `context.progress(completed, total=None, reliable_total=False, message='')`
  accepts actual nonnegative 64-bit counts. Only explicitly trusted totals travel
  to the UI; unknown/untrusted totals remain None. A supplied trusted total must
  be nonnegative and at least completed. A zero total produces no percentage in
  ProgressBar. Message limit: 4096 UTF-8 bytes. This nonblocking post returns False
  on saturation/closed consumer; it never advances a synthetic count.
- `snapshot` returns immutable `OperationSnapshot`: source, generation, name,
  state, active, cancellable, worker_exited, delivery and outcome. It retains only
  the latest operation, including an outcome unavailable to the UI consumer.
  Explicitly starting another operation replaces that receipt; there is no
  historical retention or disk history.
- `handle(event)` belongs in the UI handler. It recognizes its current
  generation, consumes the exact final event once and returns whether it accepted
  the event. It does not draw or handle keys. A delivered receipt means this
  bridge consumed the event, not that a downstream callback or terminal paint
  succeeded. Do not repost final events.
- `close()` disposes the consumer, suppresses its owned request and wakes blocked
  publication. It is idempotent and never joins or kills domain work. Use it in
  the UI's finally block, followed by `loop.close()`.

The bridge owns at most one domain worker and one completion observer. The
observer is created lazily, joins the domain worker off the UI thread, publishes
its final event, then sleeps on a condition between operations. It has no polling
timer. Disposal wakes that condition. Loop shutdown also signals the existing
request token, releasing an idle observer or a publication wait. A blocked domain
worker can keep the observer waiting until the domain returns; no deadline is
promised. Threads are non-daemon: process exit is not treated as successful cleanup.

Callbacks and domain closures are trusted application code. The bridge cannot
sandbox a malicious worker or bound its allocations. Context mutation rejects
foreign threads; workers receive no presentation API. Never capture a renderer,
terminal or widget in an adapter.

## Lifecycle, completion and cancellation

The approved lifecycle is `Idle -> Validating -> Running -> Committing -> Succeeded`,
with distinct `Failed` and `CleanupFailed`. Committing appears only when explicitly
observed by the adapter. Validating begins when the worker enters its invocation;
no domain validation success is inferred from starting a thread.

A returned value is provisional until cleanup returns and the observer confirms
the domain thread exited. Only then is a terminal result/error published. Cleanup
failure after an observed commit is still CleanupFailed and never implies rollback.
Its error event retains the bounded result when it fits, plus `result_available`
and the last observed phase; if combined diagnostics/result exceed the event limit,
the event explicitly reports result omission. Primary and cleanup diagnostics
are separate. Error messages use bounded exception class/first-string-argument
text, without retained traceback graphs or arbitrary exception string callbacks.

The slot remains busy until worker exit and final consumption. Suppression by
generation does not release a running worker. After exit, suppressed/unavailable
publication is explicit in the retained receipt and permits an explicit new start
on a live consumer. Delivery values are `none/pending/queued/delivered/suppressed/
unavailable/publication_failed`. Queued means admission, not consumption. Final
publication failure never triggers an automatic retry that could duplicate an
uncertain admission. Inspect `loop.wake_error` for an admitted event whose backend
wake reported failure.

Cancellation is off by default. An adapter may supply
`CooperativeCancellation(evidence)` only after its domain tests establish safe
checkpoints, interruption behavior and owned cleanup. This bounded evidence string
is an assertion/reference, not a certification performed by the bridge. No existing
Cereja service is certified by the synthetic fixture.

`cancel()` returns whether it requested cooperation and changes the snapshot to
CancelRequested. This immediate UI-owned state needs no inbox capacity. The adapter
calls `context.checkpoint()` only at a validated safe boundary. Acknowledgement
through that checkpoint, successful cleanup and actual worker exit are all required
for Cancelled. A request arriving after the last checkpoint can finish Succeeded;
cleanup failure yields CleanupFailed. While committing or settling a returned
operation, Cancel is unavailable. Publication cancellation uses the existing
Request token; domain cancellation has a separate Cancellation signal. Loop close,
stale generations, discarded results, callback errors and process termination never
stand in for a domain acknowledgement.

## Exit, navigation and feedback

`exit_choices` offers return/wait during noncancelable work, adding cancel only
while the validated capability is usable. `request_exit('return')` is the default
and withdraws a previous wait-to-exit decision. `request_exit('wait')` leaves the
UI running and requests loop shutdown after consuming final delivery.
`request_exit('cancel')` first requests supported cooperation, then waits through
the same completion path. `request_exit('exit')` rejects active work.

Ordinary quit keys must route through this decision BEFORE calling EventLoop's
`request_shutdown` or posting QuitEvent (those are unconditional shutdown signals).
EOF, terminal loss and externally forced loop shutdown can make final delivery
unavailable. The receipt remains inspectable; it does not claim the worker stopped.
If a producer reports publication_failed, show that receipt on the next explicit
UI action and let the user retry the exit decision after work exits. No periodic
poll disguises a dead consumer as a working one.

Navigation never calls cancel/close. Keep a single bounded status row owned by the
application while screens change. Route accepted events/snapshots to InlineStatus,
ProgressBar and ActivityIndicator from the UI thread, and aggregate changed rows
before `request_render`. Running/Committing are observed activity; count completion
alone is not success. Stop the indicator at terminal outcomes and dispose it in
finally. The existing 30/4 Hz frame and 8/2 Hz indicator ceilings remain candidates.

The bridge owns no composer, focus, selection, scroll, confirmation or clipboard.
Ctrl+C with textual selection stays with the existing copy action, including copy
failure; it is never implicit worker cancellation. Safe TextContent, logical copy
offsets and stable identity/revision continue to belong to the existing components.
Color, Unicode and motion remain independent; ASCII/no-color, reduced motion and
plain output retain textual operational truth.

## Admission and storage bounds

Events live in `cereja.ui.events`: OperationStartedEvent, OperationPhaseEvent,
existing ProgressEvent, OperationResultEvent and OperationErrorEvent. They are
widget-independent frozen values. Lifecycle events carry source/generation;
OperationStartedEvent also carries name/cancellable, phase events carry the
observed phase, results carry Succeeded/Cancelled plus value, and errors carry
Failed/CleanupFailed plus bounded diagnostics, last phase and optional result.

The existing inbox still admits at most 1024 envelopes and 1 MiB logical aggregate
UTF-8/raw payload, including progress slots. Progress coalesces per source/generation.
Start/phase/final publication uses worker-only `wait_post`; final events never
coalesce. Smaller user inbox limits can reject an event that cannot fit at all;
the receipt reports unavailable instead of waiting forever. A zero-payload
WakeEvent keeps that failure notification ready for a blocking plain consumer,
even when no lifecycle event fits. It uses the same bounded inbox.

Operation event payload is at most 64 KiB, including identity/name/diagnostics/value.
State and booleans are fixed enums/scalars; names/IDs and each error string are at
most 4096 bytes. The bridge keeps one bounded outcome reference until replaced or
released with its owner; during handoff the observer may briefly retain the previous
event while the next explicit operation starts. The pending observation slot holds
an already started worker, never a queued invocation. These are logical storage
bounds, not RSS/global memory limits. Adapter working sets, Python thread overhead
and caller-retained snapshots are outside them. Ledger's proposed 20 results/2 MiB
retention is not implemented or calibrated here.

All events reuse core admission, wake, generations and per-turn fairness.
`EventLoop.request_active(request)` observes presentation eligibility, not liveness.
`forget_request(source, request=owned_request)` removes only that exact generation;
its optional guard preserves newer owners. No alternate event queue or result store
bypasses core accounting. Native input is inspected each turn; the existing 64-event/
4 ms posted work policy cannot preempt a callback, renderer or OS write.

## Executable examples and verification

A finite, memory-only synthetic operation:

```python
from io import StringIO
from cereja.ui.operations import OperationBridge
from cereja.ui.scheduling import EventLoop
from cereja.ui.terminal import StreamBackend, TerminalSession

def synthetic(context):
    context.running()
    for completed in range(1, 101):
        context.progress(completed, total=100, reliable_total=True)
    context.committing()  # Explicit synthetic publication, not a service claim.
    return "100 bounded iterations completed"

with TerminalSession(StreamBackend(StringIO(), StringIO())) as session:
    loop = EventLoop(session, lambda event: bridge.handle(event))
    bridge = OperationBridge(loop, "example")
    try:
        bridge.start("Synthetic", synthetic)
        while bridge.active:
            loop.turn(block=True)
        assert bridge.snapshot.state == "Succeeded"
        assert bridge.snapshot.worker_exited
        assert bridge.snapshot.delivery == "delivered"
    finally:
        bridge.close()
        loop.close()
```

The bounded feedback/navigation demonstration terminates and prints its final
snapshot (it is not a terminal walkthrough):

```text
python -B -S benchmarks/ui_operations.py --demo
python -B -S -m unittest tests.test_ui_operations tests.test_ui_scheduling tests.test_ui_benchmarks tests.test_ui_imports
python -B -S benchmarks/ui_operations.py --samples 31 --warmup 3 --output benchmarks/ui_operations_samples/baseline-windows-py314.json
```

Tests distinguish fake-clock scheduling from synchronized real worker lifecycle.
The benchmark uses real worker threads and wall time, 80x6 ASCII/no-color cells,
local/low-bandwidth/off/plain, with/without renderer and with/without a competing
noncoalescible producer. It retains environment, source fingerprints, raw input
injection/handler timestamps, turn numbers, production interval, queue pressure,
served/coalesced/rejected work, final outcome and rendering counters. Each producer
targets the configured minimum duration and four handled keys, with hard
limits of two seconds/one million iterations. Input is bounded to 64 synthetic
Tab keys, one outstanding at a time. Warmups are excluded.

Median, nearest-rank p95, MAD and range describe observed injection-to-handler
latency only for keys injected during confirmed production. The aggregate input
distribution and distribution of per-sample p95 are separate. Actual injection
frequency depends on the previous acknowledgement and Python scheduling (5 ms
minimum delay afterward); it is not a guaranteed 200 Hz input source.

Scheduler/CellBuffer and renderer/memory-sink measurements are separate. The sink
counts then discards output, without retained frame history. No OS transport,
terminal presentation, human task, clipboard, real domain I/O, RSS or global memory
is measured. These measurements neither prove a latency ceiling nor certify the
candidate frame rates, 4 ms callback budget or human usability. The #311 virtual
feedback benchmark is not evidence for these real producer latencies.

## Measured Windows baseline (2026-10-10)

[Raw evidence](../../benchmarks/ui_operations_samples/baseline-windows-py314.json):
Python 3.14.5, Windows 11, 16 scenarios, 31 samples after three warmups per
scenario (496 retained samples). All samples delivered exactly one successful
final result after worker exit; post-completion periodic work was zero.
The table selects the contended scenarios, with a second producer and initial
1024-envelope saturation. Values are milliseconds; distributions contain only
keys injected during actual progress production.

| Mode | Rendering boundary | Keys | Median | p95 | MAD | Min / max |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| local | scheduler/CellBuffer | 158 | 0.289 | 30.634 | 0.254 | 0.030 / 60.970 |
| local | renderer/memory | 159 | 0.235 | 26.387 | 0.199 | 0.028 / 38.787 |
| low-bandwidth | scheduler/CellBuffer | 155 | 0.353 | 30.642 | 0.319 | 0.032 / 50.703 |
| low-bandwidth | renderer/memory | 162 | 0.305 | 32.353 | 0.273 | 0.031 / 45.546 |
| off | scheduler/CellBuffer | 152 | 0.202 | 30.387 | 0.167 | 0.034 / 49.983 |
| off | renderer/memory | 161 | 0.175 | 27.748 | 0.142 | 0.029 / 50.739 |
| plain | scheduler/CellBuffer | 162 | 0.151 | 28.232 | 0.111 | 0.029 / 48.254 |
| plain | renderer/memory | 155 | 0.224 | 29.166 | 0.186 | 0.031 / 46.404 |

Small median differences between boundaries are not a causal renderer comparison;
thread scheduling and background load are uncontrolled. Raw counters and per-sample
p95 dispersion remain in the report. Source fingerprints were verified against
the delivered files, including the final publication-failure wake and cancellation
validation guards. Earlier interrupted collections are not this baseline.

Verification: 32 focused operation tests, 73 combined operation/scheduler/benchmark/
UI-import checks, and 396 UI cases per local Python 3.11 through 3.14 on Windows
(387 passed, nine platform skips per version). Direct review covered request
ownership, aggregate byte accounting, final publication/cleanup races, thread
start failure, stale generations, consumer loss and independent domain cancellation.
Actual terminal operation walkthroughs, clipboard roundtrips and human accessibility/
usability acceptance remain unperformed. The issue and coordination record own
the published revision, CI and acceptance disposition.
