# Cereja IO 2.0 Read-Only MVP Design

## Status

Proposed design for the first `cereja.io` milestone. This document defines the architecture and public contracts; it does not authorize implementation changes to the legacy `cereja.file.FileIO` API.

## Motivation

The current `cereja.file.FileIO` API selects specialized readers primarily from a file extension. That is convenient for trusted application data, but it is not a reliable foundation for archive handling, security inspection, metadata extraction, or untrusted files. An extension is a declaration made by a filename, not proof of the underlying format.

`cereja.io` will be a new low-level read-only I/O core that identifies and describes resources from observable content. It must be reusable by future archive/compression services, `cereja.security`, metadata tools, and eventually a compatibility adapter beneath the existing `FileIO` API.

The first milestone is intentionally read-only. Write/mutation APIs, broad format coverage, remote resources, and transparent migration of `FileIO` are out of scope until the read path and inspection contracts are stable.

## Design goals

The MVP MUST:

- live under the public namespace `cereja.io`;
- have zero mandatory third-party dependencies;
- be safe for untrusted input and never execute, import, evaluate, deserialize with unsafe mechanisms, or shell out to inspected content;
- never treat a filename extension as authoritative evidence of format;
- support local filesystem files and in-memory `bytes` as first-class sources;
- use bounded reads and streaming operations where full materialization is not required;
- support large files without implicitly reading the complete resource into memory;
- produce deterministic, typed, serializable inspection results;
- distinguish universal metadata, format detection, and format-specific metadata;
- support multiple format-specific facets for one resource;
- expose explicit confidence and evidence for detection decisions;
- permit new detectors and inspectors to be added without modifying a central `if/elif` dispatch tree;
- keep security judgments outside `cereja.io`;
- preserve the existing `cereja.file.FileIO` API during this milestone;
- follow PEP 8, type annotations, focused modules, typed runtime errors, and documented public APIs.

## Non-goals

The MVP WILL NOT:

- replace or deprecate `cereja.file.FileIO`;
- write or mutate resources;
- extract archives to disk;
- execute archive members;
- recursively scan archive members by default;
- perform malware classification or assign a risk score;
- implement `scan_many()` concurrency yet;
- support HTTP, cloud storage, sockets, arbitrary URLs, or generic file-like streams as public sources;
- support every media/document/archive format;
- depend on `libmagic`, FFmpeg, Pillow, pefile, python-magic, or external executables;
- claim that a file is valid merely because a signature matches.

## Architectural layers

The long-term architecture has three layers.

### Layer 1: `cereja.io` core

The core owns safe resource access and neutral structural facts:

- resource abstraction;
- bounded readers;
- hashing and basic byte-level metrics;
- detection;
- detector/inspector registry;
- typed metadata models;
- format-specific inspectors.

Core primitives MUST remain synchronous, small, deterministic, and side-effect-free except for reading the source.

### Layer 2: `cereja.io` services

Services compose core primitives into useful public operations. The MVP service is `scan()`.

Later services may include:

- `scan_many()`;
- safe archive traversal;
- archive extraction;
- transformations;
- copy/move/write operations.

Concurrency and parallelism belong primarily in this layer. A future `scan_many()` may use threads for I/O-bound work and explicitly selected process workers for CPU-heavy inspectors. Low-level `Reader.read()` and detector methods MUST NOT implicitly create worker pools.

### Layer 3: compatibility/domain adapters

The existing `cereja.file.FileIO` remains the historical high-level API. During this milestone it is unchanged.

After `cereja.io` stabilizes, `FileIO` may progressively delegate source reading, detection, and metadata gathering to `cereja.io` while preserving its public behavior. The new core MUST NOT depend on `cereja.file`.

`cereja.security` is not a layer beneath `cereja.io`. It is a lateral consumer of neutral scan facts. For example:

- `cereja.io`: "content is PE, declared extension is `.jpg`, extension does not match";
- `cereja.security`: "a PE presented as `.jpg` is a suspicious mismatch".

## Proposed package structure

```text
cereja/io/
├── __init__.py
├── _errors.py
├── _models.py
├── _resource.py
├── _reader.py
├── _registry.py
├── _scan.py
├── _metrics.py
├── detection/
│   ├── __init__.py
│   ├── _base.py
│   ├── _binary.py
│   ├── _text.py
│   ├── _archive.py
│   └── _executable.py
└── inspectors/
    ├── __init__.py
    ├── _text.py
    ├── _archive.py
    └── _executable.py
```

The exact private filenames may change during implementation if a simpler decomposition is demonstrated, but public boundaries in this specification must remain intact.

## Resource model

A resource is the source of bytes being inspected. It is not a parsed file object and does not infer format.

The MVP supports:

```python
Resource.from_path(path)
Resource.from_bytes(data, name=None)
```

`Resource` exposes immutable source facts where available:

```python
resource.name
resource.size
resource.declared_extension
resource.source_kind   # "path" | "bytes"
```

For path-backed resources, filesystem timestamps and absolute/resolved path information may be recorded in core metadata. Bytes-backed resources have no filesystem timestamps and MUST represent those fields as `None` rather than inventing values.

A bytes resource MAY receive a descriptive `name`. Its suffix is still only declared metadata and must not influence detection as authoritative evidence.

### Resource invariants

- Construction from a missing path raises `ResourceNotFoundError`.
- Directories are not accepted by `scan()` in this MVP. Passing a directory raises `UnsupportedResourceError`.
- Symlinks are followed using normal platform file-open semantics, but metadata MUST expose whether the original path was a symlink when this can be determined portably.
- Resource construction MUST NOT read the complete file.
- `Resource.from_bytes()` MUST not copy immutable `bytes` unnecessarily.

## Reader model

`Reader` provides bounded random/sequential access over a `Resource`.

Minimum internal interface:

```python
reader.size
reader.read(offset=0, size=None, *, max_bytes=None) -> bytes
reader.iter_chunks(chunk_size=..., *, start=0, stop=None)
```

The reader MUST enforce configured limits before allocation. Detection and inspectors consume a `Reader`; they MUST NOT call `Path.read_bytes()` or equivalent full-read helpers.

A path-backed reader opens files in binary mode only. Text decoding belongs to text inspection.

`size=None` means "to the end" only when an explicit maximum or policy allows the operation. Public scanning MUST never make an unbounded full-file read through this path.

## Scan API

Primary public API:

```python
from cereja.io import scan

result = scan(source)
```

Accepted MVP source forms:

```python
scan("sample.bin")
scan(pathlib.Path("sample.bin"))
scan(b"raw bytes")
```

Optional configuration is represented by a typed immutable policy rather than an expanding list of unrelated keyword arguments:

```python
from cereja.io import ScanPolicy, scan

result = scan(
    source,
    policy=ScanPolicy(
        hash_algorithms=("sha256",),
        entropy=True,
        max_probe_bytes=64 * 1024,
    ),
)
```

The initial public `ScanPolicy` SHOULD include only fields required by the MVP. Future fields must be backward-compatible additions.

## Scan result model

A scan result has three conceptual areas:

```text
ScanResult
├── core       universal facts
├── detection  probable identity and its evidence
└── facets     format-specific facts that were independently inspected
```

### `CoreMetadata`

Universal or source-level facts:

```python
@dataclass(frozen=True)
class CoreMetadata:
    name: str | None
    source_kind: str
    size: int
    declared_extension: str | None
    created_at: datetime | None
    modified_at: datetime | None
    accessed_at: datetime | None
    hashes: Hashes
    entropy: float | None
```

`Hashes` contains only algorithms requested/enabled by policy. SHA-256 is enabled by default. MD5/SHA-1/Git blob SHA-1 are useful for compatibility and forensic workflows but SHOULD be opt-in if benchmarking shows material cost for the common case.

