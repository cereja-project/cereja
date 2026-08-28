# Cereja IO 2.0 Read-Only MVP — Independent Architecture Review

## Review scope

This review challenges the proposed IO 2.0 design from four independent perspectives: correctness/security, performance, API design, and extensibility/maintenance. It compares the design against Python stdlib behavior, OWASP file-handling guidance, Apache Tika's detector architecture, IANA media-type semantics, and libmagic's content-signature model.

The review does not authorize implementation. It identifies changes that should be incorporated into the design before an implementation plan is written.

## Overall verdict

The architecture direction is sound: a neutral `cereja.io` core, a small public `scan()` service, content-based detection, typed facets, and legacy `FileIO` as a future adapter are all worth keeping.

The current spec is not yet implementation-ready. Several issues can create correctness bugs, avoidable I/O cost, or misleading results on adversarial files. The recommended changes below tighten the design without increasing the public surface materially.

## 1. Keep one stable opened source during a scan

### Problem

A path-backed `Resource` that is repeatedly reopened by detectors, hashers, and inspectors creates a time-of-check/time-of-use problem. The file may be replaced or modified between detection and metadata collection, producing a result assembled from different byte sequences.

### Decision

Separate an immutable source descriptor from an opened scan handle:

- `Resource` describes how to obtain the source.
- `ResourceHandle` (private/internal in the MVP) owns one opened binary stream/file descriptor for the lifetime of a scan.
- source metadata for a path-backed resource should be derived from the opened descriptor where portable (`os.fstat`) rather than repeatedly from the path.
- record pre/post size and `mtime_ns` where available and add a neutral issue if the source changed while being scanned.

This is a correctness boundary, not security policy.

## 2. Reader API must be position-independent

### Problem

A public/internal `read(offset=..., size=...)` implemented over one mutable seek cursor can make detectors interfere with each other and complicates future concurrency.

### Decision

The core reader contract should be logically position-independent:

```python
reader.read_at(offset: int, size: int) -> bytes
reader.read_head(size: int) -> bytes
reader.read_tail(size: int) -> bytes
reader.iter_chunks(...)
```

The implementation may use `seek` + read synchronously, or platform-specific primitives internally, but callers must not depend on shared cursor state.

Do not expose a generic unbounded `read(size=None)` in the scan path.

## 3. Add a scan-wide read/work budget

### Problem

A per-read `max_bytes` is insufficient for hostile structures. A detector can perform thousands of individually bounded reads and still cause I/O or CPU denial of service.

### Decision

`ScanPolicy` must define a scan-wide budget, enforced by a private `ScanBudget`/context:

- maximum probe bytes cumulatively read by detectors;
- maximum read operations/seeks;
- maximum structural entries visited (for example archive members/import descriptors);
- maximum evidence bytes retained;
- optional permission for a full sequential pass.

Budget exhaustion should create a typed issue/partial result where possible rather than crash the entire scan.

## 4. Do not perform full-file hashing or entropy by default

### Problem

The current draft enables SHA-256 by default. On a 100 GB resource this makes a supposedly quick metadata scan necessarily read 100 GB even if detection needs only kilobytes.

### Decision

The default `scan()` should be cheap and bounded:

- no full-file hash by default;
- no full-file entropy by default;
- content detection and cheap facets only.

Whole-stream metrics are explicit policy choices. `cereja.security` or forensic workflows can request SHA-256, Git blob SHA-1, entropy, etc.

When multiple full-stream metrics are enabled, compute them in one sequential pass over the resource rather than one pass per metric.

## 5. Add a single-pass metric collector

### Problem

Independent implementations of SHA-256, SHA-1, Git blob SHA-1, MD5 and entropy can cause repeated full scans.

### Decision

Use one internal stream traversal with a set of incremental collectors. A chunk should update all requested hashes and byte-frequency counters before being discarded.

`hashlib.file_digest()` is useful for a single digest, but the multi-metric case should use one shared chunk loop because `file_digest()` may leave the file object in an unknown position and would otherwise require separate passes.

## 6. Detection must preserve ambiguity and polyglot evidence

### Problem

Selecting exactly one highest-confidence candidate discards useful facts. Some resources are valid under more than one format interpretation; executable/archive and PDF/ZIP polyglots are real examples. Security and archive consumers should not lose that information.

