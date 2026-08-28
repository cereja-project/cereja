# EDD Case Study #001 — `cereja.io`

## Status

Baseline and living case-study record for the first validation cycle of **Evidence-Driven Development (EDD)**.

This document captures the state of the case before production implementation of `cereja.io` begins. Its purpose is to preserve the initial problem, decisions, uncertainties, methodology interventions, expected measurements, and evidence requirements so that later evaluation does not depend on chat history or retrospective reconstruction.

The case study is not a success report. At this stage it establishes the baseline and the claims that must still be tested.

## Case identity

- **Case:** EDD-001
- **Project:** `cereja-project/cereja`
- **Feature:** `cereja.io`
- **Milestone:** IO 2.0 — Read-only MVP
- **EDD version:** experimental v0.1
- **Case phase:** architecture/specification, before implementation plan
- **Primary implementation constraint:** zero mandatory third-party dependencies
- **Target platforms:** Windows, Linux, macOS

## Why this case was selected

`cereja.io` is intentionally difficult enough to test whether EDD adds value without being so broad that outcomes become impossible to attribute.

The feature combines:

- low-level filesystem and binary I/O;
- untrusted input;
- format detection;
- structural metadata extraction;
- archive handling;
- executable inspection;
- cross-platform semantics;
- performance-sensitive paths;
- public API design;
- migration from a legacy abstraction;
- reuse by security and compression flows.

These characteristics create technical uncertainty where premature implementation can produce expensive architectural debt.

## Original engineering problem

The existing `cereja.file.FileIO` model selects specialized handlers primarily through filename extension. This is convenient for trusted application flows but is insufficient as a general foundation for:

- safe archive/compression support;
- security inspection;
- trustworthy metadata generation;
- files with misleading or missing extensions;
- future reusable file services.

The initial desire was to expand compression support and possibly add a generic scan feature. Examination of the current design exposed a deeper dependency: a trustworthy scan/compression architecture requires a cleaner low-level I/O foundation.

This led to the decision to create `cereja.io` as a new core rather than continue extending the legacy `FileIO` model.

## Feature objective

Build a small, read-only, content-aware I/O core that can safely and efficiently describe file resources without trusting filename extensions and without introducing mandatory external dependencies.

The MVP should become reusable infrastructure for:

- `cereja.security`;
- future archive/compression services;
- metadata inspection;
- a progressive compatibility adapter beneath `cereja.file.FileIO`.

## Non-negotiable constraints

The case is invalid as an EDD success if implementation achieves functionality by weakening these constraints:

1. no mandatory third-party runtime dependencies;
2. no mandatory third-party test dependency required for Cereja's normal test suite;
3. Windows, Linux, and macOS compatibility by design;
4. hostile/untrusted input assumptions at the core boundary;
5. bounded work and bounded allocation for default inspection paths;
6. measurable performance rather than assumed performance;
7. narrow public API with richer implementation details kept private until needed;
8. clear separation between neutral I/O facts and security judgments;
9. maintainable, typed, documented, PEP-8-compliant implementation;
10. concrete differentiation in safety, usability, performance, explainability, composability, or equivalent value;
11. benchmark comparison with equivalent stdlib approaches and relevant mature tools/libraries where meaningful;
12. legacy `FileIO` must not be broken by the read-only MVP.

External libraries may be installed in isolated benchmark/research environments solely for comparison.

## Scope of the read-only MVP

The current intended public capability is centered on:

```python
from cereja.io import scan

result = scan(source)
```

Initial source forms:

- `str` / `os.PathLike[str]` path;
- immutable `bytes`.

The MVP is intentionally not a complete file framework. It excludes:

- write/mutation APIs;
- archive extraction;
- recursive archive-member scanning by default;
- `scan_many()` concurrency;
- remote/network sources;
- broad media/document parsing;
- security verdicts or malware scoring;
- migration/deprecation of the legacy `FileIO` API.

## Architecture decisions reached during brainstorming

### 1. Three-layer direction

Long-term responsibilities are separated into:

