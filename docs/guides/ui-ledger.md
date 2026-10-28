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

The three presentation options are independent. Interactive POSIX and Windows use require
an explicit `--bracketed-paste` assertion for a terminal supporting that protocol.
On Windows, this selects `ENABLE_VIRTUAL_TERMINAL_INPUT` and the shared bounded
escape parser. Bracketed paste produces one literal `PasteEvent`, including its
newlines and Unicode, rather than submission or shortcut events. Console modes
and the paste protocol are restored through the existing session journal.
Without the assertion, the command prints the plain reference and reads no input.
The host must preserve the protocol delimiters. Unmarked paste cannot be
distinguished from keyboard Enter; output VT support or a terminal environment
variable alone does not prove paste support. Use a supporting Windows Terminal
host rather than asserting support for a legacy console that omits delimiters.

Noninteractive input/output,
unsupported cursor transport and explicit `--plain` print a finite reference and
return without reading stdin or starting an interaction loop. Help and explicit
plain mode do not load the toolkit or acquire terminal resources. Native startup
uses the existing terminal session's capability detection and restoration.

## Commands and discovery

| Registered command | Current behavior |
| --- | --- |
| `/home` | Append a Ledger introduction. No hardware collection. |
| `/system` | Open the section form. Only explicit Run/Refresh starts basic, non-sensitive collection. |
| `/tree` | Explicit root/depth form, bounded child loads, keyboard expand/collapse and path inspection. |
| `/context` | Explicit root/query form, admission checks and cache-off text search. |
| `/compress` | Compress/decompress files or directories, then review the exact new destination. |
| `/download` | HTTP(S) URL/new destination form, exact-target review and byte-limited transfer. |
| `/examples` | Open a form for synthetic text, input or progress. |
| `/examples text`, `/examples input`, `/examples progress` | Explicitly select the corresponding bounded synthetic example. |
| `/tools` | Append the informational capability catalogue, including broader references. |
| `/diagnostics` | Append allowlisted terminal policy booleans, versions and logical retention size. No environment/argv, host identifiers, paths, inventory or export. |
| `/help`, `/help NAME` | General or named capability help. |

Grammar is a finite case-sensitive registry. It accepts no shell/Python evaluation,
pipelines, arbitrary function invocation, newline commands or domain argument
passthrough. Invalid input remains in the composer, with a non-echoing error.
`Available UI` identifies executable application behavior within the supported limits below. System is executable on Windows/Linux/macOS; other hosts show a reason in its form/help. `CLI` and `Python API` independently
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

(system-integration-314)=

## System integration (#314)

Submit `/system`, edit the comma-separated section names, then select Run/Refresh.
Opening the form, Home, catalogue, help or importing the application never collects.
The default explicitly selects `system,os,cpu,memory,gpu,motherboard,bios`. Unknown,
empty or duplicate names are rejected. Only `basic` detail and
`include_sensitive=False` are used; full/sensitive switches are not offered.
Values are read-only section headings and key-value rows in the existing selectable,
scrollable result surface. Names are the typed API field names; `_bytes` means bytes,
`_mhz` MHz and `_mts` MT/s. Missing values/empty sections say Unavailable, never zero.
An actual numeric zero remains zero. The facade has no per-field error/warning
channel; the UI neither infers a cause nor manufactures collector warnings.

The synchronous `cereja.system.hardware.info` call runs on the existing bridge's
worker. Navigation, editing, help, selection, scrolling and resize remain available.
A second Run/Refresh is explicitly rejected; no invocation is queued. Prior snapshots
remain separate selectable blocks during refresh and after a failure, subject to the
existing oldest-completed eviction policy. Each successful snapshot includes UTC
observation time and actual monotonic facade duration. Focus, draft and anchors are
preserved; only an existing follow-latest state follows the new result.

The loading indicator activates only on observed Running. Request elapsed time uses
the real monotonic clock from explicit admission (including scheduling/publication),
so it differs from final facade duration. Decorative indicator ticks update the
visible elapsed label, without changing canonical result identity/revision. With
reduced motion or hidden feedback it updates on actual input/state/render events;
there is no timer merely to update time. Conclusion/hiding/disposal releases the
existing shared indicator timer. System clears previous synthetic numeric progress.
There is no percentage, speed, ETA, internal phase, Committing or Cancel claim.
Exit offers Stay or Wait, and Wait can be withdrawn. Consumer/terminal loss detaches
observation; it does not interrupt synchronous I/O. No UI join or global shutdown
deadline is promised. Platform subprocess timeouts do not bound the whole call;
section selection can still perform other collector work.

