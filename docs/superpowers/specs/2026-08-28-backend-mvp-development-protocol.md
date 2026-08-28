# Evidence-Driven Backend MVP Development Protocol

## Status

Experimental project protocol for complex backend MVP work in Cereja. This document is intentionally living: rules may be tightened, simplified, promoted to reusable patterns, or removed as implementation evidence accumulates.

It is not yet a global Cereja skill. The protocol must first prove useful during `cereja.io` development. Stable, repeatedly validated techniques may later be promoted to project instructions or reusable agent skills.

## Purpose

The goal is not to maximize ceremony. The goal is to reduce expensive wrong turns while preserving implementation speed.

Use this protocol when a backend feature is architecturally significant, security-sensitive, performance-sensitive, cross-platform, reusable, difficult to validate, or has meaningful uncertainty about the correct implementation.

`cereja.io` is the first feature used to exercise and refine this protocol.

## Non-negotiable engineering constraints

Every covered feature MUST preserve these constraints unless the requirement itself is explicitly amended by the maintainer:

1. **Zero mandatory third-party runtime dependencies.** Production behavior must be implemented using Python and the operating-system facilities available through the standard library. External libraries may be used only in isolated comparative research/benchmark environments and MUST NOT become runtime or test requirements for Cereja.
2. **Cross-platform behavior.** Supported behavior must be designed for Windows, Linux, and macOS. Platform-specific optimization is acceptable only behind a portable contract with a tested fallback.
3. **Measured performance.** Performance claims require evidence. Relevant work must measure latency, throughput, memory, allocation behavior, and scaling characteristics as appropriate.
4. **Security by construction.** Untrusted input must be treated as hostile. Resource limits, bounded work, safe defaults, no execution of inspected content, and explicit failure modes are design requirements rather than later hardening.
5. **Reusable core, narrow public API.** Internal architecture may be richer than the public interface. Public contracts are promoted only when a concrete consumer requires them.
6. **Clear separation of responsibilities.** Parsing, detection, policy, orchestration, domain judgment, persistence, and compatibility layers must not be merged merely for convenience.
7. **No speculative abstraction.** New abstractions need a demonstrated use case, a measured problem, or a boundary required by the approved architecture.
8. **Maintainability is a delivery criterion.** Code must be typed where useful, PEP-8 compliant, cohesive, documented at public boundaries, testable in isolation, and understandable without reconstructing hidden agent reasoning.
9. **Differentiation must be concrete.** Cereja should aim to be materially easier, safer, faster, more explainable, or more composable than equivalent approaches. A feature that only duplicates an existing standard-library wrapper without measurable value should be challenged.
10. **Compatibility is explicit.** Existing public APIs are not silently broken. Migration, adapter, or deprecation decisions require an explicit specification.

## Sources of authority

When sources disagree, apply the following precedence:

1. explicit maintainer decisions and non-negotiable constraints;
2. approved feature specification and architecture decisions;
3. verified experimental evidence from this repository;
4. Python language/stdlib documentation and applicable standards;
5. security guidance and format specifications;
6. behavior of comparable libraries/tools;
7. implementation preference.

Comparable tools are evidence, not authority. Cereja does not inherit another project's architecture merely because it is popular.

## Core development loop

The protocol separates **known work** from **uncertain work**.

A task with an already-proven implementation path may proceed through normal TDD. A task that violates a constraint, fails a test/benchmark, depends on an unverified assumption, or has multiple credible implementation strategies MUST enter the Investigation Loop before solution code is written.

```text
objective
  ↓
context + dependency map
  ↓
requirements / invariants / budgets
  ↓
known path? ── yes ──→ TDD implementation
  │
  no / failure / uncertainty
  ↓
investigation
  ↓
hypotheses
  ↓
rank + select
  ↓
isolated proof of concept
  ↓
measure / falsify
  ↓
knowledge record
  ↓
design decision
  ↓
TDD implementation
  ↓
verification + benchmark + review
  ↓
knowledge promotion check
```

## Task readiness gate

A task is ready for implementation only when all applicable items are known:

- target user/consumer and observable outcome;
- relationship to the current MVP objective;
- upstream inputs and downstream consumers;
- public API impact, if any;
- correctness invariants;
- security boundaries and resource limits;
- performance budget or measurement plan;
- cross-platform expectations;
- dependency constraints;
- acceptance tests;
- whether the implementation path is already proven.