1. **`cereja.io` core** — resource access, bounded reading, detection, neutral metadata, inspectors and internal registries;
2. **`cereja.io` services** — orchestration such as `scan()` and, later, batch/archive services where concurrency can be introduced deliberately;
3. **compatibility/domain adapters** — the existing `cereja.file.FileIO`, progressively consuming `cereja.io` without forcing the new core to depend on legacy APIs.

`cereja.security` is a lateral consumer, not part of the I/O core.

### 2. Neutral scan vs security analysis

`cereja.io` reports facts. It does not make security judgments.

Example:

```text
cereja.io:
  declared extension = .jpg
  detected format = PE

cereja.security:
  executable disguised with an image extension is suspicious
```

This boundary prevents security policy from contaminating reusable I/O primitives.

### 3. Core metadata + typed facets

A scan result is not modeled as one rigid subclass per file type.

Conceptually:

```text
ScanResult
├── core
├── detection
├── facets
└── issues
```

Universal facts live in core metadata. Format identity lives in detection. Specialized structural facts are represented by typed facets.

The initial useful facets are deliberately limited to:

- `TextMetadata`;
- `ArchiveMetadata`;
- `ExecutableMetadata`.

New facets must be driven by real consumers rather than speculative taxonomy design.

### 4. Multiple facets are allowed

One resource may have several relevant structural interpretations. This avoids class hierarchies such as `ArchiveDocumentFile` or `XmlImageFile` and permits future formats such as DOCX, SVG or APK to expose more than one useful structural view.

### 5. Extension is a hint, never authority

Filename extension is retained as declared source metadata but does not determine the parser or increase content-evidence strength.

## Independent review and design corrections

An independent architecture review challenged the first design from correctness/security, performance, API, and extensibility perspectives. This produced several material corrections **before implementation**, which is already relevant evidence for the EDD process.

### Stable-open resource identity

The initial design did not strongly require one stable opened source for the complete scan. Review identified a TOCTOU/correctness risk: repeated opening could combine detection and metadata from different versions of a changing file.

Revised direction:

```text
Resource descriptor
  ↓
open once
  ↓
private ResourceHandle
  ↓
all scan operations
```

Descriptor metadata should use the opened handle (`fstat` where portable) when practical, and source mutation during scanning should be detectable.

### Position-independent reader contract

The initial generic `read(offset, size)` concept was refined to logical position-independent primitives:

```text
read_at(offset, size)
read_head(size)
read_tail(size)
iter_chunks(...)
```

Detector behavior must not depend on shared cursor state.

### Scan-wide work budget

Per-read limits were recognized as insufficient. A hostile input can cause many individually small reads or structural traversals.

The revised architecture requires cumulative budgets for relevant work such as:

- probe bytes;
- read operations/seeks;
- structural entries visited;
- retained evidence;
- explicit permission for complete sequential passes.

### Cheap bounded default scan

The first draft enabled SHA-256 by default. Review showed this contradicts the goal of a fast metadata/detection scan because scanning a very large resource would necessarily become a full-file operation.

Revised direction:

- full hashes disabled by default;
- full entropy disabled by default;
- detection and cheap facets bounded by default;
- expensive whole-stream metrics explicitly enabled by policy.

### Single-pass expensive metrics

When multiple whole-stream metrics are requested, one sequential traversal should update all incremental collectors rather than reading the resource once per metric.

This is both a performance requirement and a candidate reusable technical pattern to validate during implementation.

### Preserve ambiguity/polyglots

The original design selected one highest-confidence candidate. Review identified information loss for polyglot/ambiguous resources.

Revised direction:

- ergonomic primary detection;
- bounded credible alternatives preserved;
- inspectors may consume relevant candidate evidence rather than only the primary kind.

### Ordinal evidence strength

A floating numerical confidence such as `0.97` was judged misleading without a calibrated scoring model.

The MVP should use documented ordinal evidence strength such as:

```text
weak | probable | strong | verified
```

`verified` refers only to the detector's structural checks, not resource safety or complete semantic validity.

### Archive vs compressed stream

ZIP/TAR and GZIP are not the same abstraction. The design must distinguish member-oriented archives/containers from compressed streams so future compression services are not forced into an incorrect taxonomy.

### ZIP preflight

