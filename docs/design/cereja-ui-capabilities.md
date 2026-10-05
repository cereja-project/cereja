# Cereja UI v1 capability selection evidence

Status: the maintainer selected an initial five-area proposal for concrete flows:
System Information, explicit-path Tree, explicit-root Context Search,
Compress/Decompress, and Download. Ledger and files plus directories are now
selected. Detailed resource limits remain implementation calibration candidates;
the historical alternatives below record selection evidence, not open choices.
Inspected baseline: `ed7fbfa5bc08f3e5814602f1cb3f09e3d6ad5d87`.

## Discovery is broader than interactive execution

The catalogue should explain the existing Cereja ecosystem: purpose, public
API/CLI entry, parameters, input/output example and documentation. Mark entries
`Runnable here` or `API/CLI reference` explicitly. A non-runnable catalogue entry
does not claim an interactive adapter exists. Curate metadata from the static
CLI registry and public export registry without eagerly importing every module
or executing examples during discovery. Do not add a generic arbitrary-function
invoker or parse signatures into supposedly safe forms automatically.

Source indexes: [CLI registry](../../cereja/commands/registry.py) and
[public exports](../../cereja/_exports.py). The current CLI covers compress,
decompress, encrypt, decrypt, protect, tree, context, security, http, download,
system, privacy and module; public library capabilities are broader than CLI.
Their presence is discovery evidence, not automatic inclusion for execution.

## Selected initial proposal

| Area | Authorized interaction direction | Source gap to represent honestly |
| --- | --- | --- |
| System Information | Central utility: panels, sections/tables, refresh, responsive layout and host capabilities. | Typed data exists; synchronous collector may take seconds. No fake completion estimate or unsupported Cancel. |
| Repository/Directory Tree | User supplies a path; hierarchy, TreeView, selection/scroll, large-volume and Unicode/resize behavior. No full browser. | Existing renderer returns text; depth does not bound breadth. Structured bounded data adapter needs investigation. |
| Context Search | Explicit roots/query/filters, results/highlights, navigation and empty/error/success. | Returned-result limit is not a whole-scan work budget; no advertised cooperative cancellation. |
| Compress/Decompress | One functional area with source/destination, review/confirmation, real operation and outcome. | Existing APIs lack live progress/cancellation. V1 can run indeterminately with actual duration/results and no Cancel. |
| Download | URL/destination, validation, actual byte progress/speed when supported, network errors and controlled concurrency. No full HTTP client. | Chunk progress exists; cancel/no-clobber/total bounds require explicit proof and adapter design. |

Broader catalogue entries HTTP, encrypt/decrypt, protect, privacy, security,
module and registry are documentation/API/CLI references, not executable v1
integrations. `Available` is reserved for a functioning UI integration;
`CLI`/`Python API` identify real current surfaces, and `Planned UI` identifies
unbuilt/candidate integration. No implementation exists merely because selected.

See [operation contracts](cereja-ui-operation-contracts.md) for current API
evidence. All five remain subject to concrete flow review. Existing Color/Freq/
array suggestions below are historical alternatives, not the current proposal.

## Earlier comparison matrix (not the selected subset)

Each candidate below exists, offers a concrete interactive use, exercises toolkit
components and fits Cereja's utility-library purpose. Selection should balance
user utility with integration cost; the safest or smallest demo is not
automatically the best product.