Missing information does not automatically block the whole feature. It determines whether the task enters investigation before implementation.

## Investigation trigger

Investigation is REQUIRED when any of the following occurs:

- an implementation would violate or weaken a non-negotiable constraint;
- a correctness, security, compatibility, portability, or performance requirement is not met;
- a benchmark regresses materially and the cause is not established;
- a test exposes behavior whose root cause is unknown;
- two or more credible designs have materially different trade-offs;
- the standard library behaves differently across platforms or versions in a way that affects the contract;
- a parser or detector needs assumptions not justified by a format specification or reliable evidence;
- an optimization is proposed without evidence that the relevant path is a bottleneck;
- a workaround starts accumulating special cases;
- a task depends on behavior inferred only from filename extension, MIME metadata, undocumented implementation details, or another unverified hint;
- an agent is about to solve a symptom while the causal mechanism remains uncertain.

## Investigation loop

### 1. Re-state the objective

Record what must become true and why it matters to the MVP. Do not start from a preferred implementation.

Example:

```text
Objective: classify a ZIP-like resource without unbounded metadata allocation.
Why it matters: archive inspection is an IO 2.0 facet and is part of the untrusted-input boundary.
Dependent flow: scan → detection → archive inspector → security/compression consumers.
```

### 2. Map dependencies and importance

Identify:

- what information this task consumes;
- what components consume its output;
- whether it is on the critical MVP path;
- what can proceed without it;
- what failure mode it can introduce;
- whether a simpler degraded behavior is acceptable for the MVP.

This prevents spending disproportionate time on non-critical elegance.

### 3. Research before proposing a fix

Research should be scoped to the uncertainty, not performed as an open-ended literature review.

Potential evidence sources:

- repository code, tests, history, and related flows;
- prior validated Cereja experiments;
- Python documentation and CPython behavior;
- relevant PEPs;
- file-format specifications and standards;
- OWASP or equivalent security guidance;
- established comparable libraries/tools;
- public bug reports and implementation discussions when primary documentation is insufficient;
- benchmark data.

Record links/references or precise local locations when the evidence affects a design decision.

### 4. Generate falsifiable hypotheses

Do not jump directly from research to solution. Produce competing explanations or implementation hypotheses.

A useful hypothesis has:

```text
HYPOTHESIS ID
statement
reasoning/evidence
expected observable result
falsification condition
cost to test
risk if wrong
```

Example:

```text
H1: EOCD preflight can reject pathological ZIP central directories before ZipFile construction.
Expected: entry count and central-directory size can be bounded using <= 66 KiB tail reads.
Falsified if: valid common ZIP variants require unbounded scans or the required fields cannot safely bound parser allocation.
```

### 5. Rank hypotheses

Prefer experiments that maximize information gained per unit of effort.

Ranking factors:

- impact on correctness/security;
- importance to current MVP path;
- probability of resolving the uncertainty;
- experiment cost;
- reversibility;
- portability implications.

Do not select a hypothesis because it matches the current implementation preference.

### 6. Isolated proof of concept

Each selected hypothesis MUST be tested outside production implementation first when the uncertainty is material.

A PoC should:

- test one primary hypothesis;
- use the smallest realistic input set;
- avoid changing public API;
- avoid creating architecture that later has to be preserved;
- capture timings/memory where performance is part of the claim;
- include adversarial/malformed input where security/correctness is relevant;
- be easy to delete after learning is captured.

PoC code is disposable. Knowledge is the deliverable.

### 7. Decide from evidence

Classify the result:

- **supported** — evidence is strong enough to inform implementation;
- **rejected** — evidence falsified the hypothesis;
- **inconclusive** — another experiment or a reduced requirement is needed.

An inconclusive result MUST NOT silently become an implementation assumption.

## Experiment record

Material experiments should be captured in a concise record using this structure:

```markdown
# EXP-<id>: <question>

## Context
<why this matters and dependent flow>

## Hypothesis
<falsifiable claim>

## Method
<inputs, environment, commands, controls>

## Results
<observations and measurements>

## Conclusion
supported | rejected | inconclusive

## Implications
<what design/task/spec changes, if anything>

## Reusable knowledge candidate
pattern | antipattern | invariant | benchmark method | platform note | none
```

