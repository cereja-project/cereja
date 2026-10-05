# Cereja UI planning evidence

Status: UI-00 evidence reconciled; bounded model validation and recorded native
primitive observations, not a production implementation or platform certification.
The requested independent core supersedes the reference design's early display integration.
No production module, dependency, terminal mode, or public API was changed by these spikes.

## Reproduce

From the repository root, with Python 3.11 or newer and no third-party packages:

```text
python -B -m unittest discover -s benchmarks/ui_spikes -p test_model.py -v
python -B benchmarks/ui_spikes/verify.py
```

Use the [spike replay instructions](../../benchmarks/ui_spikes/README.md) to
collect new observations in a new directory outside the checkout. Preserve
the original raw reports instead of passing their paths to the probe writers.

The recorded run used Python 3.14.5 on Windows, revision
`ed7fbfa5bc08f3e5814602f1cb3f09e3d6ad5d87`, plus the uncommitted spike sources whose
SHA-256 values are recorded in the baseline. Renderer measurements contain 31 raw samples
each after five warmups, median, p95, and separately measured peak
traced memory. Timings exclude process startup except that import samples use
fresh processes and time only the import itself. No username, filesystem root,
host name, or environment dump is required to reproduce this report.

Evidence files:

- [Model tests](../../benchmarks/ui_spikes/test_model.py)
- [Disposable model](../../benchmarks/ui_spikes/model.py)
- [Raw baseline](../../benchmarks/ui_spikes/baseline-windows-py314.json)
- [Platform probe](../../benchmarks/ui_spikes/platform_probe.py)
- [Raw platform results](../../benchmarks/ui_spikes/platform-windows.json)
- [UI-00 integrity verification](../../benchmarks/ui_spikes/ui00-verification.json)

The UI-00 reconciliation on 2026-09-21 reran the nine model tests on Python
3.14.5 and verified all nine recorded source fingerprints across the renderer
and download reports. The 15 workloads contain 2,325 renderer timing samples
(five measured operations with 31 samples each), plus nine fresh root-import
observations. Every stored median and p95 recomputes from the raw samples.
The p95 uses sorted index `int(n * .95)`, index 29 for 31 samples. Original raw
files were preserved and their byte hashes are recorded in the verification.
No fresh timing measurements were needed for this consistency assessment.

Publication check on 2026-09-24: the nine model tests and the saved-evidence
verifier passed again on Python 3.14.5/Windows against integration base
`f54f600668c1370dc414bff8cdcf975324888a30`. All nine source fingerprints still
match the original evidence. This confirms compatibility of this evidence package
with that base, without replacing the historical samples or rerunning native probes.
Publication additionally checks four LF/CRLF fingerprint tests. Git may convert
Python source newlines, so the verifier reports exact and newline-only matches
separately. Raw JSON bytes retain their original hashes through directory Git
attributes; code changes and other whitespace changes do not qualify as matches.

| Evidence class | Bound evidence | Limit |
| --- | --- | --- |
| Model | Nine rerun tests, seeded diff equivalence, raw renderer timings | Disposable cells and primitives; no application or terminal emulator |
| Native observations | Previously recorded Windows waits/socket wake and owned loopback transfer | Noninteractive Windows primitives and bounded transfer paths only |
| Source/API references | Architecture and linked primary documentation | Specify behavior; do not demonstrate this implementation |
| Unverified implementation | Renderer transport, real input/modes, Unicode tables, lifecycle, product UX | Acceptance and end-to-end calibration remain pending |

The original platform JSON has no embedded revision or source fingerprint.
The renderer baseline separately fingerprints `platform_probe.py`, and that
fingerprint matches now, but this does not establish the original platform
capture's provenance. The download raw report includes source metadata that
its probe does not emit automatically. New captures must record this metadata
alongside their output, as the replay instructions describe.

## Renderer hypothesis and result

Hypothesis: dirty-cell comparison reduces sparse comparison work while preserving
the full-frame comparison result, provided invalidation covers every mutation.
Control: scan every cell. Candidate: scan sorted dirty indices. Both compare
text, width/occupancy, and style against the same front frame.

Nine tests pass. Seed 293 exercises 300 frame transitions and 6,000 attempted
writes at three sizes, including clipping and repeated wide-cell overwrites.
Tests compare complete change sets and reconstructed cells, check occupancy
invariants, and check a concrete continuation-cell overwrite. A deliberately
missing invalidation makes the candidate disagree with the reference, confirming
that the oracle detects that failure. The benchmark separately checks all 15
size/workload combinations for identical change sets.

Selected local medians, milliseconds:

| Viewport | Workload | Full diff | Dirty diff | Dirty diff + encoding | UTF-8 bytes |
| --- | --- | ---: | ---: | ---: | ---: |
| 80x24 | one cell | 0.1251 | 0.0003 | 0.0009 | 12 |
| 120x40 | one row | 0.3177 | 0.0130 | 0.0340 | 1,572 |
| 240x80 | unchanged | 1.2629 | 0.0002 | 0.0004 | 0 |
| 240x80 | 10% | 1.3436 | 0.2006 | 0.5214 | 26,016 |
| 240x80 | all | 2.3534 | 2.3227 | 6.2663 | 277,200 |

