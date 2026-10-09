# Independent core performance calibration (#304)

Scope: the implemented terminal/text/buffer/rendering/scheduling core. Ledger
remains the selected product direction; application latency belongs to #321.
Historical spike measurements establish feasibility only.

## Frozen collection protocol (2026-10-09)

Runtime source: develop `383598f96ab4619530e7783797c7a4a55aac653c`.
No runtime optimization is part of collection. Each report records the actual
source SHA-256 values, HEAD/tree, interpreter, platform, pointer size, GC state
and conditions, including uncommitted benchmark instrumentation.

Use one process at a time on the same Windows host and CPython 3.14.5 (64 bit).
Affinity, power policy and background load are uncontrolled. No cross-machine,
cross-interpreter or cross-OS timing comparison is authorized by these samples.
Fresh import processes may have warm OS filesystem caches.

Before measurement: fix 31 timing samples, three discarded warmups and seven
separate untimed tracemalloc windows. p95 uses nearest rank (30th of 31); seven
memory samples have p95 equal to the maximum. Report median, MAD, min/max and
all raw observations. MAD/range are dispersion, not confidence intervals.

Data is deterministic (no random seed): ASCII/default-style and repeated
Ledger-like combining accents, CJK, emoji ZWJ text with four fixed styles.
The representative generator repeats by measured cell width, keeping each
source row eligible for the <=1,024-code-point metrics cache. Paint includes
text normalization/measurement/clipping and draw, not just Cell construction.
Full/dirty compare identical effective front/back, damage, cursor and output.
Two opaque layers include a bottom-right 16x2 overlay. Sparse changes request
one cell, one row or 10% of row-major drawable cells; wide-glyph footprints
can expand actual changes. The last column is reserved by the renderer.
Initial/full, unchanged, and resize from each base by +/-8 columns and +/-2
rows complete coverage at 80x24, 120x40 and 240x80.

Timed stages: source copy/paint/resize, two-layer composition, capability
preparation, reference full diff, dirty diff, encoding and immutable snapshot.
Separate bare Renderer totals use a synchronous memory sink. UTF-8 byte
counting stays outside these windows. Patched renderer totals/stages explicitly
include instrumentation; they are not subtracted to invent compute time.
Matched full/dirty order alternates; priming the old front is outside timing.
Preparation also counts actual Cell constructor calls in a separate patched
render; this is a scoped allocation count, not all Python allocation churn.
Separate whole-sample memory windows include setup/controls and report retained
survivors, peak tracked bytes and live traced blocks. Buffer windows retain
frames; text windows distinguish cleared metrics cache from warm cache, never
confusing that cache with fresh process imports.

Scheduling reuses the existing ordered 10,000-event probe and native probe.
Virtual time only establishes scheduling/counters. Additional compute windows
dispatch 1/64/1,024 due timers with small append callbacks, request a Unicode
frame and repeat an unchanged frame at each dimension. Native key/post latency
and native output are measured in hidden fresh Windows consoles separately.
Native output measures fixed encoded payloads: logical payload dimensions may
exceed the observed console viewport. Write acknowledgement/flush does not
establish visual presentation. Native flush can be a no-op for console handles.

Imports: root, UI namespace, terminal, text, buffer, rendering and scheduling
in a fresh `-B -S` process per sample, then an identical import statement with
sys.modules warm. Only the statement is timed; process startup is excluded.
Module sets, captured output and surviving new threads accompany every sample.
Import contracts independently verify absence of feature/worker side effects.

Baseline first, then freeze comparison budgets using only baseline measurements.
Core time budget per metric: max(1.25*p95, p95+3*MAD, 50 microseconds).
Tracked memory: max(1.10*p95, p95+3*MAD, 4 KiB) for bytes, analogous 10%/MAD
with a 16-block floor for live blocks. These are local regression investigation
thresholds, not universal ceilings. The 25% margin, MAD allowance and timer
floor avoid treating tiny instrumentation/clock variations as material pressure.
The import root guard retains the design's max(2 ms,20%) paired median rule,
unchanged module set and no side effects. Then collect an unchanged-code
control under the same conditions. Preserve any breach; a repeated material
compute breach requires profiling before selecting an intervention. Neither
the first baseline nor a throughput difference between full and dirty is a
candidate optimization.

