# Initial five operations: source contracts and implementation gaps

Status: source-grounded planning proposal, not implementation acceptance. The user
selected System Information, Tree with an explicit path, Context Search with
explicit roots, Compress/Decompress as one area, and Download with URL and
destination. The bounds below elaborate that selection; they do not silently
remove directory operations or decide encryption scope for the user.

Authoritative interaction decision: long operations may ship with indeterminate
Running and actual final duration/result/error. Percent, speed, ETA, and Cancel
must not be invented. Cancel is unavailable unless safe cooperative interruption
is proven for that operation. Generic domain instrumentation is separate follow-up
work and must not block the functional baseline merely because it is absent.

Inspected at `ed7fbfa5bc08f3e5814602f1cb3f09e3d6ad5d87`. This report uses source
inspection, not execution of private files, external URLs, or hardware collection.
No production code changed. Line numbers below refer to that checkout.

## Existing entrypoints and result contracts

| Area | Public API and source location | Data boundary | Actual progress/cancellation |
| --- | --- | --- | --- |
| System Information | `cereja.system.hardware.info(detail="basic", include_sensitive=False, sections=...)`; [collector.py](../../cereja/system/hardware/collector.py), line 13. CLI: `cereja system info`. | Existing `HardwareInfo` dataclass and section models, [models.py](../../cereja/system/hardware/models.py), line 90. Do not parse formatted terminal output. | Synchronous final result; no progress/cancel parameter. Windows/macOS collectors have subprocess phases with 10-second timeouts; there is no demonstrated whole-call deadline. |
| Tree | `cereja.system.render_repository_tree(path, depth=...)`; [_repository_tree.py](../../cereja/system/_repository_tree.py), line 16. CLI: `cereja tree PATH --depth N`. | Returns one formatted Unicode string, not typed tree nodes. This is a service gap for the selected hierarchical TreeView: introduce structured traversal results reusing current filtering rules, never reverse-parse glyphs. | Synchronous traversal; no progress/cancel callback. Depth limits recursion, not directory breadth or rendered length. |
| Context Search | `cereja.system.search_text_context(roots, query, ...)`; [search.py](../../cereja/system/_context/search.py), line 17. CLI: `cereja context search --root ROOT --query QUERY`. | Existing `ContextResponse`, `ContextResult`, `ContextSnippet`, `SkippedFile`; [models.py](../../cereja/system/_context/models.py), lines 7-37. Keep scores, truncation, and skip reasons. | Synchronous final response, no cancel/progress parameter. `max_results` is applied after traversal and collection, not a visited-file or memory bound. |
| Compress/Decompress | `cereja.hashtools.compress_file`, `compress_dir`, `decompress_file`, `decompress_dir`; [_compress.py](../../cereja/hashtools/_compress.py), lines 686, 976, 740, 1233. CLI: `cereja compress`, `cereja decompress`. | Compression returns `(path, CompressionStats)`; decompression returns path only. Adapter adds operation kind, output kind, bytes if measured, and actual commit/cleanup status. | `verbose=True` drives legacy display internally; not a callback. Use `verbose=False`. No cancel token, byte progress, or structured partial-failure result. Never scrape console output to manufacture progress. |
| Download | `cereja.transfers.download(url, destination, client=..., progress=..., chunk_size=..., timeout=...)`; [download.py](../../cereja/transfers/download.py), line 22. CLI: `cereja download URL -o DESTINATION`. | Existing `TransferProgress(bytes_transferred, total_bytes)` and `DownloadResult(path, bytes_transferred, total_bytes, status_code)`; [models.py](../../cereja/transfers/models.py), lines 6 and 12. | Real callback after each written chunk. No cancel-token parameter. A callback exception aborts the transfer through `except BaseException`, but cannot interrupt a currently blocked read or prevent a commit race after the last callback. |

## Flow bounds and user-visible behavior

### System Information

Require an explicit Run/Refresh action. Default basic, non-sensitive fields and
show unavailable sections as unavailable, not zeros. No automatic periodic
hardware scan. Selected sections do not necessarily reduce all platform collector
work. The Windows collector can invoke external system commands, so hiding the
screen does not imply collection stopped. No network service is required by the
inspected facade; do not persist machine identity in application history by default.

Proposed UI: section selector, read-only values, Refresh, loading with elapsed
time, and warning details. No Cancel action until cooperative stop is supported
and verified. Waiting for collection to finish is not cancellation.

### Tree

One explicit root path and a hierarchical TreeView with keyboard navigation,
selection, expansion/collapse, and visible focus. This does not authorize a general
filesystem browser, editing, moving, or deletion. Existing code rejects symlink roots
and does not descend child links. It honors filtering implemented by Cereja;
do not promise exact Git behavior beyond existing traversal tests.

Introduce a generic domain-level structured traversal result, for example
`TreeNode(id, parent_id, relative_path, name, kind, load_state)` plus a bounded
`ChildrenResult(nodes, complete, omitted_count_or_unknown, error)`. IDs derive
from root identity and normalized relative path, not list position or display
text; state preserves selected/expanded IDs across loaded pages and handles
disappeared nodes explicitly. Links are displayed but not descended. Child loading
must preserve inherited ignore rules and deterministic ordering. UI widgets consume
these records independently of filesystem code; the current CLI text renderer can
later consume the same service without making legacy display a core dependency.