All three unchanged workloads encode zero bytes and plan zero stream calls.
Nonempty frames plan one batched stream call; actual stream or OS writes are not
measured. Sub-microsecond values approach timer resolution and should not be
used as precise speedup ratios. Full repaint shows essentially no diff benefit.
Invalidation collection, layout, painting, frame allocation, terminal transport,
and emulator costs are excluded from these comparisons. The intentionally simple
encoder emits a cursor/style sequence per leading cell and is not an efficient
production encoder. Its byte count motivates a later run-grouping experiment.

Decision: preserve a correct full-diff reference and add dirty tracking only with
equivalence checks. Sparse model benefit is sufficient to retain the candidate,
not to claim a production frame-rate or justify native acceleration. Resize
requires explicit full invalidation. Old and new geometry, style policy changes,
occlusion, writer failures, cursor state, and final-column wrapping still require
implementation tests. The model does not emulate terminal autowrap or scrolling.

## Unicode and trust boundary

The spike replaces C0, DEL, and C1 controls before measurement and encoding.
CSI/OSC payloads, newline, tab, carriage return, and BEL are neutralized in the
single-line policy. Multiline components must convert line breaks and tabs into
layout operations rather than relaxing this boundary. Tests check idempotence
and the absence of control code points. This is bounded text sanitization, not a
complete input parser, paste limiter, bidi policy, or full security review.
The model substitutes U+FFFD for controls; the architecture proposes visible
ASCII escapes so the exact control is inspectable. The tested representation
is therefore deliberately different: only the neutralization boundary is
supported by this spike, not the final sanitizer's complete behavior.