### Decision

Keep a primary detection for ergonomics but preserve bounded alternatives:

```python
DetectionResult(
    primary=FormatMatch(...),
    alternatives=(FormatMatch(...), ...),
)
```

or equivalent fields that preserve the existing simple accessors:

```python
result.detection.kind
result.detection.format
result.detection.alternatives
```

The registry should collect credible candidates before deterministic ranking.

## 7. Confidence is not a probability

### Problem

A floating-point `confidence=0.97` implies calibration that heterogeneous signature/structure detectors cannot substantiate. Comparing a PNG signature detector's `0.99` with a text heuristic's `0.91` is arbitrary unless formally calibrated.

### Decision

Use an ordinal evidence strength in the MVP, for example:

```text
weak | probable | strong | verified
```

or an enum with equivalent semantics.

`verified` means the detector completed the structural checks it defines; it does not mean the entire file is safe or semantically valid.

A numerical score can be added later only if detectors have a documented common scoring model.

## 8. Separate format detection from filename consistency

### Problem

`extension_matches` mixes a content detector's output with filename metadata. Detection should remain a statement about bytes; extension agreement is a derived relationship between two independent facts.

### Decision

Keep the declared extension in core/source metadata and expose consistency as a derived property or separate neutral `FormatConsistency` object on `ScanResult`.

The extension must never influence content-evidence strength.

## 9. Treat archive, container and compressed stream as different concepts

### Problem

ZIP, TAR and GZIP are not equivalent abstractions. ZIP/TAR can expose members; GZIP normally represents a compressed byte stream around one payload. Future compression support will become awkward if all are labeled simply `archive`.

### Decision

Detection taxonomy should distinguish at least:

- `archive` / container with members (ZIP, TAR);
- `compressed_stream` (GZIP, BZIP2, XZ, ZSTD when supported);
- formats that are both domain containers and archives can expose multiple facets later.

`ArchiveMetadata` remains a member-oriented facet. A future `CompressionMetadata` facet handles compressed streams.

## 10. ZIP must be preflighted before `zipfile.ZipFile` builds large metadata lists

### Problem

`zipfile` is appropriate for standard-library ZIP parsing, but hostile archives can contain extreme central-directory metadata. Limits checked only after creating an unrestricted `ZipFile`/`infolist()` are too late for a strict untrusted-input boundary.

### Decision

Before full ZIP inspection, perform a small tail/EOCD preflight sufficient to bound:

- declared entry count;
- central-directory size;
- central-directory offset relative to resource size.

Reject or return a limited partial facet when configured limits are exceeded. Only then instantiate the standard-library ZIP parser.

The MVP still must not extract members.

## 11. Use portable filesystem timestamp semantics

### Problem

A universal `created_at` is misleading. Unix `ctime` is metadata-change time, not creation time; birth time availability differs by platform.

### Decision

Use neutral fields:

```text
modified_at
accessed_at
metadata_changed_at  # when platform meaning is available
birth_time           # optional, only when the platform exposes a real birth time
```

Do not synthesize `created_at` from `ctime`.

## 12. Accept `os.PathLike`, not only `pathlib.Path`

### Decision

Path-backed resources should accept the standard filesystem path protocol (`str | os.PathLike[str]`) and normalize internally. This follows PEP 519 and avoids unnecessary coupling to one path implementation.

## 13. Keep `mmap` out of the default architecture

Memory mapping can help particular workloads but has platform-specific behavior and does not remove the need for bounds. The buffered binary I/O API is already portable and thread-safe at its internal state level.

Decision: do not make `mmap` a core assumption or public feature in the MVP. It may be introduced internally after benchmarks demonstrate a material win for a specific inspector.

## 14. Facets remain the right model, but inspectors must not depend only on the primary kind

A resource can validly produce multiple structural facts. Keep typed facets.

However, an inspector's applicability should be based on the scan context/candidate evidence, not only `primary_detection`, otherwise secondary structures in polyglot/container resources can never produce facets.

For the MVP, inspectors may declare the format IDs/candidate conditions they consume.

## 15. Canonical internal format IDs must be independent of MIME strings

IANA media types are valuable interoperability metadata, but not every format has a canonical registered media type and aliases evolve.

