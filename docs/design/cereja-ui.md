# Cereja UI architecture and acceptance contract

Status: UI-00 contract freeze v1, reviewed locally on 2026-09-21 for
[#294](https://github.com/cereja-project/cereja/issues/294). This fixes the core
semantics for dependent implementation, not a claim that `cereja.ui` exists or
that platform acceptance has passed. Publication and integration status are
tracked in #294; the original review was local on 2026-09-21.
The requested independent architecture supersedes the earlier shared-stack
proposal. Source baseline: `ed7fbfa5bc08f3e5814602f1cb3f09e3d6ad5d87`.

Read with [UX and motion](cereja-ui-ux.md), [evidence](cereja-ui-evidence.md)
and [delivery plan](cereja-ui-plan.md). The wireframe HTML is a disposable
planning artifact, not the implementation technology for the terminal product.

Current official-application direction is a command-driven shell/workbench with
a persistent bottom composer and rich inline content. Slash discovery/navigation,
autocomplete, contextual help and keyboard overlays must use the same reusable
toolkit. Inline Loading/Empty/Error/Success/Warning states are not independent
screens. The maintainer selected Ledger, with bounded sequential result blocks,
and file-plus-directory archive scope. This does not change the independent
terminal/rendering contracts below.

## UI-00 decision and coverage

Retain the independent Python/stdlib core. The existing full/dirty model and
native wake primitives support feasibility; they do not implement these contracts.
Sections 2-5 freeze ownership, capability precedence, Unicode, pressure and
failure behavior. Numerical limits are explicit initial policies, adjustable
through a recorded contract change and boundary tests, not measured optima.
Public class signatures and internal data structures remain implementation choices.

| Requirement | Frozen contract / current evidence | Remaining acceptance owner |
| --- | --- | --- |
| Independent, lazy, zero dependencies | Sections 1-2; current packaging, static command registry and root-import baseline reviewed at the revision above | #295, #305: new UI import and distribution tests |
| Capabilities and single terminal owner | Sections 2-3; conservative plain fallback and explicit overrides | #295: virtual lifecycle/failure matrix; #296/#297: OS integration |
| Safe Unicode and consistent cells | Section 4; pinned segmentation plus separate width policy; spike proves only a subset | #298: generated data, license/hashes, conformance and fallback fixtures; #299: composition |
| Transactional rendering | Section 4; full-diff oracle, whole-wide-cell invalidation, write/flush commit | #299/#300: compositor, resize, cursor, partial-write and flush failures |
| Bounded input, producers and timers | Section 5; count and payload bounds, explicit rejection, shutdown independent of queue | #301: sustained overload, fairness and worker teardown |
| Repeatable model evidence | [Evidence](cereja-ui-evidence.md) and [replay instructions](../../benchmarks/ui_spikes/README.md); original samples preserved | #304: representative implementation baseline before optimization |
| Platform coverage | Section 7 matrix is required, not passed | #305: core; #321: real application, terminals and packages |
| Product and legacy boundary | Selected Ledger and five areas preserved; no new product decisions here | Existing product tasks; #322: compatibility after stabilization |

The UI-00 gate is documentary and executable-model acceptance only. Missing real
terminal evidence remains with its dependent task. No production task starts as
a side effect of this freeze; no current API or dependency changes.

## 1. Scope and requirement validation

Deliver two distinct surfaces: reusable `cereja.ui` and explicit `cereja ui`.
Python 3.11+ and the standard library are the reference implementation. No
runtime dependency, compiler, network fetch or native module is required.
Windows, Linux and macOS are release targets; pipes, redirected streams and CI
must terminate with useful plain output. Toolkit scope is not reduced by the
first application use case. Mouse, graphics, native acceleration and advanced
terminal protocols are optional later work, not dependencies of the core.

Verified repository facts: `pyproject.toml` requires Python >=3.11, declares no
runtime dependencies and routes the CLI to `cereja.entrypoint:main`. The root
package attaches lazy exports and prints its banner only through an explicit
function. `commands/registry.py` is static; the dispatcher imports one command.
Existing CI tests Python 3.11-3.14 on Windows/Linux and import contracts on all
three OSs with 3.13. Full macOS UI coverage is therefore new acceptance work.

The legacy `_terminal.py` encoding flag is not a terminal capability detector.
Do not import it as the new capability model. No dependency from the new UI to
`cereja.display` is allowed. Legacy characterization happens after the new
system stabilizes, except a nonbinding inventory used to bound migration cost.

## 2. Architecture and ownership

```text
domain services -> data -> application state -> retained widget tree
                                ^                    |
normalized input / timer / result events             v
                              invalidation -> layout -> paint/composition
                                                           |
                                                    desired CellBuffer
                                                           |
last successfully emitted CellBuffer -> diff -> encode -> OutputWriter
                                                           |
                                              platform TerminalBackend

later: cereja.display -> compatibility adapter -> cereja.ui primitives
```

Internal modules live under `cereja.ui`: `terminal`, `rendering`, `text`,
`geometry`, `style`, `events`, `layout`, `widget`, `widgets`, `app`, `testing`.
`__init__` stays lazy. The application command lives in `cereja.commands.ui`
and its domain adapters outside reusable widgets. Public exports initially
cover `App`, immutable events/styles and the documented basic widgets. Backend
internals and cell serialization remain private until a concrete extension need.

| Boundary | Input/output and invariant |
| --- | --- |
| Domain adapter | Typed request -> bounded result/progress/error; no terminal writes, ANSI, widget objects or UI imports. |
| State reducer | `(state, event) -> state + effects + invalidations`; only UI thread mutates the widget tree. |
| Widget | Stable identity, measure/arrange/paint/handle; paint writes clipped cells, never streams. |
| Layout | Integer cell rectangles, nonnegative sizes, deterministic remainder distribution in sibling order. |
| Metrics | Sanitized text + width policy -> grapheme units/cell widths; same boundaries for editing and painting. |
| Renderer | Composed desired cells + committed front + damage -> output transaction; commit only on successful write and flush. |
| Backend | Capabilities, size, session, wait, normalized input, writer; no application decisions. |
| Test backend | Virtual dimensions, injected input, fake clock, captured cells/operations and injected failures. |

A single UI-thread owner writes during a session. External work posts bounded
events; it cannot print or mutate widgets. A suspend context restores terminal
modes before external output, then reacquires and invalidates the full frame.
No capture of global stdout/stderr is required by the core. Applications may
install an explicit stream adapter later; exceptions retain their original cause.

## 3. Terminal backend and lifecycle

`Capabilities` records input interactivity and output interactivity separately,
color depth (0/16/256/truecolor), Unicode policy, cursor movement, alternate
screen and paste support. Unknown capability defaults conservatively. Precedence:
explicit per-run option, environment convention, backend detection, safe default.
Nonempty `NO_COLOR` disables color, not navigation. An explicit color override
must be visible/documented. No automatic active probe is needed for v1.

Resolve each capability independently and retain its effective value and source
for diagnostics. Per-run typed options may lower or assert color depth, Unicode,
cursor/alternate-screen and paste protocol support; invalid values fail before
acquisition. `NO_COLOR` is the only v1 color environment override; other variables
are conservative detection hints. Explicit color wins over `NO_COLOR`, but cannot
enable cursor navigation. Noninteractive input or output always selects plain
mode. With interactive handles, `TERM=dumb` or unknown cursor support defaults
to plain; an explicit capability assertion may override those hints only when
the backend supports acquisition. No override makes a pipe a TTY or enables raw mode on it. Plain output
contains no terminal control sequences even with an explicit color request.
Reduced motion and ASCII are independent policies. Acquire modes only at session
entry; changing a capability during a session requires suspend/reacquisition and
full invalidation. Reject a second owner of the same terminal until release.

`TerminalSession` is context managed: capture -> acquire -> run -> unwind.
Record each acquired resource before the next operation; cleanup is idempotent
and reverses completed acquisitions on normal exit, exception, Ctrl+C and partial
setup. Restore modes, cursor, alternate screen and installed signal handlers.
SIGKILL, forced termination and terminal disconnect cannot promise restoration.
Cleanup attempts every acquired resource even if one restoration fails. Preserve
the initiating exception and attach cleanup failures; without an initiating
failure, surface the cleanup error. Suspension has the same guarantees, and a
failed reacquisition ends the session rather than leaving two writers active.

POSIX: `termios`/`tty` manage modes; `selectors` watches input and a nonblocking
self-pipe for posted work/shutdown. Resize signal only enqueues/coalesces a
notification. Decode UTF-8 and escape sequences incrementally, including split
reads. Escape ambiguity timeout starts at 30 ms (configurable 10-100 ms), with
fixtures at each boundary and measured SSH behavior before release.

Windows: `ctypes` binds typed Win32 APIs. `GetConsoleMode` detects console
handles; enable VT output when supported and restore original modes. Wait for
both console input and an application wake event with `WaitForMultipleObjects`;
`ReadConsoleInputW` consumes records only when ready. Normalize key repeats,
modifiers, UTF-16 surrogate pairs and resize records. Invalid surrogates replace
predictably. Do not run a POSIX stdin selector on Windows. Legacy non-VT hosts
use plain output; a second native drawing engine is not needed for v1.

Plain mode acquires no raw/alternate-screen state and schedules no animation.
`cereja ui` with noninteractive input or output prints one meaningful overview
with equivalent CLI commands and exits 0. A failed requested operation exits
nonzero. An explicit `--snapshot` may select a data screen without interaction;
JSON stays in the existing data commands. Broken pipe stops output cleanly;
other write failures end the session with its original error.

## 4. Text, security and cells

Neutralize ESC, C0/C1 and DEL in all ordinary text before measurement. Newline
and tab become layout tokens, not raw terminal commands. Render other controls
as visible ASCII escapes. Titles, status, logs, paths, exceptions and paste use
the same boundary. Styles are typed values; no arbitrary ANSI API in v1.
Bidirectional formatting controls are displayed visibly for source/path views;
the initial renderer uses logical ordering and does not claim a full bidi engine.

Choose pinned generated Unicode tables at development time, shipped as Python
data with provenance/license and a regeneration script. Runtime `unicodedata`
alone does not provide extended grapheme segmentation. Freeze Unicode 17.0.0
default extended grapheme boundaries, UAX #29 revision 47, without tailoring.
Version 17.0.0 is a fixed dataset choice. Its [published test data](https://www.unicode.org/Public/17.0.0/ucd/auxiliary/GraphemeBreakTest.txt)
is available; pinning avoids different behavior across Python 3.11-3.14. The
exact fetched dataset hashes are a
UI-04 acceptance artifact. Grapheme segmentation and terminal width are separate:
ambiguous width defaults to 1 with an explicit policy switch to 2. Exact RGI emoji
sequences from Emoji 17.0, including its listed basic emoji and ZWJ sequences,
occupy 2 cells. Apply this precedence after sanitization: exact RGI match; exact
listed text-style emoji variation sequence; fallback; ordinary text width.
Text-style variation sequences use their base's text width. Otherwise, an
unassigned scalar, U+200C/U+200D, Variation_Selector, Emoji_Modifier or
Regional_Indicator in a non-RGI cluster triggers replacement of the whole cluster
with `?` (one cell). Emoji property alone does not trigger fallback: bare digits,
copyright and text-style heart use ordinary text width. Ordinary clusters use
the maximum non-mark scalar width: W/F = 2, A = the selected ambiguous width,
others = 1; attached Unicode marks (Mn/Mc/Me) add no cells. An all-mark cluster
receives a dotted circle of width 1 before its marks. This is a terminal policy,
not a glyph-shaping guarantee.
Unpaired surrogates first become U+FFFD. ASCII mode preserves printable ASCII
clusters and maps every other complete grapheme to `?` before layout. Do not
split a cluster or count Python code points as cells. UI-04 must test this exact
policy against the pinned properties and emoji lists, including decomposed text.

Required fixtures: ASCII, precomposed/accented decomposed forms, CJK, emoji,
heart+VS16, family ZWJ, flags, isolated modifiers/selectors, malformed text,
last-column clipping and replacement of wide by narrow cells. Width/emulator
disagreement is documented and solved by policy/fallback, never hidden as
universal Unicode conformance. Shared metrics cache is bounded and keyed by
text, Unicode version and width policy.

Cell = grapheme + interned effective style + occupancy (lead width 1/2 or
continuation). Continuations are not printable cells. A frame is rectangular,
completely composed and clipped before comparison. Replacing either half of a
wide glyph invalidates/clears its whole previous footprint. No split grapheme
or half-wide glyph is displayed. Clip a wide glyph that cannot fit to blank.

Keep the full-frame diff as a correctness oracle. Dirty damage is a union of
old/new bounds expanded for wide neighbors and composition overlap. Equality
includes effective style and occupancy. Resize/capability/theme policy changes
invalidate cached geometry or frame state as applicable. Avoid final-column
autowrap and bottom-right scrolling using an explicitly tested encoder policy;
if unsupported, reserve the bottom-right cell as blank.

`OutputWriter.write_frame(str)` batches each frame; front-buffer commit follows
acknowledgment of the full character count and successful flush. A short count
must advance only by that count and retry the remainder with bounded progress;
zero progress is a failed transaction. Partial write/exception leaves screen state
unknown; unwind or force a full redraw after reacquisition. Unchanged cells and
cursor/session state produce exactly zero writes and zero flushes.
Only integer counts within the remaining string length acknowledge progress;
`None`, negative and oversized counts fail. Positive short writes retry only the
unwritten suffix, so attempts are bounded by the finite frame length. Flush
failure never commits the front buffer. UI-00 promises no timeout for a blocked
OS write; transport latency and shutdown limits require backend evidence.

## 5. Events, timers, cancellation and pressure

Events: Key, Paste, Resize, Focus, Timer, Result, Progress, Quit. Each result has
a request generation so cancelled or stale results cannot replace current state.
Keyboard events remain ordered; resize/progress can coalesce by source. Paste
is text, never shortcut replay. Legacy Windows records cannot always distinguish
paste; disclose this and never bind destructive actions to ordinary text.

Frozen initial limits (tunable, not measured optimal values): 1 MiB decoded paste
measured as UTF-8, 4 KiB encoded escape sequence, 1,024 posted event envelopes,
10,000 log records of at most 4 KiB UTF-8 each including truncation markers.
Queue count does not bound arbitrary Python object graphs: envelopes carry bounded
scalars/text or identities into explicitly bounded result storage. The combined
queued text/bytes limit is 1 MiB, shared across sources including coalesced slots;
both the count and payload limits apply. UI-07 must define and test accounting for
each typed event before accepting it. Rejected payloads remain producer-owned;
referenced result storage needs its own finite application budget and release path.
These are logical payload bounds, not Python-heap guarantees.
Reject oversized paste atomically with visible feedback, consume through its end
delimiter without growing the buffer, and never replay its remainder as shortcuts.
Discard malformed/oversized escape sequences without growing the parser buffer.
Queue saturation returns failure to a nonblocking post; worker-side retry must
wait for capacity or cancellation, never spin or silently drop ordered actions.
Coalescing replaces only same-source resize/progress, within the same byte budget.
Reserved shutdown signaling remains independent. Never block the UI thread
waiting for its own queue. Native input admission must pause with retained order
when capacity is unavailable; OS-side overflow is reported when detectable, not
represented as a guarantee of lossless unbounded input.
Process at most 64 posted events or 4 ms of producer work per turn before
checking input/shutdown and due timers. These are initial scheduling policies;
verify with a fake-clock sustained 10,000-event producer that a queued key and
Quit are inspected by the next turn and no unbounded drain can starve them.
Measure real input latency under this pressure separately before accepting the
policy for release. Do not drop ordered user actions to satisfy the timing gate.

Heap timers use monotonic deadlines and deterministic sequence tie breaking.
Wait timeout is the earliest timer/render/input deadline, or infinite if idle.
One delayed timer produces one current animation state, not replay of missed
frames. Destroyed/hidden widgets cancel timers. Global reduced motion cancels
decorative timers; operation progress still updates on actual data events.
Frame ceiling starts at 30 Hz locally and 4 Hz for low-bandwidth mode; these are
ceilings, not claims of sustained throughput. Spinner uses at most 8 Hz locally.

Cancellation first stops presentation updates for the generation, requests
cooperative worker cancellation and keeps cleanup observable. Existing synchronous
services without cancellation must run off the UI thread with bounded requests;
never claim a worker has stopped when only its result was suppressed. Application
integration must provide a shutdown strategy for blocking service calls before
those flows are accepted. Avoid adding background workers at import time.

The user refined this contract: a Cancel control exists only when that operation
has a proven safe cooperative interruption mechanism. Suppressing stale results,
leaving a screen or terminating a process is not cooperative cancellation.
Current APIs without this mechanism remain executable with an indeterminate
Running state, actual final duration/outcome and no Cancel button. Determine
progress/speed/ETA only from actual total/advance/time; do not invent values.
Domain progress/cancellation extensions, if justified, are generic callbacks or
events usable by CLI/UI/external callers without domain-to-UI dependencies.
Disproportionate instrumentation is deferred with evidence rather than silently
dropping the selected capability or blocking its honest baseline integration.

## 6. Layout and application contracts

Row/Column use fixed, content and weighted remaining space; distribute rounding
left-to-right/top-to-bottom, shrink flexible items to documented minima and clip
overflow. Stack is deterministic insertion z-order. Viewport zero sizes are valid.
Scroll clamps after content/viewport changes and brings focused items into view.
Tables virtualize rows; offscreen rows do not each create a widget.

Build high-level widgets only after the UX gate supplies accepted screens and
component states. Widgets remain reusable and receive data/callbacks rather than
calling Cereja commands. The official application consumes their public API.
Its root command is opt-in and leaves existing CLI help, command dispatch and
JSON formatting contracts unchanged. UI-specific imports occur only on UI use.

## 7. Evidence, budgets and release gates

The isolated spike compares full vs dirty-cell diff and measures local imports,
rendering-model work and timers. It does not validate actual escape output,
real input-to-visible latency, complete Unicode or OS restoration. See the
evidence report for raw samples, tests, failure cases and exact coverage.

Behavioral gates are unconditional: zero unchanged writes, no periodic idle
redraw, bounded memory queues, full/dirty equivalence, no injected control bytes,
successful cleanup of every acquired resource and no UI import side effects.
Timing gates compare the same machine/interpreter/workload before and after.
Freeze baseline/environment before optimizing; report median/p95, sample count,
bytes, stream calls, peak traced memory and separate compute/terminal I/O.

Initial interaction target is p95 <=100 ms for navigation/search-result display
at 80x24 and 120x40, excluding domain search time but including event/layout/
paint/diff/encode/write. Measure actual terminal latency separately from the
virtual clock. A breach requires profiling and a documented decision, not a
silent narrower workload. Provisional import guard: root import unchanged module
set and no side effects; investigate paired median increase >max(2 ms,20%).
UI import's first baseline is measured once the skeleton exists. Neither target
is claimed achieved by this plan. These interaction/rate/import numbers are
provisional product policies, not evidence-derived performance acceptance.
The measured model supports only stage-specific comparisons in the
evidence report. #304 (CORE-PERF) must freeze core budgets from a representative
implementation baseline; #321 must freeze end-to-end budgets from a representative
application baseline before any optimization candidate is evaluated. Until
then no total latency or cross-platform performance gate is considered passed.

Release coverage: unit/contracts on Python 3.11-3.14 x Windows/Linux/macOS;
POSIX PTY integration on Linux/macOS; real Windows console integration;
manual Windows Terminal, Linux terminal, macOS Terminal and SSH checks with
emulator/version/dimensions/encoding/capabilities recorded. Test no-color,
ASCII, reduced-motion, redirected stdin/stdout, CI, Ctrl+C and broken pipes.
Use fixtures without private paths/content. Wheel/sdist installs in an empty
environment must run `cereja ui --snapshot` without downloads or extra packages.

## 8. Legacy compatibility after dogfooding

Only after toolkit/application stability, inventory `console`, `Progress`,
`State`, captures, nesting, concurrency, Jupyter, `_terminal` consumers and lazy
exports. Characterize signatures and observable output/lifecycle with fixtures.
Compare each behavior with new contracts: adapter/wrapper for matching
semantics, facade or internal refactor for ownership changes, explicit documented
migration for incompatible behavior. Preserve the maximum reasonable API without
changing the independent core. Do not preselect deprecation. Existing tests are
necessary but do not prove notebook/concurrency equivalence by themselves.

Native acceleration requires a failed agreed end-to-end budget, profiler hotspot
inside Python UI computation, tried Python/batching/invalidation improvements,
measured meaningful end-to-end benefit and identical Python fallback behavior.
Do not accelerate terminal I/O merely because a microbenchmark can be faster.

## 9. Primary references and their limits

- [Python 3.11 termios](https://docs.python.org/3.11/library/termios.html): POSIX mode capture/restoration APIs, not Cereja test evidence.
- [Python select](https://docs.python.org/3.11/library/select.html): Windows socket-only limitation motivates distinct console wait integration.
- [ReadConsoleInput](https://learn.microsoft.com/en-us/windows/console/readconsoleinput): console record input; normalized semantics require our tests.
- [WaitForMultipleObjects](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitformultipleobjects): console input and events are supported wait targets; integration remains untested.
- [Unicode 17.0 segmentation, revision 47](https://www.unicode.org/reports/tr29/tr29-47.html): pinned default boundaries; terminal widths remain separate.
- [Unicode 17.0 East Asian Width, revision 44](https://www.unicode.org/reports/tr11/tr11-44.html): property limitations; not a complete terminal-width algorithm.
- [Emoji 17.0, revision 29](https://www.unicode.org/reports/tr51/tr51-29.html), [sequences](https://www.unicode.org/Public/17.0.0/emoji/emoji-sequences.txt), [ZWJ sequences](https://www.unicode.org/Public/17.0.0/emoji/emoji-zwj-sequences.txt) and [variation sequences](https://www.unicode.org/Public/17.0.0/ucd/emoji/emoji-variation-sequences.txt): fixed inputs for the chosen emoji policy.
- [NO_COLOR](https://no-color.org/): color opt-out convention, independent from input and animation policy.

Primary references were reviewed on 2026-09-21. They support feasibility and constraints, not claims of implemented or
validated Cereja behavior. Remaining uncertainty is owned by the delivery tasks.