Source-size evidence favors a small extraction over a separate traversal rewrite:
the existing tree formatter is 64 lines, `_repository_files.py` is 288 lines with
reusable filtering/root helpers, and `_directory_entries.py` already provides
non-recursive enumeration through `os.scandir`. These counts are an effort signal,
not proof that extraction is trivial. Existing `iter_repository_files` returns
files only, so it cannot by itself represent empty directories or lazy children.
Reuse tested rules and introduce an explicit public/internal domain boundary;
do not copy private ignore implementations into widgets.

Proposed budgets for validation: default depth 3, maximum 5,000 retained visible
nodes, bounded enumeration/time per load, and explicit incomplete/loading/error
nodes. Wide-directory sorting currently materializes children; true bounded lazy
loading requires a documented ordering/paging strategy and tests, not merely
clipping output after full traversal. This structured result is necessary for the
selected TreeView interaction. Detailed byte/percent progress remains optional:
child loads may show indeterminate Running with no Cancel. Never perform a second
unbounded pre-scan just to estimate progress. Acceptance includes stable selection,
expand/collapse, lazy-load boundaries, filtering parity, empty directories, links,
disappearing entries, permission failures, and bounded queue/node retention.

### Context Search

Require explicit roots, nonempty AND-term query, optional extensions, and Run.
Preserve current defaults: 10 results, two snippets per result, 240 characters
per snippet, and 1 MiB per file. Cache defaults off. Enabling cache explicitly
permits local per-user cache writes; it must not be described as read-only overall.
Cache management is outside this selected search flow.

Render result list, selected snippet, skipped-file counts/reasons, and truncation
state. Treat file text and filenames as untrusted display data. Do not automatically
open external editors or execute snippets. Result caps do not bound scanned files:
[search.py](../../cereja/system/_context/search.py), lines 130-211, accumulates
results and skipped entries before finalization. A scan budget, cancellation checks,
bounded retained matches/skips, and honest partial-result metadata are service work
needed before a large-root responsiveness guarantee. A budget hit is an incomplete
search, not "no matches". The current API remains executable with indeterminate
Running and no Cancel; instrumentation does not block that baseline. Multi-root
failure semantics also need explicit tests.

### Compress/Decompress

Use one area with mode, source path, output path, source/archive kind and strategy.
Both file and directory APIs exist. Recommended staging sequence: single-file
flows first, then directory flows in the same area after extraction/path/volume
gates pass. This is sequencing, not authorization to remove directory support.
The user still needs a clear proposal for encrypted archives and passwords;
encryption must not appear merely because the CLI exposes it.

The existing single-file functions read the entire input and materialize output
in memory. They open final destinations with `wb`, so failures can leave partial
output and existing content can be replaced. Directory compression streams chunks
but normally writes the final archive directly; its temporary archive path is
specific to encrypted processing, not universal atomic publication. It can skip
unreadable files and log warnings without including omissions in `CompressionStats`.

Directory decompression writes members directly into the destination tree.
`_safe_archive_path` provides path checking, but there is no public expanded-byte,
member-count or cancellation limit. Lexical path checks alone must not be advertised
as proof against all symlink/race scenarios. Compressed input size cannot bound
decompressed size. Legacy directory format materializes the archive in memory.
Do not infer successful all-or-nothing extraction from a returned path.

Output-safety work and separately tracked service improvements:

- Never allow source and destination to identify the same file. Require an explicit
  destination and verify parent/type rules; never silently infer overwrite consent.
- Produce an owned staging file or directory beside the final output, commit only
  on success, clean only owned temporary paths, and preserve the old destination on
  failure. Directory merge/replace is not the same operation as atomic file replace.
  Recommend new-directory-only extraction initially; expose that limitation clearly.
- Default to fail if the destination exists. A preflight `exists()` check is not
  race-safe no-clobber behavior; publication needs an independently tested contract.
- Add output-byte/member limits within decompression before claiming bounded memory
  or disk use. Proposed starting budgets for review: 16 MiB single-file input,
  256 MiB expanded output and 1,000 directory members.
  These numbers are product defaults awaiting workload validation, not current API limits.
- Investigate generic domain progress callbacks/cooperative cancellation between
  chunks/members for CLI, UI, and external callers; keep domain services independent
  of the UI. Record cost/evidence and defer detailed instrumentation if disproportionate.
  This must not block executable compression with indeterminate Running, actual
  final duration/result/error, and no Cancel. Structured omission/error reporting
  remains a separate correctness concern. Existing verbose single-file progress advances after reading,
  before compression and output commit, so it is not total-operation progress.

### Download

Require URL and destination; HTTP(S) download only, no request-method editor,
arbitrary headers, body composer, or general HTTP-client screen. Preserve TLS
verification. Treat query strings/userinfo as potentially secret: redact diagnostic
URLs and do not persist them as history by default. Redirect policy must be explicit
and tested rather than implied by a URL field.