The conservative width experiment accepts ASCII, precomposed accents, combining
acute attached to a base, and CJK widths. It explicitly returns unsupported for
emoji, regional indicators, variation selectors, ZWJ sequences, and isolated
combining marks. This helper is a feasibility probe, not the chosen production
Unicode contract: category and East Asian Width metadata alone do not implement
extended grapheme segmentation. [Unicode UAX #11](https://www.unicode.org/reports/tr11/)
and [UAX #29](https://www.unicode.org/reports/tr29/) define different concerns.

Decision: ship versioned generated segmentation/width data with provenance and
notices, keep generation a development task, use one metrics policy throughout
layout/editing/rendering, and support an explicit ASCII substitution policy for
unknown clusters or limited terminals. A table-generation and conformance task
must settle Unicode version, ambiguous width, emoji presentation, and cluster
fallback before accepting Unicode-aware Input. The spike's deliberate unsupported
cases must not silently become the public toolkit's advertised support level.

## Waiting, timers, and overload

The deterministic timer model preserves insertion order for equal deadlines,
limits work per dispatch, and returns no timeout when idle. The bounded FIFO
rejects overflow explicitly, preserves ordered events, and resets its wakeup
under the same lock as posting. A cross-thread test wakes a waiting consumer.
These prove primitive behavior, not a complete fair scheduler or idle application.

The native Windows probe uses standard-library ctypes with explicit signatures.
Two independent event handles demonstrate timeout (258), a producer waking the
second handle (index 1), and timeout after reset. All owned handles are closed.
A socketpair selector also reports no ready event during idle and receives one
posted byte. These are real local primitive calls, not mocked Win32 results.
The current process has non-TTY input/output and GetConsoleMode fails, so no
console record normalization, terminal mode restoration, or real input latency
was tested. No terminal input was consumed and no mode was changed.

Decision: bounded queues with explicit post success/failure, reserved shutdown
signaling, and coalescing only for replaceable notifications. Ordered key/text
events need backpressure rather than silent drops. Process at most a configured
event/time budget before revisiting input and rendering. Use a self-pipe/socket
wakeup with POSIX selectors; on Windows use native console input plus a wake
event in WaitForMultipleObjects. A threading.Event by itself does not multiplex
console input. Python's [select documentation](https://docs.python.org/3.11/library/select.html)
limits Windows select to sockets; Microsoft documents
[console input and event objects](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitformultipleobjects)
as native wait targets. The Windows event result supports feasibility but leaves
combined console/wakeup behavior to backend integration acceptance.

## Import baseline and platform coverage

Nine fresh-process root imports have a median of 0.9447 ms, no captured stdout or
stderr, no added threads, and no cereja.ui modules. This is the existing root
baseline; there is no production `cereja.ui` candidate to compare. Import acceptance
must also inspect terminal setup, environment probing, and lazy exports after
implementation. A fast root import alone cannot prove all lazy-loading behavior.

| Surface | Current evidence | Required next evidence |
| --- | --- | --- |
| Virtual buffer | Seeded equivalence, style, clipping, wide overwrite | compositor, resize, output failures, bottom-right policy |
| Windows primitives | Native event wait and socket wake; Python 3.14.5 | real console input, modes, interruption and cleanup |
| Linux / macOS | Design and primary API references only | Python 3.11-3.14 CI plus PTY lifecycle/input tests |
| Windows terminal hosts | No interactive host in this execution | Windows Terminal and console-host run records |
| Pipes / CI | non-TTY probe, root import silence, sanitized text model | actual CLI clean plain output and exit behavior |
| SSH | Not exercised | latency/byte budgets, reduced-motion interaction |
| Unicode glyph display | Cell model only | emulator/version recordings for cluster fixtures |

The Windows launcher alias could not execute during interpreter discovery; only
Python 3.14.5 was run. [Python pty](https://docs.python.org/3.11/library/pty.html)
is Unix-only. Availability of a shell or a launcher does not establish a usable
Linux/macOS runtime or terminal coverage. No platform support claim is inferred.

## Implementation gates and pending calibration

UI-00 freezes the following gate for subsequent changes to this model: all 15
workloads and the seeded mutation tests must retain identical full/dirty results;
unchanged frames must encode zero bytes; one-row and ten-percent workloads at
each of the three sizes must have lower dirty-diff median and p95 than full-diff
in the same run. Preserve both raw distributions and report all workloads,
including full repaint, where no benefit is required. These six comparisons
are recorded in the [integrity report](../../benchmarks/ui_spikes/ui00-verification.json).
This gate is selected from the observed baseline, not a preregistered efficacy
experiment. It assesses this comparison stage only; it is neither a production
budget nor a statistical significance test. Timer-resolution-sensitive one-cell
results do not establish precise speedup ratios. A failure requires retaining
the full reference and investigating; never remove a failing workload to pass.

The architecture fixes the behavior contracts and initial policies for UI-00.
The measurements above establish the bounded model baseline and support keeping
the dirty-diff candidate under full-reference equivalence checks. They do not
derive production latency, throughput, or memory thresholds. The numerical gates
below remain provisional experiments to calibrate against an implementation;
policy defaults are tunable inputs, not measured optima or accepted guarantees:

- Hard gates: unchanged frame and idle application produce zero renderer output;
  all supported text fixtures agree across metrics, clipping, editing, and paint;
  full and incremental reference screens agree; controls cannot cross Text.
- Compare root-import candidate and baseline in 30 alternating fresh processes
  on each reference runner. Investigate a median regression above 2 ms or 20%
  (whichever is larger); independently reject eager terminal setup or workers.
- For future selected application fixtures at 80x24 and 120x40, a provisional
  target is p95 under 100 ms key-to-visible update on local real terminals.
  Record stage profiles and transport latency separately. No 240x80 complete
  frame budget can yet be inferred from this diff-only spike.
- Sparse updates should emit fewer bytes than full repaint for the same final
  screen; enforce zero unchanged bytes. Set an SSH byte budget from the actual
  grouped encoder before enabling more than one animation by default.
- Validate bounded memory under a producer exceeding consumer throughput for
  60 seconds, input service every dispatch budget, and shutdown within 100 ms
  on the virtual backend. Report rejection counts and retained event ordering.
- Do not use this model's timings as pass thresholds for production or as proof
  of native-code necessity. Benchmark layout (10/100/1,000 nodes), painting,
  Unicode clusters, progress/log streams, resize, and transport when those
  implementations exist, before accepting optimization claims.

The present evidence supports an executable implementation plan with explicit
release gates. It does not remove those gates or certify an unbuilt UI.
The numerical import, latency and overload policies above are proposals to
calibrate against the implementation baseline, not evidence-derived budgets.
Measured local baselines are established; production budgets remain an explicit
calibration deliverable before optimization. Product-dependent fixtures and
final UX must conform to the recorded product scope. The selected Ledger direction
and five-area scope are planning decisions, not completed real-terminal or
product-flow acceptance.

## Separate review and visual inspection

The coordinating reviewer reran all nine model tests successfully and checked
all four source SHA-256 fingerprints against the saved baseline. This review
shares the task context and is not a blinded independent experiment.
The current HTML contains 73 structurally checked exact-size ASCII canvases
(24 specimens at three sizes plus 30x10 recovery). Earlier browser review covered
the initial dashboard 40x12/80x24 and scope/navigation. After the selected five-area
revision, the reviewer inspected Archives Running, Download with known/unknown
total fixture data and Activity with one current job. The sampled presentation
was legible; progress is explicitly fictional contract data, not a live transfer.
This is limited browser presentation review, not inspection of all 73 canvases,
actual terminal rendering, usability, or final product-flow acceptance.

## Selected-operation runtime evidence

[Operation contracts](cereja-ui-operation-contracts.md) separate source findings
from an owned loopback download probe. Known and absent Content-Length both
transferred 1,536 bytes with 12 actual callbacks and exact final output. An owned
exception on the first 128-byte callback preserved an existing destination and
removed partial output. Server and temporary-directory cleanup passed.
The local raw report records source revision and hashes for the probe and relevant
transfer/client files. This supports actual progress and that bounded abort path,
not complete cooperative cancellation or commit/blocked-read race safety.
Probe source and raw data are included under `benchmarks/ui_spikes/`.