Decision:

- internal stable ID: e.g. `pe`, `zip`, `png`, `gzip`;
- canonical media type where known and registered;
- aliases/extensions maintained as declarative metadata outside detector logic.

Do not use MIME strings as registry primary keys.

## 16. PE facet scope should be reduced for the first implementation

A robust zero-dependency import-table parser and imphash implementation is useful but materially larger and more error-prone than PE identification and basic headers.

Recommended MVP PE facet:

```text
format
architecture
bits
entry_point
compile_timestamp
subsystem
signed
```

Imports/imphash should be a second PE-inspection increment unless existing reviewed code is migrated with dedicated malformed-PE tests. This keeps the initial IO 2.0 milestone focused.

## 17. Result serialization needs an explicit schema version and stable machine IDs

`to_dict()` must not accidentally expose Python implementation details as a long-term data contract.

Decision:

- top-level `schema_version`;
- stable `format_id`, detector IDs, inspector IDs, issue codes and facet type IDs;
- JSON-friendly deterministic representation;
- bytes in evidence encoded explicitly or rendered as bounded hex, never emitted as arbitrary Python repr.

## 18. Scanner must detect source mutation

For path resources, compare stable metadata associated with the opened handle before/after complete passes. If size/mtime changes during scanning, include a neutral issue such as:

```text
resource.changed_during_scan
```

Consumers that require forensic consistency can reject such a result. Normal metadata consumers can still use the partial facts.

## 19. Public API should remain smaller than the internal architecture

Recommended MVP public surface:

```python
from cereja.io import (
    Resource,
    ScanPolicy,
    ScanResult,
    scan,
    TextMetadata,
    ArchiveMetadata,
    ExecutableMetadata,
)
```

`Reader`, registry implementation, budgets, candidates, contexts and built-in detectors/inspectors should remain private initially. Promote them only when a real external extension use case exists.

This significantly reduces backward-compatibility obligations while the architecture matures.

## 20. Revised execution model

```text
source
  ↓
Resource descriptor
  ↓
open once → ResourceHandle
  ↓
position-independent bounded Reader
  ↓
ScanBudget + small probe cache
  ↓
content detectors collect candidate matches
  ↓
rank primary + preserve alternatives
  ↓
format inspectors produce typed facets
  ↓
optional one-pass whole-stream metric collectors
  ↓
source-stability check
  ↓
ScanResult (core + detection + facets + issues)
```

## Recommended MVP defaults

The default scan should prioritize latency and bounded work:

```text
full hashes: disabled
full entropy: disabled
recursive archive scanning: disabled
archive extraction: impossible
max probe budget: bounded
ZIP metadata/member count: bounded
result evidence: bounded
```

A forensic/security caller explicitly enables expensive whole-stream metrics.

## References used by this review

- Python `io` documentation: buffered binary I/O is the preferred high-level binary interface; text I/O has additional conversion costs; buffered binary objects protect internal state with locks.
- Python `hashlib.file_digest`: efficient single-file digesting can bypass Python I/O and leaves stream position unspecified afterward.
- Python `zipfile`: documents resource-exhaustion/decompression-bomb risks and filename/path concerns.
- Python `tarfile` extraction filters / PEP 706 guidance: extraction filters do not eliminate DoS risk; member count, total size, filename and link restrictions remain necessary for untrusted input.
- `os.fstat`: supports metadata from an already-open file descriptor.
- PEP 519: standard `os.PathLike` filesystem path protocol.
- Apache Tika Detector: separates input-stream content detection from metadata hints and composes detector implementations.
- libmagic: identifies files through tests at defined byte offsets rather than filename extension alone.
- IANA Media Type registry: media types, magic numbers and file extensions are distinct registration metadata.
- OWASP File Upload Cheat Sheet / ASVS: extension, content type and signatures are each insufficient alone; content validation and resource limits should be defense in depth.

## Review conclusion

Keep the overall three-layer architecture and typed-facet model. Before implementation, revise the main spec with the decisions in this review, especially stable-open scan identity, scan-wide budgets, cheap default scans, single-pass expensive metrics, ambiguous/polyglot detections, ZIP preflight, ordinal evidence strength, and a smaller public API.
