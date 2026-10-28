# Find large files without reading content

Use the explicit submodule API or the `large-files` command. No Ledger
integration, persistent index, worker pool or runtime dependency is required.

```python
from cereja.system.file_sizes import find_large_files

report = find_large_files("path/to/data", min_size_bytes=1048576, max_results=20)
for file in report.files:
    print(file.size_bytes, repr(file.path))
print(report.complete, report.reasons, report.results_truncated)
```

```bash
cereja large-files path/to/data --min-size-bytes 1048576 --max-results 20
python -m cereja large-files path/to/data --format json
```

The root is required. Relative roots are made lexically absolute. Hidden files,
binary files, `.git`, caches, compiled files and `.gitignore` itself are eligible.
No file content is opened or read, including ignore files. Enumeration uses
`os.scandir`; sizes and kinds come from metadata with `follow_symlinks=False`.
Only regular files are ranked. Symbolic links, broken links, Windows reparse
points (including junctions), FIFOs, devices and sockets are excluded.
Roots with a linked/reparse component are rejected.

`size_bytes` is the observed logical size (`st_size`), not allocated disk usage.
Sparse/compressed files may occupy different physical space. Hard links count
once per path; there is no inode deduplication or directory-size aggregation.
Results sort by descending size and then case-sensitive relative path, with
`/` separators. API paths are literal data. The CLI uses ASCII JSON escaping for
paths in both text and JSON output, including operational error messages.

## Limits and report

`find_large_files(root, *, min_size_bytes=0, max_results=20,
max_entries=1000000, max_depth=64, max_errors=32)` returns a frozen
`FileSizeReport` containing frozen `FileSize` and `FileSizeError` records.
Integers must meet the documented minima; Boolean values are rejected.

| Argument | Meaning |
| --- | --- |
| `min_size_bytes` | Inclusive minimum logical size, at least zero. |
| `max_results` | Maximum retained file records, at least one. |
| `max_entries` | Maximum entries examined across the scan, at least one. Directories, links, special files and failing entries consume this budget too. |
| `max_depth` | Maximum directory descent below root, at least zero. Zero still examines root files but skips child directories. |
| `max_errors` | Maximum retained error details, at least zero. All errors are counted even after this cap. |

| Report field | Meaning |
| --- | --- |
| `root`, `files` | Absolute root and retained `(path, relative_path, size_bytes)` records. |
| `complete`, `reasons` | Whether traversal finished within the chosen scope without errors or skipped directories. Reasons are `max_entries`, `max_depth`, or `filesystem_error`. Excluded links/special files do not make a scan incomplete. |
| `results_truncated` | More qualifying regular files were observed than retained. This can be true for a complete scan. |
| `examined_entries` | Entries obtained from directory iterators, including metadata failures. |
| `scanned_files`, `matched_files` | Successfully identified regular files, and those meeting the threshold. |
| `skipped_links`, `skipped_special` | Excluded link/reparse entries and other non-regular entries. |
| `error_count`, `errors`, `errors_truncated` | Total failures, bounded `(path, operation, errno)` details, and whether details were omitted. |

A limit on retained results does not shorten traversal. A complete scan ranks
all eligible files observed within the root. An incomplete scan ranks only the
examined portion and cannot establish the largest files in the whole root.
Enumeration order is OS-dependent; partial rankings can differ across scans.
At an exact entry cap, the report conservatively remains incomplete because
it does not read an additional entry to determine EOF. Omitted counts are unknown.

Invalid/missing roots and failures while validating root components raise an
`OSError` subclass. Later metadata/enumeration failures preserve prior results,
increment the error count and make the report incomplete. Failure to enumerate
an otherwise valid root also produces an incomplete report. Invalid limits
raise `ValueError`.

CLI flags have the same names with hyphens. `--format text` is the default;
`--format json` serializes every report field. Exit codes are 0 for a complete
scan (even with truncated results), 1 for root validation failure, 2 for usage
errors and 3 for an incomplete scan, including enumeration errors. No matching
files is a valid complete result.

## Resource and filesystem boundary

The scanner maintains a bounded top-k heap rather than retaining the entire
inventory. It retains at most `max_results` candidates, `max_errors` error
details and one directory iterator per active level (at most `max_depth + 1`).
All iterators close on normal completion, limits, errors and interruption.
Storage also includes path strings and the active directory stack. These
logical bounds do not establish a process RSS limit. Metadata traversal is
linear in entries, with heap work up to `O(N log K)` and an additional
`O(K log K)` final sort. Ancestor revalidation adds metadata work per descent.

Directory components are checked again before descent. Use owned, trusted
trees: separate metadata checks and enumeration cannot prevent hostile
concurrent ancestor replacement between OS calls. Ordinary links/reparse
points are excluded, but there is no race-proof containment guarantee.
Metadata may change during or after a scan; the result is not an atomic
filesystem snapshot. OS calls can block, including on network filesystems.
Entry/depth limits provide no wall-clock deadline or cancellation guarantee.

## Reproduce tests and measurements

```bash
python -B -m unittest tests.test_file_sizes tests.test_command_registry -v
```

Benchmark tooling, raw samples and harness tests under `benchmarks/` are local
only: they are ignored by Git and excluded from distributions. With those
local files present, run:

```bash
python -B -m unittest discover -s benchmarks/local_tests -v
python -m benchmarks.file_sizes --counts 1000 10000 --samples 7 --warmups 2 --output new-file-sizes.json
```

The benchmark creates and removes only its own temporary fixtures. Use
`--temp-parent PATH` if the host's default temporary directory is unavailable.
`--output` requires a new file and never replaces an existing result.