For hostile ZIP metadata, safety limits applied only after unrestricted `ZipFile` metadata construction may be too late.

The current direction is to investigate bounded EOCD/central-directory preflight before permitting more expensive ZIP parsing.

This is explicitly an **unproven implementation hypothesis** until the planned PoC validates it across valid ZIP variants and malformed/adversarial fixtures.

### Portable timestamps

A generic `created_at` is not portable. The design should distinguish available semantics such as:

- `modified_at`;
- `accessed_at`;
- `metadata_changed_at` when meaningful;
- `birth_time` only where the platform exposes actual creation/birth time.

### Smaller initial public surface

Reader, registry, scan budgets, candidates, detector contexts and internal handles remain private in the MVP unless a concrete external consumer proves a public contract is necessary.

## First observable EDD effect

Before production implementation started, independent review changed several design decisions materially:

- default SHA-256 changed from enabled to disabled;
- one-open resource consistency became an explicit invariant;
- the reader contract changed to position-independent bounded access;
- a cumulative scan budget was added;
- numerical confidence was challenged in favor of evidence strength;
- polyglot alternatives were preserved instead of discarded;
- archive/compressed-stream taxonomy was separated;
- ZIP safety moved toward a preflight investigation rather than immediate use of the obvious stdlib path;
- PE facet scope was reduced to keep the MVP focused;
- public API exposure was reduced.

These changes are not yet proof that EDD improves final delivery, but they are baseline examples of design correction occurring before production code created compatibility or maintenance cost.

## Known uncertainties entering implementation

The following questions must not silently become assumptions:

### IO-UNC-001 — random bounded read strategy

Question: what portable implementation gives correct position-independent reads with acceptable performance on Windows, Linux, and macOS?

Candidate strategies may include buffered `seek` + `read` under controlled ownership and optional platform-specific primitives only if benchmarks justify complexity.

Decision must be evidence-driven; `mmap` is not assumed.

### IO-UNC-002 — probe caching

Question: does a small bounded probe cache materially reduce repeated reads across detectors without adding complexity or memory overhead that outweighs the benefit?

Do not add caching without measurement.

### IO-UNC-003 — ZIP preflight sufficiency

Question: can bounded tail/EOCD parsing safely reject pathological ZIP metadata before `zipfile` construction while accepting the common/required valid ZIP variants?

Requires isolated PoC with normal, ZIP64 where applicable, truncated and adversarial fixtures.

### IO-UNC-004 — detection ranking model

Question: what deterministic evidence ordering is sufficient for heterogeneous detectors without inventing false probability semantics?

Must preserve ambiguity and remain explainable.

### IO-UNC-005 — text detection boundaries

Question: which stdlib-only heuristics provide useful text/binary distinction without pretending to identify arbitrary encodings reliably?

### IO-UNC-006 — whole-stream metric cost

Question: what chunk sizes and collector organization provide good throughput/memory behavior across relevant file sizes/platforms?

Requires benchmark rather than intuition.

### IO-UNC-007 — PE parser MVP boundary

Question: which PE fields can be safely and maintainably parsed zero-dependency in the first increment without expanding the parser surface disproportionately?

The current recommendation is basic structural metadata only; imports/imphash remain deferred unless existing reviewed code plus malformed-fixture tests make their cost small.

## Candidate hypotheses for early experiments

These are candidates, not accepted truths.

### H-001 — bounded random reads need no public platform specialization

A portable internal implementation using one stable file handle and bounded seek/read can satisfy the MVP contract; platform-specific read primitives will not provide enough benefit to justify public or architectural specialization.

**Falsify if:** benchmarks or correctness tests expose unacceptable contention, cursor interference, portability problems, or material throughput/latency loss in the target workloads.

### H-002 — one-pass metric collection is materially better than independent passes

Updating all requested incremental metrics during one sequential traversal reduces I/O cost with acceptable implementation complexity.

**Falsify if:** multi-collector CPU overhead dominates realistic workloads or specialized stdlib paths materially outperform it while preserving equivalent semantics.

### H-003 — ZIP EOCD preflight can create a useful safety boundary