Behavioral gates remain unconditional and are verified by existing contracts
plus benchmark assertions: unchanged frame/cursor/session writes and flushes
zero; transactional front commit/failure cleanup; full/dirty equivalence;
safe text; imports without workers; indefinite idle wait without periodic
renders; next-turn input inspection during ordered 10,000-event pressure;
bounded queues/payloads, generations and cooperative cancellation.
30 Hz local, 4 Hz low-bandwidth and <=8 Hz spinner remain policies.

The report does not claim Ledger p95 <=100 ms, human acceptance, RSS, a Python
heap bound from logical payload budgets, preemption of callbacks, or timeout
of blocked OS writes. Emulator, SSH, ConPTY and real disconnection walkthroughs
remain platform-validation work.

## Results and disposition

The runtime remains unchanged. Raw [baseline/control](../../benchmarks/ui_core_samples/)
reports contain source fingerprints, conditions, all observations and median/p95/MAD/range.
Baseline: 48 render scenarios, 18 buffer scenarios, four cold/warm text cases,
nine timer/dimension cases, seven fresh-import cases, 31 native input samples
and six native output cases. Each time case has 31 samples after three warmups;
tracked memory has seven separate windows. There is no optimization treatment.

Representative Unicode/four-style bare dirty Renderer totals, milliseconds
(two layers, memory sink; paint/composition excluded):

| Size | Workload | Baseline median / p95 | Frozen p95 limit | Control median / p95 | UTF-8 bytes |
| --- | --- | ---: | ---: | ---: | ---: |
| 80x24 | unchanged | 0.808 / 1.951 | 2.439 | 1.621 / 14.601 | 0 |
| 80x24 | one_cell | 1.044 / 1.810 | 2.499 | 1.817 / 13.949 | 44 |
| 80x24 | ten_percent | 1.083 / 2.655 | 3.318 | 1.707 / 5.808 | 431 |
| 80x24 | all_drawable_cells | 2.415 / 5.657 | 7.071 | 5.029 / 45.312 | 3937 |
| 80x24 | resize_grow | 2.179 / 4.904 | 6.129 | 2.601 / 4.576 | 5402 |
| 120x40 | unchanged | 2.503 / 5.090 | 7.178 | 2.678 / 5.308 | 0 |
| 120x40 | one_cell | 2.248 / 4.866 | 6.082 | 2.688 / 6.416 | 44 |
| 120x40 | ten_percent | 2.928 / 6.519 | 8.173 | 3.006 / 6.260 | 985 |
| 120x40 | all_drawable_cells | 7.001 / 14.094 | 17.618 | 7.145 / 10.877 | 9629 |
| 120x40 | resize_grow | 4.536 / 9.323 | 11.654 | 4.971 / 7.054 | 12766 |
| 240x80 | unchanged | 8.240 / 15.680 | 19.600 | 10.356 / 17.255 | 0 |
| 240x80 | one_cell | 8.744 / 18.662 | 23.327 | 10.109 / 20.703 | 44 |
| 240x80 | ten_percent | 10.464 / 24.276 | 30.345 | 10.643 / 13.663 | 3676 |
| 240x80 | all_drawable_cells | 28.502 / 44.017 | 55.021 | 31.578 / 51.477 | 36579 |
| 240x80 | resize_grow | 19.615 / 29.583 | 38.901 | 17.448 / 26.292 | 47156 |

Full Unicode paint/composition/preparation/diff/encode stage medians, milliseconds.
These independent windows must not be added into an alleged application latency.