| Candidate and actual entry | Real interactive value / toolkit evidence | Effects and integration cost | Recommendation |
| --- | --- | --- | --- |
| File compression and decompression: `cereja compress`/`decompress`; `cereja.hashtools.compress_file`, `decompress_file` | Complete a useful local file operation with visible strategy, destination, result size and recovery. Exercises parameter forms, action review, progress/activity, status and results. | Writes destination; API reads entire file and writes with `wb`, lacks overwrite/cancellation contract. Use explicit input/output review, safe publication, bounded file size and honest non-interruptible phase. No encryption or directory extraction in initial proposed slice. | Recommended real-operation anchor, conditional on the stated output-lifecycle acceptance. More product value than a synthetic compression demo alone. |
| Compression analysis: `analyze_data`, `suggest_strategy`, `compress` | Compare supported strategies on a bounded supplied sample; inspect ratio/time/size. Table, selection, text input and before/after feedback. | CPU/memory depend on payload/strategy. No per-call cancellation; cancel comparisons between calls. No file/network effects for memory API. | Companion to the file operation, not a substitute for it if real file execution is selected. |
| System: `cereja system info`; `cereja.system.hardware.info` -> `HardwareInfo` | Inspect actual environment/sections, unavailable data and refresh. Section list, key-value view, loading/errors/scroll. | Local inventory and platform subprocesses, potentially 10-second phases; no whole-call cancellation. Basic still describes machine. Sensitive identifiers off. Explicit collect/refresh, worker lifecycle, no automatic continuous dashboard polling. | Recommended real-service integration for the initial System direction, with bounded sections and truthful collection status. |
| Color conversions/contrast: `cereja.utils.colors.Color`; `cereja.wcag.validator.contrast_checker` | Convert actual values and compare colors while developing. Form validation, numeric results, table and redundant swatch preview. | Small pure input computation; range/format errors; swatch differs by terminal capability. Contrast result is library math, not proof the terminal is accessible. | Recommended complementary developer utility. Numeric/text output retains value with no color. |
| Frequency: `cereja.mltools.Freq`, `most_common`, `probability` | Inspect frequency/probability of an explicit token list. Sort/filter/table/selection/scroll. | Input/result privacy; bounded tokens/distinct values. Avoid `to_json` unless export is separately selected. Tokenization must be explicit. | Alternative to Color if data exploration is higher priority; do not add both solely to increase widget count. |
| Arrays: `cereja.array.flatten`, `get_shape`, `reshape` | Inspect a real transformation and understand shape errors. Input/result panes, controls, validation and scroll. | JSON-only input, no Python eval; bound bytes/nesting/elements/dimensions. Synchronous with no cancellation hook. | Alternative data tool; keep scope to named transforms, not an unrestricted notebook. |
| Base64: `cereja.hashtools.base64_encode`, `base64_decode` | Decode/encode supplied bytes with text/hex preview. Input mode and safe binary preview. | Keep `eval_str=False`; bound bytes; existing decoder may accept permissive input. No history of pasted secrets by default. | Discoverable; lower initial execution priority because interactive gain overlaps richer candidates. Not encryption. |
| Security: `cereja security analyze`; `cereja.security.analyze_file` -> `SecurityReport` | Inspect actual findings with details/severity and provenance. Tables, nested details, errors, loading. | Reads potentially large files, temporary extraction for archives, no cooperative cancellation. Must not claim a safe-file verdict. | Valuable later executable slice or replacement if maintainer prioritizes it; initial catalogue can explain it without running it. |
| HTTP: `cereja http`; `cereja.http.Client.request` | Compose a request and inspect real response/status/headers. Strong developer value; form/table/response panes. | Network/remote side effects, secrets, bounded response, phase rather than total timeout. Needs method review, masking, cancellation/worker shutdown, no automatic retry of mutations. | Explicit alternative real-operation anchor, with larger network/secret contract than local compression. Discovery does not issue requests. |

Sources: [compression](../../cereja/hashtools/_compress.py),
[Color](../../cereja/utils/colors/_color.py),
[contrast](../../cereja/wcag/validator/_color.py),
[Freq](../../cereja/mltools/data.py), [arrays](../../cereja/array/_array.py),
[Base64](../../cereja/hashtools/_hash.py),
[System command](../../cereja/commands/system.py),
[hardware collector](../../cereja/system/hardware/collector.py),
[security analysis](../../cereja/security/_analysis.py),
[HTTP client](../../cereja/http/sync/client.py).

## Superseded executor recommendation

Before the maintainer chose the five-area proposal, the executor proposed
**single-file compression/decompression + System snapshot + Color
conversions/contrast**, with compression analysis as the operation's inspection
companion. This covers a useful side-effecting operation, a real existing service
and a fast developer utility. Each offers a different interaction contract;
none depends on turning Cereja into a generic explorer or system manager.
Examples remain synthetic reference/dogfooding activities separate from tools.

Keep broader capabilities discoverable through API/CLI explanations. Propose
deferring directory archives, encryption/secrets, protected-code generation,
HTTP/download execution, security archive traversal, arbitrary file browsing,
unrestricted function invocation and persistent recent-history until selected
by a clear need. These are proposed v1 exclusions, not limitations imposed by
the toolkit or a claim that those Cereja capabilities are unsupported.

If the maintainer prefers data work, substitute Freq or array transforms for
Color. If network inspection is central, substitute HTTP for file compression
and accept its additional request/secrets/lifecycle work. Do not quietly replace
an accepted real-operation flow with a toy in-memory equivalent. That earlier
recommendation did not select product scope and is superseded by the selection
above; its exclusion of Tree/Search/Download no longer applies.

## Proposed file-operation flow and non-negotiable adapter evidence