A bounded tail read can establish enough central-directory limits to reject pathological metadata before expensive parsing for the supported ZIP subset.

**Falsify if:** supported valid archives require behavior incompatible with the bounded assumptions or parser allocation cannot be meaningfully bounded by this preflight.

### H-004 — typed facets reduce coupling without overengineering

A small facet model allows archive, executable and text consumers to evolve independently while keeping `ScanResult` stable.

**Falsify if:** implementation repeatedly requires facet cross-dependencies, awkward registry machinery, or more code/indirection than direct typed fields would require for the real MVP consumers.

### H-005 — bounded default scan is a meaningful product differentiator

A default content-aware scan can identify useful formats and structural metadata while reading only a small portion of large inputs, producing lower latency/I/O than equivalent full-content analysis paths without sacrificing the declared semantics.

**Falsify if:** supported detection/facets routinely require whole-file access or the bounded behavior offers no meaningful usability/performance advantage in comparison benchmarks.

## Benchmark plan

The case must include reproducible comparative benchmarks where semantics are equivalent.

### Primary metrics

Measure where applicable:

- wall-clock latency distribution;
- throughput;
- peak memory or bounded allocation behavior;
- bytes read relative to source size;
- number of read operations/seeks when useful;
- scaling with input size;
- scaling with structural entry count;
- malformed/adversarial input behavior.

### Workload classes

At minimum include representative:

- tiny files;
- typical files;
- large sparse/generated fixtures where safe;
- unknown/binary inputs;
- text;
- ZIP with increasing member counts;
- malformed/truncated inputs;
- PE samples/fixtures sufficient for structural parsing tests.

### Comparative baselines

Depending on capability, compare with:

- direct Python stdlib approaches;
- current Cereja file/archive behavior where equivalent;
- mature external detection/metadata libraries or tools in isolated benchmark environments.

Comparisons must state semantic differences. A faster implementation that performs less validation is not an equivalent win.

### Cross-platform evidence

Important benchmark/correctness suites should run on Windows, Linux, and macOS where GitHub Actions or equivalent execution is available.

Results must not force identical OS internals; they must verify the public invariant and expose meaningful platform differences.

## EDD measurement plan for this case

The case study evaluates both the artifact and the methodology.

### Engineering quality

Record:

- bugs/regressions discovered before and after implementation;
- invariant violations;
- review findings;
- decisions reverted after implementation;
- platform-specific failures;
- security/resource-boundary failures.

### Investigation effectiveness

Record:

- tasks that entered investigation;
- hypotheses tested;
- supported/rejected/inconclusive counts;
- design/implementation decisions changed by experiment;
- code paths avoided because a hypothesis was rejected;
- unresolved hypotheses that blocked or reduced scope.

### Delivery cost

Record approximately where practical:

- investigation time;
- implementation time;
- benchmark/verification time;
- rework time;
- blocked time caused by unresolved uncertainty.

The goal is directional evidence, not false precision.

### Knowledge compounding

Record:

- knowledge candidates produced;
- candidates later reused;
- repeated research that should have been avoided;
- project instructions/patterns/antipatterns/skills/checks promoted;
- promoted guidance later rejected or revised;
- cases where existing validated guidance allowed a task to skip investigation safely.

### Context/process cost

Observe:

- repeated reading of large documents;
- repeated reasoning about already-decided questions;
- agent loops;
- duplicated records;
- methodology steps that fail to affect decisions;
- documents/instructions that can be shortened or retrieved only on demand.

The EDD protocol must be simplified when evidence shows its own ceremony is wasteful.

## Knowledge candidates already visible

These are not yet globally promoted patterns unless supporting evidence is strong enough.

### Candidate: extension-directed parser selection is unsafe for untrusted/general inspection

The filename suffix is caller-controlled metadata and may conflict with actual content. It can remain useful as a trusted schema contract in explicitly controlled application flows, but it should not be the source of truth for general scanning.

### Candidate: expensive optional metrics should share a stream pass

When several whole-content incremental calculations are requested, sharing traversal is likely preferable to independent full reads. Requires benchmark confirmation before broad promotion.

### Candidate: public API should be smaller than internal architecture