Use actual `TransferProgress` events, coalesced for display. Show determinate bytes
only when a trustworthy positive total is available; otherwise show transferred
bytes and activity. Callback totals originate from Content-Length, not measured
final length. Completion is after successful commit, not after the last progress event.

[AtomicFileSink](../../cereja/transfers/sinks.py), lines 14-38, creates missing parents,
writes a sibling `.part`, flushes/fsyncs, and calls `os.replace`; `abort()` removes
its owned partial file. This preserves the old destination during ordinary transfer
failure, but the library unconditionally replaces it at commit. CLI `--force`
protection is a preflight check, not a transfer API no-clobber guarantee.

There is no transfer-byte cap in `download`. An adapter callback can reject a
threshold after a chunk was written and trigger cleanup; the temporary file can
therefore exceed that threshold by a chunk. It is not a pre-write disk bound.
Propose a reviewed 256 MiB default and explicit override only after volume/error
behavior is tested. Unknown content length must not disable the byte budget.

Synchronous callback cancellation is possible between chunks by raising an owned
exception, provided tests establish abort, old-output preservation, and closure.
It does not give immediate cancellation during DNS/connect/read or after the final
callback. The library also offers `async_download`, but its use of background
file writes via `asyncio.to_thread` requires cancellation/cleanup race validation;
its existence is not proof of safe interruption. Do not switch the toolkit to an
async-first architecture solely for this operation.

For the baseline flow, Cancel is unavailable pending proof of safe cooperative
interruption including the final-callback/commit boundary. Actual byte callbacks
can still provide progress without implying cancellation support or promising
speed/ETA. Missing cancellation does not block functional download execution.

## Common worker and output lifecycle proposal

Use one active background operation across the five areas, without an automatic
job queue or silent starts. The user's asynchronous/concurrent I/O requirement
means the UI remains responsive alongside background work; it does not require
multiple simultaneous downloads. Multiple transfers are deferred. The active
blocking call uses its own worker and, for downloads, an owned client/sink.
Workers return typed data and never write to the terminal. UI-owned state and
bounded messages remain common. Progress is coalescible per operation ID; final
completion/error is not discardable. Navigation and activity remain usable while
work runs. Starting another operation explicitly reports the current busy state.
Changing screens leaves operations visible in status and does not secretly
cancel them. Single-operation scheduling also prevents concurrent UI writers
against the same destination; it does not eliminate external filesystem races.
Running Cancel remains unavailable without the validated cooperative contract.

`Idle -> Validating -> Running -> Committing -> Succeeded` with separate
`Failed` and `CleanupFailed` states. `CancelRequested` and `Cancelled` are optional
states only for operations whose safe cooperative cancellation has been validated. A request
becomes Cancelled only after the operation is stopped and owned resources are
settled. During commit, stop is unavailable and this state should be brief.

For the current synchronous tree/search/system/compression APIs, a thread keeps
the UI responsive but cannot guarantee stopping work. Use no Cancel in that
baseline. Investigate minimal generic service hooks separately; do not kill Python
threads or label discarded results as cancelled work. Process termination is not
an accepted substitute for cooperative cancellation.

Quit while work is active needs an explicit flow: stay or wait for completion;
offer cooperative stop only if that operation has validated support. Do not block
UI input while joining a worker. Hard shutdown latency
cannot be promised until blocking I/O and collector subprocess cleanup are tested.

## Evidence required before these flows are accepted

A bounded runtime download probe is recorded in
[download-loopback.json](../../benchmarks/ui_spikes/download-loopback.json), produced
by [download_probe.py](../../benchmarks/ui_spikes/download_probe.py):

```text
python benchmarks/ui_spikes/download_probe.py --output benchmarks/ui_spikes/download-loopback.json
```

On the current Windows/Python 3.14.5 runtime, an owned loopback HTTP server returned
the same 1,536-byte fixture with known and absent Content-Length. Both transfers
produced real monotonically increasing progress callbacks and byte-identical final
files. Totals were 1,536 and null respectively. An exception from the first 128-byte
callback propagated, preserved a pre-existing destination containing `original`,
and left zero partial files. Server shutdown and fixture directory cleanup passed.
This proves those bounded runtime cases only. It does not certify cooperative
Cancel, blocked-read interruption, final-chunk/commit races, all failure cleanup,
network confidentiality, or multiple transfers. No external URL or user data was used.

Tests must cover all five successful operations on owned fixtures, invalid inputs,
empty results, broad/large input budgets, truthful activity/progress, state changes,
and output sanitization. Compression/download additionally need old destination
preservation, commit races, disk/permission errors, cancellation around last chunk
and commit, and cleanup failure visibility. Directory extraction needs traversal,
links, malformed archives, member/output limits, and partial-error cases. Download
tests should use controlled loopback HTTP with unknown length, delay, truncation,
error status, and redirect fixtures before any external-network dogfood run.

These are narrow integration prerequisites for the selected product flows, not a
request to rewrite unrelated Cereja functionality or couple the UI core to display.