Exact raw benchmark output may live beside the record when useful. The record itself should stay readable.

## Knowledge lifecycle

Experiments produce **knowledge candidates**, not immediate universal rules.

A candidate may be:

- **Invariant** — a fact the implementation must preserve;
- **Pattern** — a repeatedly useful technique with known applicability;
- **Antipattern** — a demonstrated approach that fails or creates unacceptable trade-offs;
- **Platform note** — relevant Windows/Linux/macOS behavioral difference;
- **Benchmark method** — a reproducible way to measure a class of operation;
- **Security rule** — a validated boundary or hostile-input constraint;
- **Format note** — verified structural behavior of a supported file format.

Promotion levels:

```text
observation
  ↓ reproduced
knowledge candidate
  ↓ reused successfully / corroborated
project instruction
  ↓ general across projects + skill tests
reusable skill/pattern
```

A one-off experiment SHOULD NOT become a global instruction unless the underlying standard/specification makes the result intrinsically general.

## Pattern / antipattern record

Promoted technical knowledge should state applicability and limits, not merely describe history.

```markdown
## Pattern: Bounded tail preflight
Use when: a format places a bounded locator near EOF and the full parser can allocate from attacker-controlled metadata.
Guarantee: rejects resources exceeding declared structural limits before expensive parser construction.
Does not guarantee: semantic validity or decompression safety.
Evidence: EXP-...
Counterexamples: ...
```

An antipattern should include the failed mechanism:

```markdown
## Antipattern: Extension-directed parser selection for untrusted input
Fails because: filename suffix is caller-controlled and can disagree with resource bytes.
Acceptable only when: the caller explicitly treats the extension as a trusted schema contract.
Evidence: ...
```

## Benchmark protocol

Benchmarking is part of the feature contract when performance is a stated differentiator or when implementation alternatives have meaningful cost differences.

### Benchmark goals

Measure the relevant subset of:

- cold/warm latency;
- throughput;
- peak memory / bounded allocation behavior;
- bytes read relative to input size;
- operations/seeks when meaningful;
- scaling with file size/member count;
- malformed/adversarial behavior;
- concurrency scaling in future services.

### Comparative baseline

Comparable implementations may include:

- Python standard-library direct implementation;
- the current Cereja implementation;
- established third-party libraries with similar capabilities;
- command-line tools where API-level comparison is not meaningful.

External comparison tools/libraries MUST remain optional and isolated from Cereja runtime/test dependencies.

A comparison must state where semantics differ. Faster results obtained by doing less validation are not presented as equivalent performance.

### Methodology requirements

- capture Python version, OS, architecture, storage context where relevant, and input corpus characteristics;
- include warm-up where appropriate;
- execute enough repetitions to expose variance;
- use a monotonic high-resolution timer such as `time.perf_counter_ns()` for in-process wall time;
- separate fixture generation from timed code;
- use identical corpora and equivalent validation levels when comparing libraries;
- report distributions or at least median plus dispersion, not a single lucky run;
- investigate regressions rather than tuning the benchmark to hide them;
- preserve reproducible benchmark scripts in the repository when they guard an important performance contract.

The production package remains zero-dependency even if a dedicated developer environment installs comparison libraries.

## Cross-platform verification

A feature is not considered portable because it uses only the standard library. Behavior must be validated.

For relevant tasks, verification covers Windows, Linux, and macOS for:

- path semantics;
- timestamps and metadata meanings;
- file locking/sharing behavior;
- symlink behavior;
- binary/text mode differences;
- filesystem replacement/mutation behavior;
- available stat fields;
- encoding defaults when unavoidable;
- platform-specific optimizations and fallbacks.

Tests should assert the public invariant, not force platforms to expose identical low-level metadata.

## Security review gate

For untrusted-input features, review at minimum:

- bounded reads and allocations;
- cumulative work budget;
- integer/offset/range validation;
- malformed/truncated input;
- path traversal when paths/member names exist;
- symlink/hardlink behavior when applicable;
- decompression/resource amplification when applicable;
- unsafe deserialization/execution/import behavior;
- subprocess/shell interaction;
- TOCTOU/source mutation;
- ambiguity/polyglots;
- exception leakage and partial-result semantics;
- data retained in evidence/logs.