| Size | Paint | Compose | Prepare | Dirty diff | Encode |
| --- | ---: | ---: | ---: | ---: | ---: |
| 80x24 | 2.862 | 1.110 | 0.768 | 1.032 | 0.762 |
| 120x40 | 6.812 | 2.874 | 2.344 | 2.616 | 1.874 |
| 240x80 | 26.896 | 11.558 | 10.327 | 10.344 | 7.557 |

## Budget disposition and profiles

All 1,050 per-metric thresholds are in [budgets.json](../../benchmarks/ui_core_samples/budgets.json).
They were frozen before the unchanged-code control. Time thresholds include
compute, memory-sink and explicitly separate instrument/native observations;
tracked-byte/live-block thresholds follow the stated memory formula.
The [comparison](../../benchmarks/ui_core_samples/budget-control.json) preserves
156 compute/memory-sink exceedances, 67 instrumentation exceedances and five
native observational exceedances. No tracked-memory threshold was exceeded.
All ten independent report checks passed, including zero unchanged output,
native/virtual indefinite idle wait and next-turn key inspection during all
10,000 ordered results. Root import median/module/silence/thread guards passed.

**These timing thresholds are investigation budgets, not stable automatic
acceptance gates.** The control failed them despite identical source fingerprints
and declared host/interpreter/inputs. Background load/power/affinity were not
controlled; the root cause of timing variation is unresolved.

A single [targeted 80x24 repeat](../../benchmarks/ui_core_samples/rendering-targeted-repeat.json)
kept 31 samples/three warmups/seven tracing windows and the same source/data.
Nine of 48 primary paint/prepare/dirty-total comparisons still exceeded their
original limits; two of 16 dirty totals exceeded. Unicode unchanged p95 was
2.353 ms versus 14.601 ms in the first control (limit 2.439 ms); one-cell p95
was 2.030 ms versus 13.949 ms (limit 2.499 ms). This supports instability of
the large failures, without attributing a cause or passing every timing budget.
Budget values were not raised to fit the control/repeat.

[Bounded representative profiles](../../benchmarks/ui_core_samples/profile-representative.json)
cover three 240x80 full paints and preparations after one warmup. Paint cost
is attributed to draw_text, normalization/clipping and cell painting; preparation
has per-cell traversal, Style hashing and observed Cell construction. Patched
counts establish 1,920/4,800/19,200 preparation Cell constructions at the three
base sizes, including unchanged renders. These counts exclude unrelated objects;
traced live blocks are separate from cumulative allocation churn.
[Long-input profiles](../../benchmarks/ui_core_samples/preliminary-long-input/profile-long-input.json)
locate the preliminary paint cost in repeated uncached _measure/grapheme work
inside the generator. Profiler times include overhead and are not latency samples.

Decision: no production candidate and no native acceleration. The observed
large failures were not reproducibly attributable to a correctable runtime
regression; no Ledger end-to-end budget was tested. Python alternatives were
assessed: generate only enough row input to fill its cell width (applied to the
benchmark as a declared workload correction), reuse immutable cells whose effective style
is unchanged, and reduce repeated style hashing. The latter two affect preparation
contracts/capability fallback and need stable paired evidence of material pressure
before a measured candidate is justified. No API/cache/worker change is introduced.
Do not infer that current core costs can never become an application bottleneck.

## Imports, memory and native observations

| Fresh process case | Median / p95 ms | Warm identical exec median us |
| --- | ---: | ---: |
| root | 1.382 / 1.743 | 27.000 |
| ui | 1.581 / 1.862 | 28.600 |
| ui_terminal | 15.405 / 17.357 | 21.300 |
| ui_text | 14.432 / 16.370 | 14.600 |
| ui_buffer | 17.871 / 19.490 | 15.000 |
| ui_rendering | 19.688 / 21.749 | 15.200 |
| ui_scheduling | 18.986 / 20.617 | 15.500 |

