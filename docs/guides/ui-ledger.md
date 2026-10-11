# Ledger terminal application

APP-01 / [#313](https://github.com/cereja-project/cereja/issues/313) composes the
public `cereja.ui` toolkit into `cereja ui`. Python 3.11+, standard library only.
No root exports, legacy display initialization or mandatory dependencies are added.

```text
cereja ui
cereja ui --bracketed-paste
cereja ui --no-color --ascii --reduced-motion
cereja ui --low-bandwidth
cereja ui --plain
```

The three presentation options are independent. Interactive POSIX use requires
an explicit `--bracketed-paste` assertion for a terminal supporting that protocol.
Unmarked paste cannot be distinguished from keyboard Enter by the existing native
transports. Windows console record input explicitly lacks paste identification;
`cereja ui` therefore returns the plain reference on Windows. It does not enter
raw mode or present an executable composer there. This is a concrete outstanding
native-input limitation, not verified Windows interactive acceptance. Adding a
paste-aware Windows transport or changing the approved submission grammar requires
a separately scoped decision; this increment does neither.

Noninteractive input/output,
unsupported cursor transport and explicit `--plain` print a finite reference and
return without reading stdin or starting an interaction loop. Help and explicit
plain mode do not load the toolkit or acquire terminal resources. Native startup
uses the existing terminal session's capability detection and restoration.

## Commands and discovery

| Registered command | Current behavior |
| --- | --- |
| `/home` | Append a Ledger introduction. No hardware collection. |
| `/system`, `/tree`, `/context`, `/compress`, `/download` | Open Planned UI reference help with verified CLI/API entries and expected parameters. No domain execution or misleading Run action. |
| `/examples` | Open a form for synthetic text, input or progress. |
| `/examples text`, `/examples input`, `/examples progress` | Explicitly select the corresponding bounded synthetic example. |
| `/tools` | Append the informational capability catalogue, including broader references. |
| `/diagnostics` | Append allowlisted terminal policy booleans, versions and logical retention size. No environment/argv, host identifiers, paths, inventory or export. |
| `/help`, `/help NAME` | General or named capability help. |

Grammar is a finite case-sensitive registry. It accepts no shell/Python evaluation,
pipelines, arbitrary function invocation, newline commands or domain argument
passthrough. Invalid input remains in the composer, with a non-echoing error.
`Available UI` identifies executable local application behavior; `Planned UI`
identifies the five unimplemented integrations. `CLI` and `Python API` independently
identify existing entrypoints. `Reference` entries never promise a future UI.
Static catalogue discovery imports no service, starts no worker and does no I/O.

Typing `/` opens prefix suggestions. Enter/Tab inserts and closes discovery.
Only a later Enter submits. Pasting is bounded literal editing, including newline
and slash. The composer retains at most 4096 safe UTF-8 bytes; the transport and
event admission bounds remain independent. Typing `q` is ordinary text.

## Focus, results and overlays

The four-row composer dock persists at 120x40, 80x24 and 40x12. A separate pager
precedes it. Result blocks have stable identities and chronological order; the
selected payload and preceding header are displayed, with other blocks reachable
by Left/Right on the block header. Text wraps by the toolkit's grapheme metrics.

Tab traverses composer, selected block, content, Copy, Latest (when applicable),
Help and Exit. Shift+Tab reverses. Block Home/End selects oldest/latest. Content
PageUp/PageDown scrolls with an overlap; Home/End reaches content boundaries.
Scrolling or selecting an earlier block disables following latest. Latest explicitly
resumes it. New output and operation completion do not change focus, draft or an
open overlay. F1 opens help; Escape restores its invoking state. Forms retain safe
values on Back/reopen. Below 40x12, hidden editing is suspended while state and
operation status survive; Ctrl+C still follows copy/exit ownership.

Ctrl+A on content selects the whole canonical result. Editing fields support
grapheme-range selection through Shift+arrows. Clean copy uses canonical content,
revision and logical offsets, preserving tabs, blank lines and intentional spaces.
Padding, wrapping, markers and style do not become copied text. A selection of an
active result pins its old canonical revision when completion changes the result.
Pinned text stays inspectable and is counted in retention. Escape from content
clears it. A block-header selection alone is navigation, not text selection.

Clipboard transport remains unavailable. Ctrl+C with an owning textual selection
reports Copy unavailable and preserves it. It never falls through to exit or Cancel.
Explicit Copy also reports unavailability. No clipboard write or roundtrip is claimed.

## Retention and privacy

Results are memory-only; no command/draft history is written to disk. They retain
registered command names and application-generated safe output, never raw command
arguments or failed input. Example form text is not appended to results or diagnostics.
Terminal-control sanitization is not arbitrary secret detection: future adapters
must redact before creating widgets, events or result payloads.

The calibrated defaults are 20 completed blocks, 256 KiB aggregate canonical
UTF-8 payload and 16 KiB per block, plus one active identity inside the byte budget.
The earlier 2 MiB proposal remains a comparison candidate, not the selected bound.
Oldest completed results are removed first; active identity is never
evicted. Selection falls to the next survivor, then previous/empty. The pager shows
omission count; truncated content contains an explicit marker. Logical bytes count
identity, command, state, canonical text and any pinned prior revision. They do not
bound Python objects, Unicode metrics/caches, frame buffers, workers or RSS.

## Operations and synthetic examples

The application owns one OperationBridge and reuses the existing EventLoop,
posting, requests, generations, cancellation, wake and shared feedback timers.
It creates no parallel queue or scheduler. A second operation is rejected without
queueing. Worker phases and final delivery are distinct. Missing/failed final
publication becomes Unavailable, never a displayed success. Failed and CleanupFailed
remain distinct. The UI never joins workers or writes from them.

Text/layout uses labelled synthetic Unicode and hostile-control fixtures. Input
uses a 64-byte synthetic editor and is ended with Done/Back. Progress runs at most
20 finite memory batches, deliberately paced at 50 ms between observed counts.
Counts are real completed synthetic batches, not domain telemetry. There is no
fabricated speed/ETA or success at 100%. This fixture's cooperative cancellation
is checked between finite batches and has no owned external resources. It certifies
only itself, never existing Cereja services or a maximum shutdown deadline.

Ctrl+C without owning text selection requests exit. During work the default is
Stay; Wait returns to responsive navigation and exits after actual worker completion
and final consumption. Ctrl+C then Stay withdraws that wait. Cancel appears only
while the bridge's tested synthetic capability is usable. Terminal loss closes the
consumer without claiming worker exit. ActivityIndicator, ProgressBar and InlineStatus
share the core policies; final/hidden/static feedback releases periodic timers.

## Embedding and reproducible verification

```python
from cereja.ledger.app import Ledger
from cereja.ui.events import KeyEvent, PasteEvent
from cereja.ui.terminal import TerminalSession
from cereja.ui.testing import VirtualBackend

with TerminalSession(VirtualBackend(size=(40, 12))) as session:
    app = Ledger(session)
    try:
        app.handle(PasteEvent('/ex'))
        app.handle(KeyEvent('enter'))  # insertion, no work
        assert app.composer.text == '/examples '
        assert not app.bridge.active
        app.handle(KeyEvent('enter'))  # parameter form
        assert app.overlays.top.identity == 'examples-form'
    finally:
        app.close()
```

```text
python -B -S -m unittest tests.test_ui_ledger tests.test_ui_ledger_imports
python -B -S benchmarks/ui_ledger.py --demo
python -B -S benchmarks/ui_ledger.py --samples 31 --warmup 3 --memory-samples 3 --output report.json
```

Tests audit every claimed CLI/API, lazy imports, safe grammar, real synchronized
workers, failure/publication paths, virtual keyboard/layout continuity, retention
and modes. Benchmarks record fresh-process startup separately from warmed in-process
command-to-CellBuffer work and untimed tracemalloc retention. OS caches are uncontrolled.
No terminal presentation, human input/acceptance, clipboard, RSS or global memory
bound follows from those measurements. Exact publication/CI disposition belongs to
#313 and coordination #306. Real terminal and participant acceptance remain separate.

## Measured Windows baseline (2026-10-11)

[Raw samples and virtual keyboard snapshots](../../benchmarks/ui_ledger_samples/baseline-windows-py314.json)
retain environment, source fingerprints, 31 samples after three warmups per timing
case, and three separate fresh-process traces per retention fixture. CPython 3.14.5
on Windows. Fingerprints normalize CRLF to LF for comparison with published Git
blobs. The recorded base HEAD/dirty state describes precommit collection, not a
claim that the base commit contains the measured application.

| Fresh process window | Median ms | p95 ms | MAD ms |
| --- | ---: | ---: | ---: |
| Root import | 1.278 | 1.322 | 0.021 |
| Catalogue import and discovery | 9.928 | 11.421 | 0.241 |
| Application import | 38.054 | 42.486 | 1.390 |
| Plain entry | 25.887 | 29.677 | 1.016 |
| Application import, construction and first CellBuffer | 44.794 | 48.655 | 1.379 |

These windows exclude the common harness imports; outer process wall time, raw
samples, minimum/maximum and module counts are also retained. All cases observed
zero new threads and zero imported domain/legacy modules. Fresh processes are not
OS-cold filesystem caches. The first frame uses a virtual terminal, not native
transport or screen presentation.

For `/tools` Enter through handler and CellBuffer, warm in-process median/p95 were
28.298/46.174 ms at 120x40, 23.910/39.128 ms at 80x24, and 23.249/41.812 ms at 40x12.
This excludes scheduler pacing, renderer acknowledgement and concurrent producer
pressure. It does not inherit or establish the earlier bridge's responsiveness
results. Timings are observations, not a latency guarantee or optimal frame rate.

| Retention fixture (21 insertions) | Completed retained | Logical bytes | Median traced bytes retained / peak |
| --- | ---: | ---: | ---: |
| 1 KiB blocks, selected defaults | 20 | 21,012 | 2,443,541 / 2,462,984 |
| Candidate 64 KiB blocks, 2 MiB aggregate | 20 | 1,311,252 | 158,446,284 / 167,620,848 |
| Selected 16 KiB blocks, 256 KiB aggregate | 15 | 246,162 | 29,624,930 / 31,902,729 |

The first fixture evicted one completed block by count; the selected large-payload
fixture evicted six by bytes. Each trace starts with fresh application/metrics
caches and excludes imports. These observations justify reducing the candidate
payload allowance while retaining twenty short summaries. They do not establish
an optimal budget, total live heap, RSS or a global application memory ceiling.
Canonical metrics, caches and temporary objects explain the difference from
logical payload. Core envelopes (1024/1 MiB), operation events (64 KiB), collection
limits and worker ownership remain separate and unchanged.

Direct review covered grammar/discovery truth, compact field revelation, pager
residue, pinned revisions, active-result eviction, delivery loss, Cancel phase
visibility and disposal. Requirement tests retain regressions for the observed
corrections. Windows interactive Ledger, clipboard roundtrips and human
accessibility/usability acceptance remain unperformed. The new automated POSIX
PTY smoke exercises the official entry and native restoration when run on POSIX;
it is not a participant walkthrough.