Fixtures contain deterministic logical sizes and names in flat directories and
four-level nested layouts, including hidden files and normally ignored paths.
The harness checks the exact expected ranking and scan completeness for every
sample. Fixture construction and validation are outside the timing window.
Timing and `tracemalloc` peak-allocation samples use separate scans; raw samples,
median, nearest-rank p95, MAD, environment and source SHA-256 hashes are emitted.

Two retention settings use the same scanner: top 20 and all files. This measures
the cost of retaining the complete inventory; it is not a comparison against
an optimized sort-all algorithm. OS caches, load and antivirus are uncontrolled.
Traced Python allocations are not RSS, disk buffers or physical disk usage.
Results do not establish cold-disk speed, network performance, TUI latency or
cross-platform performance. The local samples are
`benchmarks/file_size_samples/windows-py314.json`, `windows-py311.json`
and `linux-py311.json`; they are not included in a fresh checkout.

The local Windows/Python 3.14.5 sample uses seven measurements after two
warmups for each retention setting. Top-20 measurements:

| Layout | Files | Median ms | p95 ms | Median traced peak KiB |
| --- | ---: | ---: | ---: | ---: |
| Flat | 1,000 | 2.891 | 2.994 | 15.5 |
| Flat | 10,000 | 23.916 | 24.742 | 15.6 |
| Nested | 1,000 | 48.526 | 50.780 | 28.7 |
| Nested | 10,000 | 83.899 | 137.612 | 28.8 |

For the same 10,000-file fixtures, retaining all results instead used median
traced peaks of 4,555.9 KiB (flat) and 5,232.4 KiB (nested). These observations
support bounded candidate retention under these conditions; they do not
establish a general speed advantage or an RSS bound.

## Executed Python 3.11 validation

The focused behavior and compatibility suite passed on both platforms on
2026-10-23:

| Environment | Tests run | Skipped | Outcome |
| --- | ---: | ---: | --- |
| Windows, CPython 3.11.15 | 129 | 7 | Passed |
| Linux x86_64, CPython 3.11.16 | 129 | 1 | Passed |

The Linux run exercised real symbolic links, a FIFO and literal control
characters in filenames. Its only skip was the Windows junction test. The
Windows run retains platform/privilege skips; it does not establish native
POSIX behavior. No product-code correction was necessary for these runs.

Reproduce the suite with a Python 3.11 interpreter:

```bash
python -B -S -m unittest tests.test_file_sizes tests.test_command_registry tests.test_cli tests.test_import_contract tests.test_public_exports tests.test_lazy_imports tests.test_lazy_resolver tests.test_export_stubs tests.test_repository_files tests.test_repository_tree tests.test_repository_traversal -q
```

Linux validation used the locally available `python:3.11-slim` image with
network disabled and the host checkout mounted read-only. Legacy CLI tests
create fixtures beside the source, so the passing run used a disposable copy
of `cereja/`, `tests/`, the benchmark and the export-stub checker on the
container's writable `/tmp` filesystem. An initial attempt against the
read-only source failed in 22 legacy fixture setups; no test was changed.

The additional Linux benchmark used `/tmp` on tmpfs for its fixtures. Its
timings are not measurements of physical disk I/O and should not be compared
directly with the Windows filesystem samples. Each benchmark independently
checks the exact fixture ranking on every sample.

The local receipt `benchmarks/file_size_samples/validation.json`
records runtime/image identity, commands, results and source hashes for both
the focused checks and the subsequent full-suite runs.

### Full unittest discovery (2026-10-28)

The full repository discovery command completed successfully on both Python
3.11 environments, without product-code or test changes:

| Environment | Tests run | Passed | Skipped | Failures/errors |
| --- | ---: | ---: | ---: | ---: |
| Windows, CPython 3.11.15 | 1,420 | 1,390 | 30 | 0 |
| Linux x86_64, CPython 3.11.16 | 1,420 | 1,365 | 55 | 0 |

```bash
python -B -m unittest discover -s tests -v
```

The passing Windows run used the native Windows temporary directory. An earlier
workspace-temporary run encountered `WinError 5` in `protect_path` while renaming
a staged package. The isolated test and full suite passed with the native
temporary directory. The exact cause of the workspace-specific failure remains
unconfirmed; this is not presented as a product fix. A separate earlier Windows
execution was interrupted without a final result and is not counted as passing.

The passing Linux run used UID/GID 1000 and a writable disposable copy of
`cereja/`, `tests/`, `benchmarks/`, `tools/`, `docs/`, `.github/` and required root
files. The original host checkout remained read-only and networking stayed off.
The initial full run as root had one cache-journal test failure: root could write
through the reserved file's read-only mode. The unchanged test passed as UID 1000,
followed by the full suite. No assertion was removed or skipped to obtain a pass.

Platform/capability skips and unsuccessful attempts remain in the receipt.
These local results do not establish the other Python versions in the CI
matrix, remote CI, distribution builds or human acceptance. Ledger was not
changed, and no push, release or publication was performed.

The 1,420-case run above predates moving benchmark-only checks into the ignored
local directory. Functional tests remain under `tests/`; harness/example checks
now run separately from `benchmarks/local_tests/` and are not required by CI.
After that move, full functional discovery passed with 1,400 cases on Windows
and Linux/Python 3.11 (30 and 55 platform/capability skips respectively). All
20 local benchmark-harness/example checks passed separately on Windows.
Linux functional validation used a source copy with no `benchmarks/` directory.
Wheel and sdist validation also passed with local benchmark files present in
the build input and absent from both generated artifacts.