Hashing MUST be incremental over chunks and MUST not materialize the resource.

Entropy, when enabled, MUST be calculated incrementally over byte counts. It may scan the complete stream but without retaining it.

### `DetectionResult`

Detection is evidence-based and distinct from filename metadata:

```python
@dataclass(frozen=True)
class DetectionResult:
    kind: str
    format: str
    media_type: str | None
    confidence: float
    extension_matches: bool | None
    evidence: tuple[DetectionEvidence, ...]
```

Examples:

```text
kind="image",      format="png"
kind="archive",    format="zip"
kind="executable", format="pe"
kind="text",       format="text"
kind="unknown",    format="unknown"
```

`kind` is the primary broad classification for UX/filtering. `format` is the specific detected representation. A resource may expose additional structural characteristics through facets.

`extension_matches` is:

- `True` when the declared suffix is recognized as compatible with the detected format;
- `False` when it is recognized and incompatible;
- `None` when no suffix exists or compatibility is unknown.

The extension MUST NOT increase a content detector's confidence. At most it may be reported as corroborating metadata separately.

### Detection evidence

Detections MUST be explainable:

```python
@dataclass(frozen=True)
class DetectionEvidence:
    detector: str
    description: str
    offset: int | None = None
    matched_bytes: bytes | None = None
```

Evidence returned publicly MUST be bounded in size. Detectors must never include large arbitrary file contents in a result.

## Facets

Facets are typed, format-specific metadata objects. `ScanResult` may contain zero, one, or multiple facets.

The MVP implements only facets with immediate consumers:

### `TextMetadata`

Candidate fields:

```python
@dataclass(frozen=True)
class TextMetadata:
    encoding: str | None
    encoding_confidence: float
    line_count: int | None
    newline: str | None
    printable_ratio: float
```

The stdlib-only MVP MUST be conservative about encoding. It may confidently recognize ASCII, UTF-8 (including BOM variants), UTF-16 BOM, and binary/non-text characteristics. It MUST NOT pretend to reliably identify arbitrary legacy encodings.

`line_count` may require complete streaming traversal and therefore is policy-controlled or calculated only when the text inspector already performs a complete pass.

### `ArchiveMetadata`

MVP archive inspection covers ZIP because Python provides safe metadata access in the standard library.

```python
@dataclass(frozen=True)
class ArchiveMetadata:
    format: str
    member_count: int
    compressed_size: int | None
    uncompressed_size: int | None
    encrypted: bool | None
    compression_methods: tuple[str, ...]
```

The MVP inspects the archive directory/headers only. It MUST NOT call `extractall`, write members to disk, or recursively scan member contents.

ZIP inspection MUST enforce metadata-level safety limits, including a maximum member count and bounded member-name/evidence handling. Suspicious compression ratios may be exposed as neutral metadata later; they are not a security verdict in `cereja.io`.

TAR/GZIP support may be added in a follow-up archive milestone using the same facet contract. It is not required for the first implementation unless doing so requires negligible incremental complexity and the implementation plan explicitly justifies it.

### `ExecutableMetadata`

MVP executable inspection covers PE using a zero-dependency parser sufficient for reliable structural metadata.

Candidate fields:

```python
@dataclass(frozen=True)
class ExecutableMetadata:
    format: str
    architecture: str | None
    bits: int | None
    entry_point: int | None
    compile_timestamp: datetime | None
    subsystem: str | None
    signed: bool | None
    import_libraries: tuple[str, ...]
    import_count: int | None
    imphash: str | None
```

The parser MUST validate offsets and sizes before reading structures. Malformed PE data produces partial metadata plus an inspection issue or a typed non-fatal inspector failure; it MUST NOT cause arbitrary reads or unbounded allocation.