The adapter consumes `HardwareInfo` and exact section models, without parsing CLI
text or calling `to_dict()`. An explicit field allowlist excludes hostname, machine,
serial numbers, UUID, CPU identifier, memory part/bank/device labels, boot/install
times and locale. It is not arbitrary secret detection in vendor/model strings.
Only a sanitized string crosses the unchanged operation-event accounting. The
worker-owned domain graph is released after projection; there is no result mailbox.
Projection caps: 32 entries per array section, 512 UTF-8 bytes per scalar and 12 KiB
section text, with visible truncation. Unexpected models/scalars fail explicitly.
Duration/time headers fit the independent 16 KiB result block cap. The bridge's
64 KiB event cap, core 1,024 envelopes/1 MiB aggregate, and Ledger 20 completed/
256 KiB retention are unchanged. These are logical payload caps, not heap/RSS caps.
Results stay in ephemeral memory. Diagnostics exports no inventory. Collector errors
publish a fixed class/duration message, excluding exception arguments; start/cleanup
and observation failures have distinct non-success outcomes.

The domain API remains unchanged:

```python
from cereja.system.hardware import info
snapshot = info(detail="basic", include_sensitive=False, sections=("os", "cpu"))
assert snapshot.cpu is None or snapshot.cpu.cores is None or isinstance(snapshot.cpu.cores, int)
```

This performs one synchronous local call with no whole-call deadline. For a bounded,
terminable synthetic integration, independent of native collector availability:

```text
python -B -S -m unittest tests.test_ui_ledger_system
python -B -S benchmarks/ui_system.py --samples 3 --warmup 1 --output report.json
```

Add `--native-samples 3` only to measure the owned host. The harness has a 30-second
observation watchdog, which cannot stop a blocked collector. The report stores no
raw inventory, identity or secrets. See [native API/platform limits](system-info.md).
Fixtures for other platforms do not prove native collection on those platforms.

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

The automatic Windows ConPTY test runs the official entry with native input and
output. It checks literal multiline/Unicode paste, no operation start, copy priority,
idle exit and console-mode restoration. The test host sends complete protocol
delimiters; backend tests separately split delimiters and UTF-16 pairs across record
reads and check rejected/unfinished paste, wake fairness, deadlines and acquisition
failures. Neither establishes a human clipboard roundtrip or support in every host.
On this Windows build, a ConPTY host write ending inside the opening delimiter can
be consumed by the console before the application receives it. Such host-side
fragmentation is outside the verified input contract; the application cannot
reconstruct an absent delimiter. The explicit assertion includes preservation of
complete delimiters, as emitted by a supporting terminal's paste action.

## Initial Windows baseline (2026-10-11)

Raw samples and virtual keyboard snapshots (`benchmarks/ui_ledger_samples/baseline-windows-py314.json`, local only)
retain environment, source fingerprints, 31 samples after three warmups per timing
case, and three separate fresh-process traces per retention fixture. CPython 3.14.5
on Windows. Fingerprints normalize CRLF to LF for comparison with published Git
blobs. The recorded base HEAD/dirty state describes precommit collection, not a
claim that the base commit contains the measured application.
These measurements describe the initial `ff539bb` delivery before the Windows
VT-input continuation. Its source fingerprints remain historical evidence.

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
corrections. Automated Windows ConPTY and POSIX PTY checks are available;
clipboard roundtrips and human accessibility/usability acceptance remain unperformed. The automated POSIX
PTY smoke exercises the official entry and native restoration when run on POSIX;
it is not a participant walkthrough.

## Windows input continuation measurements

Raw continuation samples (`benchmarks/ui_ledger_samples/windows-input-windows-py314.json`, local only)
record 31 timing samples after three warmups on CPython 3.14.5/Windows, with
45 source fingerprints. Catalogue import/discovery median/p95 was 10.672/13.539 ms;
application import 41.439/50.775 ms; import/construction/first virtual CellBuffer
49.438/55.237 ms. All startup cases observed zero new threads and no domain/legacy
imports. These remain virtual startup/frame measurements, without native input or
presentation latency. Process-wall samples and dispersion are retained; OS caches
and unrelated host load are uncontrolled. No speedup is inferred from the initial
baseline. This `--smoke` collection omits the large retention stress fixtures;
their earlier calibration is preserved above.

## APP-02 Windows measurements (2026-10-13)

Raw timings and source fingerprints (`benchmarks/ui_system_samples/windows-py314.json`, local only)
were collected with `python -B -S benchmarks/ui_system.py --samples 31 --warmup 3
--native-samples 11 --output benchmarks/ui_system_samples/windows-py314.json`.
Each scenario used three warmups, CPython 3.14.5, real monotonic clocks, sequential
runs and an 80x24 virtual terminal. Sections: os/cpu; basic, non-sensitive. No raw
inventory or machine identifiers are retained. The report's base HEAD is the
precommit base; Git/LF source fingerprints bind the measured implementation.

| Window | Fixture median/p95 ms | Windows native median/p95 ms |
| --- | ---: | ---: |
| Facade (fixture blocks 60 ms) | 60.440/69.800 | 2055.509/2336.825 |
| Explicit admission through final consumption | 65.658/101.323 | 2108.708/2384.498 |
| Synthetic input handle including CellBuffer | 0.727/1.616 | 1.036/2.194 |
| Final CellBuffer | 1.075/2.513 | 2.311/3.502 |
| Fresh renderer and memory sink | 16.087/31.502 | 28.674/99.917 |