The absence of a known exploit is not proof that the boundary is safe.

## Public API gate

Before exposing a new class/function publicly, answer:

1. Which external consumer needs it now?
2. Can the same goal be served by an existing public abstraction?
3. Is the behavior stable enough to support backward compatibility?
4. Does exposing it leak an implementation mechanism rather than a domain capability?
5. Can it remain internal through the MVP and be promoted later without blocking consumers?

Default to private until there is a real public use case.

## Complexity gate

When introducing a new abstraction, registry, strategy, cache, worker model, adapter, or protocol, document:

- concrete problem it solves;
- simpler alternative considered;
- evidence the simpler alternative is insufficient;
- lifecycle/ownership;
- test boundary;
- removal cost if the hypothesis is wrong.

If those answers are weak, do not add the abstraction.

## Task completion gate

A task is complete only when all applicable evidence exists:

- acceptance behavior passes automated tests;
- regression tests cover the failure/requirement that motivated the task;
- malformed/adversarial cases pass where applicable;
- no mandatory external dependency was introduced;
- cross-platform contract is preserved and platform-specific assumptions are documented/tested;
- benchmarks meet the stated target or the observed trade-off is explicitly accepted;
- implementation does not violate resource/security budgets;
- public API additions passed the public API gate;
- relevant documentation/specification is updated;
- temporary PoC code is removed or clearly isolated from production;
- experiments produced a conclusion, not just output;
- reusable knowledge candidates are recorded;
- no unresolved critical hypothesis is hidden in implementation code.

A passing unit test suite alone is not sufficient for performance-, security-, portability-, or architecture-sensitive tasks.

## Review checkpoints

Complex work should be reviewed at boundaries where evidence can still change direction cheaply:

1. **Specification review** — objective, constraints, consumers, non-goals.
2. **Investigation review** — evidence and hypotheses before solution commitment.
3. **PoC review** — whether evidence supports the selected design.
4. **Implementation review** — spec compliance and tests.
5. **Performance/security review** — benchmarks, budgets, adversarial cases.
6. **Knowledge review** — promote, keep as candidate, or discard learned rules.

Not every trivial task needs six meetings/checkpoints. The workflow scales with uncertainty and risk.

## Relationship to TDD and debugging

This protocol does not replace test-driven development or systematic debugging.

- Known implementation work uses TDD directly.
- Unknown causal behavior uses investigation/root-cause analysis first, then TDD for the selected solution.
- A PoC proves or rejects an assumption; it is not the production implementation.
- Production code still requires tests written around observable behavior/invariants.

This distinction prevents TDD from being misused to rapidly implement an unproven design.

## Living protocol governance

Changes to this protocol require evidence from development, not stylistic preference.

When `cereja.io` reveals friction, record:

```text
problem observed
current rule involved
why the rule helped or failed
proposed adjustment
supporting experiment/task/review
```

Protocol evolution should prefer simplification. A new rule is justified only if it prevents a recurring failure mode or encodes a high-value invariant.

Periodically remove rules that are redundant, unenforceable, or never affect decisions.

## Initial application to `cereja.io`

The IO 2.0 implementation should use this protocol to validate at least:

- position-independent bounded reads;
- stable single-open resource identity;
- scan-wide budgets;
- detector evidence model;
- ambiguous/polyglot detection behavior;
- ZIP metadata preflight before expensive parsing;
- single-pass whole-file metric collection;
- default scan cost versus explicit forensic scan cost;
- Windows/Linux/macOS filesystem semantics;
- performance against direct stdlib approaches and selected comparable detection/inspection libraries or tools;
- memory behavior on large and adversarial files.

These experiments should refine both `cereja.io` and this protocol.

## External methodology influences

This protocol intentionally borrows only high-value ideas rather than adopting a full framework:

- Spec-driven development: durable specification and explicit constraints before implementation;
- hypothesis-driven engineering: falsifiable assumptions and isolated experiments before committing uncertain designs;
- TDD: observable behavior and regression evidence for production implementation;
- ADR-style reasoning: preserve important decisions and rejected alternatives;
- benchmark-driven optimization: measure before and after optimization;
- security threat modeling: define hostile boundaries and resource limits before coding.

The protocol remains Cereja-specific until repeated use demonstrates that some parts are broadly reusable.