ELF may have content detection in the MVP, but an ELF-specific executable facet is optional unless the implementation remains small and well-tested.

## Facet access

Internally facets are strongly typed, not `dict[str, Any]`.

Public convenience API:

```python
text = result.facet(TextMetadata)
archive = result.facet(ArchiveMetadata)
```

`facet(Type)` returns the single facet compatible with that type or `None`.

`result.facets` is an immutable tuple.

A future format may yield multiple facets. Examples:

- DOCX: `DocumentMetadata` + `ArchiveMetadata`;
- SVG: `ImageMetadata` + `TextMetadata`;
- APK: `PackageMetadata` + `ArchiveMetadata`.

The MVP does not implement these types; the examples define why the result model must not rely on a single subclass hierarchy.

## Detector and inspector registry

Extensibility uses explicit protocols and a registry.

Conceptually:

```python
class Detector(Protocol):
    name: str
    priority: int

    def probe(self, reader: Reader, context: DetectionContext) -> DetectionCandidate | None:
        ...


class Inspector(Protocol):
    name: str

    def supports(self, detection: DetectionResult) -> bool:
        ...

    def inspect(self, reader: Reader, context: InspectionContext) -> Facet | None:
        ...
```

The default registry is populated by built-in detectors/inspectors. Ordering is deterministic by priority and registration order.

### Registry requirements

- Adding a new built-in format MUST NOT require editing the scan orchestration logic.
- Registry mutation MUST NOT happen implicitly during arbitrary module import.
- Public global mutation is NOT part of the MVP API.
- Tests and future advanced integrations need a way to construct an isolated registry and pass it to the scan service internally or through an explicitly advanced API.
- Registry lookup and iteration must be thread-safe for concurrent reads so that future `scan_many()` can share a frozen registry.

The implementation SHOULD favor an immutable/frozen registry used by default scanning.

## Detection pipeline

The default flow is:

```text
source
  ↓
Resource
  ↓
Reader
  ↓
cheap signature probes
  ↓
structural validation where necessary
  ↓
rank DetectionCandidate values
  ↓
DetectionResult
  ↓
compatible inspectors
  ↓
facets
  ↓
ScanResult
```

Detection MUST use the cheapest reliable evidence first.

Examples:

- PNG: fixed signature followed by minimal IHDR validation;
- ZIP: local/EOCD ZIP signatures plus `zipfile` structural open when needed;
- PE: `MZ`, validated `e_lfanew`, and `PE\0\0` signature;
- PDF: `%PDF-` signature;
- text: byte-level null/printable/decodability heuristics only after stronger binary signatures fail.

A magic prefix alone SHOULD NOT receive confidence `1.0` when a cheap structural validation is available.

Multiple detectors may return candidates. The orchestration chooses the highest-confidence candidate deterministically. Ties are resolved by detector priority and registration order.

## Initial format coverage

The first implementation SHOULD detect at least:

- unknown/binary;
- generic text / UTF text;
- ZIP;
- PE;
- ELF;
- PDF;
- PNG;
- JPEG;
- GIF;
- GZIP.

This is detection coverage, not full specialized facet coverage.

Required MVP facets remain:

- text;
- ZIP archive;
- PE executable.

Format support is considered implemented only when accompanied by signature/structure tests, truncated-input tests, and extension-mismatch tests.

## Errors and partial results

`cereja.io` uses typed exceptions for source-level failures:

```text
IOErrorBase
├── ResourceNotFoundError
├── UnsupportedResourceError
├── ResourceReadError
├── ScanLimitError
└── RegistryError
```

A malformed or truncated format SHOULD usually not abort the whole scan after the resource itself was opened successfully. Detector/inspector problems are represented as bounded neutral issues in the result:

```python
@dataclass(frozen=True)
class InspectionIssue:
    component: str
    code: str
    message: str
```

`ScanResult.issues` is immutable.

This permits a result such as "probable PE, malformed import table" while still returning hashes and core metadata.