Low-level handles, budgets and detector machinery can remain internal until a real external extension use case exists, reducing premature compatibility obligations.

### Candidate: evidence strength should not pretend to be probability

A numerical score is inappropriate when heterogeneous detectors have no calibrated common statistical model.

### Candidate: stable-open scanning prevents mixed-version results

A scan should derive its facts from one opened source identity where possible, with mutation detection for long-running/full-pass operations.

## Expected EDD knowledge-promotion opportunities

During the case, useful validated knowledge may become:

- Cereja project instructions;
- file-format invariants;
- security boundaries;
- benchmark methodology;
- platform notes;
- implementation patterns/antipatterns;
- automated tests/checks;
- later, reusable agent skills when a technique is general and independently shown to improve behavior.

A skill is not considered useful merely because it encodes a lesson. It must be tested as an intervention against baseline agent behavior or repeated engineering failure.

## Evidence provenance model

Major conclusions in this case should point to one or more of:

- GitHub Issue;
- experiment record;
- benchmark record/raw result;
- automated test;
- source commit/PR;
- official specification/documentation;
- external research/reference.

The final case report must be reconstructable without this chat history.

## Operational model

Once project tracking is established:

- GitHub Project provides lean state;
- Issues are the unit of execution/investigation/evidence discussion;
- Milestone represents `IO 2.0 — Read-only MVP`;
- code/spec/experiments/benchmarks specific to the case remain in `cereja`;
- generalized EDD knowledge moves to the dedicated methodology repository only after promotion criteria are met.

The Project should stay lean. Initial useful fields are:

```text
Status
Type
Area
Risk
Evidence
Milestone
```

Detailed methodology data belongs in issue templates/evidence artifacts unless repeated usage proves that another Project field provides real value.

## Current baseline before implementation

At the time this baseline is frozen:

- no `cereja.io` production implementation has started under this design;
- a first IO 2.0 architecture spec exists;
- an independent architecture review has materially changed several proposed decisions;
- an experimental backend MVP development protocol exists;
- the EDD charter v0.1 exists;
- the methodology remains experimental;
- EDD has not yet demonstrated reduced total delivery time, defect rate, context cost, or rework;
- several early technical hypotheses remain untested;
- this case will establish the initial measurement baseline rather than claiming arbitrary improvement percentages.

## Case success conditions

EDD-001 is considered a useful positive case if, by the end of the read-only MVP, there is traceable evidence that:

1. important design/implementation decisions were improved or changed by investigation or experiments;
2. at least one plausible hypothesis was rejected before creating production debt;
3. technical quality is supported by tests, adversarial cases, cross-platform verification and meaningful benchmarks;
4. one or more validated knowledge units are reused by later tasks;
5. the process remains proportionate to engineering risk rather than becoming mandatory ceremony;
6. at least one EDD rule/artifact is simplified, removed or refined based on observed friction;
7. the final architecture remains maintainable and the public API remains intentionally small;
8. the case can be reconstructed from repository evidence without relying on chat memory.

A negative or mixed outcome is also valuable if documented. The methodology must permit the conclusion that EDD adds excessive overhead, that a particular gate is ineffective, or that a proposed knowledge mechanism does not improve agent behavior.

## Exit criteria for the case-study phase

The initial case-study phase ends when the `cereja.io` read-only MVP reaches its agreed acceptance criteria and the case has enough evidence to produce a retrospective answering:

- what EDD changed;
- what EDD failed to change;
- what it cost;
- what it prevented;
- what knowledge was reused;
- what methodology rules were retained, changed or removed;
- which conclusions are specific to `cereja.io` and which plausibly generalize.

Expansion of EDD beyond this case should be decided only after that retrospective.

## Current source documents

This case currently depends on:

- `2026-08-28-evidence-driven-development-charter-v0.1.md`;
- `2026-08-28-backend-mvp-development-protocol.md`;
- `2026-08-28-io2-readonly-mvp-design.md`;
- `2026-08-28-io2-readonly-mvp-independent-review.md`.

The main IO design spec must still be revised to incorporate the accepted independent-review corrections before an implementation plan is produced.