The fixture has 31 samples; native collection has 11. Native runs each handled
five synthetic inputs while Running. Fixture input counts can be smaller when
collection finishes first. Input samples/counts, scheduler-turn samples, MAD,
min/max and logical retention size are recorded separately in the JSON.
Integration includes projection, scheduler/render work, publication and the
harness's 1 ms observation waits. The native facade window does not include
projection. Scheduler-turn timing can include rendering; the isolated fresh
renderer measurement uses a memory sink and is not additive to integration.

External load, power, affinity and OS caches were uncontrolled. Native Windows
collection is measured; Linux/macOS native collection is not. No real transport
latency/presentation, participant input experience, global call/shutdown deadline,
clipboard roundtrip or heap/RSS bound follows. Existing ConPTY regression checks
cover native paste/copy priority/exit/mode restoration, not a measured System
collection-to-screen or human task trial. Human terminal/accessibility/usability
acceptance remains pending. Publication and exact-revision CI are tracked in #314.


## Tree, Context, Archives and Download

Tree uses the [structured repository API](repository-traversal.md), independent
of terminal widgets. Root and depth (0..8) are explicit. Discovery does not scan.
The worker returns at most 48,000 JSON bytes; one UI-owned TreeView retains at
most 64 nodes and 48,000 logical payload bytes. Each load examines at most 2,048
entries with a 256-entry per-directory cap. Loading a nested node revalidates
its ancestor chain within those budgets, so repeated loads can repeat work.
These are per-load and retained-widget bounds, not aggregate session work or RSS.
Right expands/loads, Left collapses/selects parent, and Enter inspects the full
safe path. Names and paths remain data; controls are escaped for presentation.
Incomplete enumeration and omitted counts remain explicit. A new Tree command
replaces the interactive tree; older result summaries remain within Ledger
retention. This is read-only traversal, without file opening or mutation.

Context uses the existing typed API with cache off, eight results, two snippets
per result, 240 characters per snippet and 256 KiB per file. Admission requires
an owned, stable root with at most 64 files, 16 MiB inventoried source bytes,
257 tree nodes, depth 8 and 2,048 examined entries. An incomplete admission scan
is refused. The subsequent existing search enumerates again; concurrent source
mutation can invalidate admission. There is no hard whole-scan/deadline guarantee.
Use only stable owned workloads within those limits. Literal snippets and paths
are safely rendered; skipped reasons, no matches and truncation remain visible.
Result text is capped at 12 KiB and uses existing canonical selection/scrolling.
No automatic opening, persistent cache or file writes occur.

Archives follow the [bounded domain contract](bounded-archives.md). The form
selects compress/decompress, file/directory, source and new destination. The
exact-target review defaults to Back; Run becomes available after the details
are inspectable. Changes to the form or target invalidate consent. Existing
targets are refused both before work and during exclusive publication. There
is no overwrite, merge, source deletion, password storage or generic extraction.

Download accepts HTTP(S) without credentials or fragments, verifies TLS, follows
at most five redirects and uses 10-second connection/read timeouts with no retries.
It writes at most 16 MiB to owned staging and publishes a new destination only.
The source URL remains explicit in review; redirected URLs do not select or
rename the destination. Known and unknown totals display actual received bytes
with indeterminate activity; no percentage, speed or ETA is inferred from remote
metadata. Length mismatches, limits and transport errors abort partial output.
The transfer layer adds optional `max_bytes`, `overwrite=False` and
`before_commit` arguments to the synchronous API. Existing defaults remain.

All four workflows reuse one active operation and the existing scheduler/bridge.
There is no automatic queue or domain Cancel. Actual Running/Committing phases,
elapsed time and final outcome are distinguished. Busy requests are explicitly
rejected. A failure during publication/cleanup can leave an output; inspect the
exact destination when the result warns about uncertain publication. Consumer
loss does not interrupt blocking I/O or prove cancellation. No global deadline
is claimed. Real clipboard transport remains unavailable.

### Candidate measurements and acceptance

`python -m benchmarks.ledger_workflows --output NEW.json` measures only owned
fixtures. Raw Windows/Python 3.14 samples are in
`benchmarks/ledger_workflow_samples/windows-py314-final.json` with source fingerprints,
11 measured samples after three warmups, median/p95/MAD and traced allocation.
The windows include admission, worker publication, scheduler, CellBuffer/memory
sink and harness observation waits. They are not terminal presentation latency,
human response time, RSS limits or performance-improvement evidence.

Automated integration and native transport checks do not establish a human
keyboard/clipboard/accessibility walkthrough. Linux/macOS directory extraction
is explicitly unsupported by this bounded API. Native collection, presentation
and human acceptance still require the observations tracked in
[#321](https://github.com/cereja-project/cereja/issues/321). Legacy migration remains
separate and must not proceed before a recorded stable-contract decision.