No raw traceback or arbitrary exception string from untrusted data becomes part of serialized output without normalization.

## Performance model

Performance requirements are architectural, not micro-optimization promises.

### Bounded probing

Default detection SHOULD require no more than 64 KiB of aggregate front-loaded probe data for common formats, with targeted additional range reads when a format contains an offset to a required header (for example PE `e_lfanew`).

The scanner MUST NOT read a multi-gigabyte file in full merely to determine its type.

### Single-pass full-stream metrics

When hashes and entropy are requested, they SHOULD be computed in one chunked pass where practical.

Default chunk size is an implementation detail and should be benchmarked; it must not be exposed as a public compatibility contract unless needed.

### Reuse of reads

`Reader` MAY maintain a small bounded probe cache so multiple detectors do not re-read identical ranges. Cache size MUST be policy-bounded.

### Concurrency readiness

All result models are immutable. Built-in detectors and inspectors MUST not use mutable global per-scan state. A frozen default registry must support concurrent read access. These constraints make a later `scan_many()` service possible without redesigning the core.

## Safety invariants

The following are non-negotiable:

1. No inspected file is executed.
2. No Python source from an inspected file is imported.
3. No pickle or other unsafe object deserialization is used for inspection.
4. No shell command or external process is invoked by core detection/inspection.
5. Archive inspection does not extract members in the MVP.
6. Every binary offset derived from input is range-validated before access.
7. Every input-controlled count/length used for loops or allocation is bounded by policy or remaining resource size.
8. Error messages and evidence are bounded.
9. Filename extension is metadata only.
10. A detector cannot silently convert detection uncertainty into a security verdict.

## Serialization

`ScanResult` MUST support conversion to plain Python primitives suitable for JSON:

```python
result.to_dict()
```

The schema includes a version field from the first release:

```text
schema_version = 1
```

This is important because `scan()` is expected to feed CLIs, security reports, metadata pipelines, and potentially persisted artifacts.

Datetime values serialize as ISO 8601 strings. Bytes in detection evidence serialize as a bounded hexadecimal representation rather than raw binary.

## Public API for MVP

The intended public surface is deliberately small:

```python
from cereja.io import (
    ArchiveMetadata,
    CoreMetadata,
    DetectionResult,
    ExecutableMetadata,
    Resource,
    ScanPolicy,
    ScanResult,
    TextMetadata,
    scan,
)
```

Low-level `Reader`, registry implementations, individual built-in detectors, and inspectors SHOULD remain private in the first release unless implementation demonstrates a concrete public use case.

This prevents premature commitment to extension mechanisms before the core has real usage.

## Relationship to `cereja.security`

The static security analyzer developed previously duplicates some low-level functionality that belongs in `cereja.io`, including:

- hashes;
- entropy;
- file-type detection;
- PE structural metadata;
- ZIP structural inspection.

No security code is migrated as part of the IO MVP implementation unless required to prove an integration contract.

After the MVP is stable, a separate migration should make `cereja.security` consume `ScanResult` and specialized facets while retaining security-specific:

- findings;
- heuristics;
- IOC extraction;
- malware-family logic;
- risk scoring.

`cereja.security` MUST remain semantically responsible for judgments; `cereja.io` supplies facts.

## Relationship to compression/archive support

Archive detection and `ArchiveMetadata` establish the substrate for a later archive service.

A future service may expose capabilities such as:

```python
inspect_archive(source)
iter_archive_members(source)
extract_archive(source, destination, policy=...)
```

The archive service should choose handlers from detected content, not solely from extension. ZIP, TAR, GZIP, and future optional RAR/7z backends can share this capability model.

`cereja decompress` support for non-Cereja archives is a later feature and is not part of this MVP.

## Relationship to legacy `FileIO`

The current `FileIO` remains functional and unchanged during this milestone.

The migration direction after IO 2.0 stabilizes is:

```text
FileIO.load(path)
    ↓
legacy adapter
    ↓
cereja.io Resource + detection
    ↓
legacy parser/handler selected with content-aware information
```

The migration must be incremental. Existing public `FileIO` behavior is a compatibility constraint; IO 2.0 architecture is not allowed to force an immediate breaking rewrite.

Long term, format parsing/editing currently embedded in the legacy `_io.py` should be decomposed into focused codecs/handlers, but that is explicitly outside the read-only MVP.

## Testing strategy

Tests MUST use synthetic and benign fixtures. Malicious samples must not be committed to the repository.

Required test categories:

### Resource/reader

- path-backed reads;
- bytes-backed reads;
- missing file;
- directory rejection;
- bounded reads;
- chunk iteration;
- large sparse/test file without full materialization.

### Detection

For each supported signature:

- valid minimal/representative fixture;
- misleading extension;
- no extension;
- truncated header;
- magic-prefix collision where structural validation is applicable;
- deterministic confidence/evidence.

### Facets

- UTF-8/text characteristics;
- ZIP metadata without extraction;
- malformed ZIP behavior;
- PE32/PE32+ metadata fixtures;
- malformed PE offsets;
- imphash reproducibility where implemented.

### Limits/security

- pathological declared offsets;
- excessive archive member count metadata;
- very long member names;
- no shell/process invocation;
- no archive extraction;
- bounded serialized evidence.

### Serialization

- deterministic `to_dict()`;
- schema version;
- facet serialization;
- issues serialization.

## Benchmarks

The implementation must add lightweight benchmarks or reproducible benchmark scripts for:

1. detection-only scan of small files;
2. detection of a large file without whole-file reading;
3. SHA-256 scan throughput for a large file;
4. `bytes` versus path-backed scan overhead;
5. multiple built-in detectors sharing probe ranges.

Benchmarks are used to catch architectural regressions, not to establish hard CI timing thresholds in the MVP.

## Documentation requirements

Public documentation must explain:

- extension versus content detection;
- `core`, `detection`, and `facets`;
- confidence/evidence semantics;
- supported MVP formats;
- read-only/safety guarantees;
- performance implications of hashes, entropy, and full-stream metrics;
- how `cereja.security` differs from neutral IO scanning;
- how future format support is expected to extend the system.

All public classes/functions require concise docstrings and type annotations.

## Acceptance criteria

The MVP is complete when all of the following are demonstrated:

1. `scan(path)` and `scan(bytes)` return equivalent format detection for identical content.
2. Renaming a supported file to an incompatible extension does not change its detected format; `extension_matches` reports the discrepancy.
3. A large file can be format-detected without being loaded completely into memory.
4. SHA-256 and entropy can be computed incrementally.
5. ZIP metadata is inspected without extraction.
6. PE metadata is inspected without external dependencies.
7. A scan can contain multiple facets without changing the `ScanResult` model.
8. New detector/inspector implementations can be registered in an isolated registry without changing scan orchestration.
9. Malformed/truncated supported formats return safe partial/unknown results rather than unsafe reads or unbounded allocations.
10. Results serialize deterministically with `schema_version=1`.
11. The existing `cereja.file.FileIO` test suite is unchanged and continues to pass.
12. The new implementation has no mandatory dependency outside Python's standard library.

## Deferred milestones

After acceptance of this MVP, recommended follow-up order is:

1. archive services: ZIP/TAR/GZIP inspection and safe member iteration;
2. `scan_many()` concurrency service;
3. migrate `cereja.security` low-level primitives onto `cereja.io`;
4. introduce write/atomic-write primitives;
5. build the `FileIO` compatibility adapter;
6. add media/document facets driven by concrete use cases;
7. optional third-party backends for formats that stdlib cannot support safely/reliably.

This order keeps the new core small while proving it against existing Cereja consumers before expanding its public surface.