1. Discover Compress/Decompress in Tools; inspect what it reads/writes and the
   existing API/CLI usage before selecting Run.
2. Enter a specific source and destination, strategy when applicable, and inspect
   estimated input size. A file picker is not required; no directory-browser
   product is implied. Reject source/destination identity.
3. Review the destination. Default refuses existing destination. A separately
   selected overwrite path must show the exact target and require explicit action;
   absence of `--force` or API defaults is not a sufficient race-safe guarantee.
4. Run with `verbose=False` so legacy Progress cannot write during the UI session.
   Stage output away from the final path, then publish only after success under
   a tested exclusive/no-overwrite or explicitly confirmed replacement contract.
   The current direct `wb` API cannot be called on a final destination safely
   merely because an earlier existence check passed.
5. Report phase-level activity and actual returned stats. Do not fabricate a
   percentage from an API with no incremental progress. The accepted v1 baseline
   is indeterminate Running plus actual final duration/outcome, without a Cancel
   button where safe cooperative interruption is unavailable. Process termination
   is not a substitute for a supported cooperative cancel contract.
6. On success show output location and stats; on error preserve the input and
   existing destination, remove only the owned temporary artifact, and offer
   edit/retry. Interrupted partial writes must never be labeled success.

These are proposed integration requirements if the capability is selected,
not a production implementation or authorization to modify arbitrary files now.
Decompression needs an output-size policy as well as input limits; compressed
size alone cannot bound expansion. A lack of a bounded existing decode API is
an adapter/integration gap to assess explicitly, not permission to ignore limits.

## User decision on long operations

Level 1: execute existing APIs with honest Running/indeterminate activity and
actual completion, error and elapsed duration. Expose no unsupported Cancel.
Level 2: investigate generic domain progress events/callbacks and cooperative
cancellation usable by CLI, UI and external consumers, without UI dependencies.
Level 3: if that adaptation is disproportionate, document evidence and retain
the honest baseline in v1, deferring detailed progress/cancellation. Apply this
to compression, download, search and every long operation. Determinate bars
require measured total and advance; speed/ETA require actual data. Spinner or
shimmer communicates known activity, not invented completion. Present evidence
and alternatives before changing selected scope because an API is inconvenient.

## Bounded existence smoke evidence

On Python 3.14.5 with `python -S`, directly imported the existing public APIs and
checked a 2,100-byte repeated-text memory compression/decompression round trip,
then a single-file round trip in an owned temporary directory, preserving its
source. Checked black/white `Color` contrast =21, `Freq(['a','b','a'])` counts
and a valid 2x2 reshape. All passed; no production code changed. Temporary paths
and contents were synthetic. This proves those bounded API calls work locally,
not UI integration, large/adversarial inputs, safe final publication, cancellation
or all-platform behavior. Inventory rows without this smoke remain source-read
existence evidence, not newly executed runtime checks.

## Local replay of bounded capability checks

Run the following with `python -S` from the checkout. This replay snippet and
raw experimental sources remain local; external code export was not approved.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from cereja.hashtools import compress, decompress, compress_file, decompress_file
from cereja.utils.colors import Color
from cereja.mltools import Freq
from cereja.array import reshape

payload = b'Cereja UI validation\n' * 100
encoded, stats = compress(payload, strategy='zlib')
assert decompress(encoded) == payload
with TemporaryDirectory(prefix='cereja-ui-capability-') as folder:
    root = Path(folder)
    src = root / 'sample.txt'
    src.write_bytes(payload)
    archive, file_stats = compress_file(
        str(src), str(root / 'sample.cjz'), strategy='zlib', verbose=False)
    output = decompress_file(archive, str(root / 'restored.txt'), verbose=False)
    assert Path(output).read_bytes() == payload
    assert src.read_bytes() == payload
print('compression memory and isolated file round trips: PASS; source preserved')
a, b = Color.parse('#000000'), Color.parse('#ffffff')
assert Color.contrast_ratio(a.luminance, b.luminance) == 21
print('Color parse and black/white contrast result21: PASS')
assert Freq(['a', 'b', 'a']).most_common() == {'a': 2, 'b': 1}
print('Freq explicit tokens: PASS')
assert reshape([1, 2, 3, 4], (2, 2)) == [[1, 2], [3, 4]]
print('reshape valid2x2: PASS')
```

Recorded stdout:

```text
compression memory and isolated file round trips: PASS; source preserved
Color parse and black/white contrast result21: PASS
Freq explicit tokens: PASS
reshape valid2x2: PASS
```