At 240x80, two blank frames retained 307760
tracked bytes (peak 307768); a dense styled Unicode frame
retained 1229992 bytes (peak 1231176).
These are scoped warm tracemalloc observations, not RSS or heap guarantees.

Native injected key median/p95: 0.533/0.762 ms;
idle post: 0.191/0.280 ms.
Callbacks carry small fixed values. This is OS injection to a handler, not
human input-to-visible/application latency. Native output uses WriteConsoleW:
UTF-16 code units and logical UTF-8 accounting are both recorded. Console
flush is a no-op on this path. Logical 120x40/240x80 payloads exceed the observed
120x30 viewport; acknowledged writes do not certify complete visible frames.
Modes were restored and cleanup failures were zero in both output collections.

## Reproduce and validation ownership

Use a new owned directory for replay; never overwrite the canonical reports.
Run each process sequentially, under the frozen host/interpreter conditions:

```text
python -B -S benchmarks/ui_rendering.py --samples 31 --warmup 3 --memory-samples 7 --output NEW/rendering-baseline.json
python -B -S benchmarks/ui_buffers.py --samples 31 --warmup 3 --memory-samples 7 --output NEW/buffers-baseline.json
python -B -S benchmarks/ui_scheduling.py --transport virtual --samples 31 --warmup 3 --memory-samples 7 --output NEW/scheduling-baseline.json
python -B -S benchmarks/ui_scheduling.py --transport windows --samples 31 --warmup 3 --output NEW/native-input-baseline.json
python -B -S benchmarks/ui_rendering.py --transport windows --samples 31 --warmup 3 --output NEW/native-output-baseline.json
python -B -S benchmarks/imports.py --samples 31 --case root --case ui --case ui_terminal --case ui_text --case ui_buffer --case ui_rendering --case ui_scheduling --output NEW/imports-baseline.jsonl
python -B -S benchmarks/ui_core_samples/freeze_budgets.py NEW
```

Then run the same six commands with control output names and unchanged code,
and run `python -B -S benchmarks/ui_core_samples/compare_budgets.py NEW`.
For diagnostics, the profile script takes `--output NEW/profile.json` and
optional `--long-input`; cProfile windows are distinct from timed samples.

Contract tests remain the acceptance mechanism for output transactions/failure
cleanup, full/dirty equivalence, text safety, import isolation, queue/payload
bounds, input order, generations/cancellation, fairness and scheduling policies.
The UI CI matrix additionally smokes the measurement paths without timing gates.
Issue [#304](https://github.com/cereja-project/cereja/issues/304) owns the actual
tested/reviewed tree, delivered commit, CI result and pending human acceptance.
Manual emulator/SSH/ConPTY/real-disconnection coverage and #321 application
calibration remain separate. Publication and CI cannot supply human acceptance.

### Preserved preliminary long-input stress

The first collection repeated the Unicode token by column count, then clipped
it to the requested row. That processes a much longer source and bypasses the
metrics cache in several cases. It is valid long-input stress but unsuitable as
the representative row baseline. The complete first baseline, unchanged-code
control, budgets and comparison remain in
[preliminary-long-input](../../benchmarks/ui_core_samples/preliminary-long-input/).
Its control exceeded 116 compute/memory-sink thresholds, 38 instrumentation
thresholds and four native observational thresholds; all ten recorded hard
checks passed. These negative results are retained, never fitted away.

Unicode full-frame paint medians were 77.644/188.447/776.051 ms at
80x24/120x40/240x80, including overlong source generation/measurement/clipping.
Do not compare those values with representative-row timings as an optimization.
The workload correction changes inputs, not production code. The current
render/buffer scripts retain `--long-input` to reproduce that generator;
later allocation instrumentation differs and has its own recorded fingerprints.
After identifying the scope mismatch, collection conditions were explicitly
refrozen before the representative baseline and control, retaining the same
31 timing samples, three warmups and seven memory windows.
