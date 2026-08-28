# Evidence-Driven Development (EDD) — Charter v0.1

## Status

Experimental methodology charter. This document freezes the decisions from the initial brainstorming phase and serves as the temporary source of truth until the methodology is moved to a dedicated repository.

The methodology is intentionally narrow in its first validation cycle. `cereja.io` is case study #001.

## Working name

**Evidence-Driven Development (EDD)**

The name is a working title. It intentionally relates to, but is not identical with, Evidence-Based Software Engineering. The methodology may be renamed later if research or validation shows a clearer distinction is necessary.

## Problem

Agentic software development and "vibe coding" make code generation cheap, fast, and abundant, but they do not make correctness, architectural quality, portability, security, maintainability, performance, or decision quality proportionally cheap.

Common failure modes include:

- agents implementing before uncertainty is understood;
- repeated rediscovery of already-known facts;
- large specs that consume context repeatedly;
- conclusions being recomputed across sessions;
- context growth degrading quality;
- agents entering loops and revisiting resolved questions;
- unverified assumptions turning into production code;
- apparent rigor through verbose reports without real evidence;
- knowledge being lost after a session ends;
- instructions and skills being written without proof that they improve behavior;
- popular public knowledge being ignored and rediscovered locally;
- performance, security, and portability being treated as late validation instead of design constraints.

## Primary objective

EDD is an experimental engineering protocol for agent-assisted software development designed to reduce unverified decisions, rework, and quality degradation through:

- specification proportional to risk and uncertainty;
- explicit identification of unknowns;
- falsifiable hypotheses;
- isolated proof-of-concept experiments;
- reproducible and traceable evidence;
- evidence-backed design decisions;
- TDD for production implementation;
- independent verification, review, and benchmarking;
- selective promotion of validated knowledge into reusable operational guidance.

EDD must remain lightweight enough that its cost does not exceed the engineering risk it is intended to reduce.

## Secondary objective: knowledge compounding

EDD should not only produce reliable software. It should progressively improve the system that produces future software.

Validated engineering evidence should be compressed into reusable, provenance-preserving knowledge so that future agents need less repeated context, investigation, and reasoning for problems that have already been solved.

The target feedback loop is:

```text
problem
  ↓
investigation
  ↓
evidence
  ↓
decision
  ↓
implementation
  ↓
validation
  ↓
knowledge
  ↓
instruction / pattern / skill / automated check
  ↓
future execution with less repeated reasoning
  ↓
new evidence
```

This is not permission to create many instructions or skills. Promotion must be selective and evidence-backed.

## Initial research question

The first validation cycle asks:

> Does Evidence-Driven Development improve the quality and predictability of a complex backend developed with coding agents without creating disproportionate process overhead?

A secondary research question asks:

> Can validated engineering evidence be progressively compressed into reusable instructions, patterns, skills, and automated checks that reduce future context cost and repeated reasoning without degrading correctness?

## Case study #001

`cereja.io` is the first EDD case study.

The case is appropriate because it contains meaningful uncertainty across:

- architecture;
- binary and file I/O;
- untrusted input;
- security boundaries;
- performance;
- cross-platform behavior;
- extensibility;
- format detection;
- archive handling;
- public API stability;
- migration from an existing `FileIO` model.

## Initial scope

EDD v0.1 targets:

- backend development;
- agent-assisted or agentic engineering workflows;
- greenfield or brownfield feature development;
- tasks with meaningful uncertainty or impact;
- architecture, performance, security, portability, and reusable infrastructure work.

The first validation cycle does NOT attempt to prove applicability to frontend, mobile, product management, data science workflows, organization-wide project management, or every class of software development.

## Non-negotiable engineering constraints for case study #001

The `cereja.io` case must preserve:

1. zero mandatory third-party runtime dependencies;
2. Windows, Linux, and macOS compatibility by design;
3. measurable performance rather than assumed performance;
4. security by construction for untrusted input;
5. reusable internals with a narrow public API;
6. clear separation of responsibilities;
7. no speculative abstractions without concrete value;
8. PEP 8, clean code, appropriate typing, maintainable modules, and documented public contracts;
9. concrete differentiation through usability, safety, performance, explainability, composability, or another measurable property;
10. explicit compatibility and migration behavior;
11. benchmarks against comparable libraries, tools, or equivalent stdlib approaches where comparison is meaningful.

External libraries may be used in isolated research and benchmark environments, but they must not become runtime or test requirements of Cereja.

## Core principle

**Use the shortest known path that preserves the required confidence.**

Process intensity must be proportional to uncertainty and impact.

Conceptually:

```text
low uncertainty + low impact
    → direct TDD path

validated prior knowledge exists
    → retrieve smallest relevant guidance → TDD → verify

high uncertainty or high impact
    → investigate → hypothesize → experiment → decide → TDD → verify
```

EDD must never require research, PoCs, ADRs, or extensive documentation for trivial work when the implementation path is already validated.

## Known-path workflow

```text
requirement
  ↓
small sufficient specification
  ↓
retrieve validated knowledge if relevant
  ↓
TDD implementation
  ↓
verification
  ↓
done
```

## Uncertain/high-risk workflow

```text
requirement
  ↓
identify uncertainty
  ↓
map dependencies and impact
  ↓
investigation
  ↓
falsifiable hypotheses
  ↓
rank/select hypotheses
  ↓
isolated PoC / experiment
  ↓
measure / attempt to falsify
  ↓
record evidence
  ↓
design decision
  ↓
TDD implementation
  ↓
verification / benchmark / review
  ↓
knowledge promotion check
```

## Investigation gate

Before solution code is written, investigation is required when a task:

- fails a correctness, security, portability, compatibility, or performance requirement;
- would weaken a non-negotiable constraint;
- depends on an unverified assumption;
- has multiple credible strategies with meaningful trade-offs;
- depends on platform-specific or version-sensitive behavior;
- exposes a benchmark regression whose cause is unknown;
- contains a bug whose causal mechanism is unknown;
- starts accumulating workaround branches or special cases;
- proposes an optimization without evidence of a bottleneck;
- relies on undocumented behavior;
- is about to treat a symptom without establishing root cause.

Investigation should consider, in proportion to relevance:

- project history and existing knowledge;
- public standards;
- primary documentation;
- prior experiments;
- relevant memory and previous decisions;
- correlated project flows and downstream dependencies;
- academic or industry research;
- comparable implementations;
- web research;
- isolated experimental reproduction.

## Hypotheses and proof of concept

A PoC exists to produce knowledge, not production code.

Each meaningful hypothesis should define, before testing:

- claim;
- assumptions;
- expected observations if supported;
- observations that would falsify it;
- minimal isolated experiment;
- measurements needed;
- environmental constraints;
- conclusion: `supported`, `rejected`, or `inconclusive`.

An inconclusive result must not silently become a production assumption.

## Evidence

Valid evidence can include:

- automated tests;
- benchmarks;
- isolated PoCs;
- format specifications;
- official documentation;
- reproducible bug cases;
- standards;
- peer-reviewed or otherwise credible research;
- comparative implementation behavior;
- cross-platform test results.

Verbose prose alone is not evidence.

Important conclusions must preserve provenance to the supporting source, issue, experiment, benchmark, test, or commit.

## Public knowledge reuse

EDD should prefer retrieval over rediscovery.

Before starting a new experiment, consult in order when applicable:

1. validated project knowledge;
2. validated EDD knowledge;
3. primary documentation and standards;
4. credible research;
5. comparable mature implementations;
6. new experiments.

Public information is evidence, not authority. Claims should record scope and freshness where relevant, such as version-sensitive, platform-sensitive, stable, or experimental.

## Knowledge promotion

Not every observation should become permanent guidance.

Promotion model:

```text
raw observation
  ↓
experiment result
  ↓
knowledge candidate
  ↓ corroborated / reused
validated knowledge
  ↓ choose best prevention/reuse mechanism
  ├── project instruction
  ├── pattern
  ├── antipattern
  ├── skill
  ├── automated check / test / lint
  └── retained reference only
```

Promotion rules:

- if behavior can be mechanically enforced, prefer automation over prose;
- if knowledge is project-specific, prefer a project instruction;
- if it requires judgment and generalizes, consider a pattern or skill;
- if it is merely historical context, keep it as a knowledge record;
- if a rule has no demonstrated effect on decisions or behavior, do not promote it.

## Skills and instructions are hypotheses

A skill or instruction is not considered successful merely because it was written.

It should be treated as an intervention hypothesis:

```text
baseline agent behavior without guidance
  ↓
observe failure / inefficiency
  ↓
introduce minimal guidance
  ↓
repeat representative scenarios
  ↓
measure whether behavior improves
  ↓
keep / refine / reject
```

Where possible, test discipline-enforcing skills using pressure scenarios and test technique skills using independent application cases.

## Context efficiency

Context is an engineering resource.

EDD should minimize repeated context consumption while preserving correctness.

Useful conceptual model:

```text
chat/session context      = short-lived cache
project validated knowledge = durable project cache
EDD validated guidance      = reusable methodology cache
web/docs/research            = external knowledge
experiment                   = recomputation when cache misses
```

The goal is not maximum compression. The goal is the smallest sufficient context with a traceable path back to evidence.

## GitHub operating model

GitHub is the operational backbone.

### GitHub Project

Use a lean Project as the global execution view.

Initial fields:

- `Status`
- `Type`
- `Area`
- `Risk`
- `Evidence`
- `Milestone`

Do not add fields merely because GitHub supports them. Promote data to a Project field only when it is repeatedly useful for filtering, coordination, or analysis.

### Issues

Issues are the main operational unit for:

- feature work;
- investigation;
- experiment;
- benchmark;
- bug;
- refactor;
- decision;
- review.

Issues may contain objective, context, dependencies, acceptance criteria, hypotheses, experiment links, conclusions, and knowledge candidates.

### Milestones

Milestones represent meaningful deliverables, not arbitrary sprint cadence.

Example:

- `IO 2.0 — Read-only MVP`
- later milestones only after the current objective is reached.

### Repository responsibilities

`cereja-project/cereja` owns:

- production code;
- feature specifications;
- case-specific experiments;
- case-specific benchmarks;
- feature-specific durable decisions.

A future dedicated EDD repository owns:

- methodology charter;
- protocol;
- templates;
- reusable patterns;
- reusable antipatterns;
- related-work analysis;
- bibliography;
- case-study summaries.

Operational session history should not become permanent methodology content.

## Dedicated methodology repository

A separate repository should be created after this charter is accepted.

Working repository identity:

`evidence-driven-development`

It begins explicitly as experimental, not as a claimed universal framework.

Suggested initial structure:

```text
evidence-driven-development/
├── README.md
├── CHARTER.md
├── PROTOCOL.md
├── references/
│   ├── bibliography.md
│   └── related-work.md
├── templates/
│   ├── investigation.md
│   ├── experiment.md
│   ├── benchmark.md
│   └── decision.md
├── knowledge/
│   ├── patterns/
│   └── antipatterns/
└── case-studies/
    └── 001-cereja-io.md
```

No custom CLI, SDK, agent runtime, or automation framework is required in v0.1. Prove the method before building tooling around it.

## Related work policy

EDD must explicitly study adjacent work before claiming novelty.

Initial map:

- Evidence-Based Software Engineering;
- Design Science Research;
- hypothesis-driven development;
- continuous experimentation;
- Test-Driven Development;
- Architecture Decision Records;
- Spec-Driven Development;
- GitHub Spec Kit;
- OpenSpec;
- agentic software development workflows;
- context engineering and reusable agent instructions.

For each relevant approach, record:

- what problem it solves;
- what EDD reuses;
- what EDD deliberately rejects;
- known limitations;
- relationship to EDD;
- primary references.

The purpose is to avoid rediscovering known ideas and known failure modes.

## Measurement model

EDD success is not measured by lines of code or raw agent speed.

### Software quality

Track where feasible:

- post-implementation defects;
- regressions;
- invariant violations;
- review findings;
- decisions reverted after implementation;
- platform-specific failures.

### Delivery efficiency

Track where feasible:

- end-to-end task completion time;
- investigation time;
- implementation time;
- rework time;
- blocked time attributable to unresolved uncertainty.

### Evidence effectiveness

Track where feasible:

- tasks requiring investigation;
- hypotheses tested;
- hypotheses rejected before production implementation;
- decisions changed by experiments;
- implementations avoided because a hypothesis failed;
- decisions later invalidated despite supporting evidence.

### Knowledge efficiency

Track where feasible:

- knowledge reuse rate;
- reinvention rate;
- repeated research on previously resolved questions;
- context consumed for repeated task classes;
- instruction/skill effectiveness;
- knowledge candidates promoted or rejected;
- loops/repeated reasoning observed during a task.

### Artifact performance

For performance-sensitive features such as `cereja.io`, measure as applicable:

- latency;
- throughput;
- memory consumption;
- allocation behavior;
- bytes read;
- scaling with source size;
- scaling with structural complexity;
- behavior on malformed or adversarial input.

Comparisons must use semantically equivalent workloads.

### Methodology cost

Measure the method itself:

- number of artifacts produced;
- time spent maintaining them;
- repeated document reads;
- steps that did not alter any decision;
- context overhead created by the methodology;
- unnecessary gates or duplicated records.

EDD must be capable of proving that part of EDD is unnecessary and removing it.

## Initial success criteria

Case study #001 is considered useful evidence for EDD if it demonstrates, with traceability:

1. important decisions changed because of investigation or experiment;
2. one or more hypotheses rejected before contaminating production code;
3. validated knowledge reused by later tasks;
4. technical quality of `cereja.io` supported by tests, cross-platform checks, security analysis, and benchmarks where applicable;
5. measurable process overhead that remains proportionate to avoided risk;
6. at least one useful refinement, removal, or simplification of the methodology itself;
7. enough provenance to reconstruct why major decisions were made without relying on chat history.

The first case establishes a baseline. It must not invent arbitrary percentage-improvement claims without comparative data.

## Limits

EDD is NOT:

- a requirement to investigate every task;
- a replacement for engineering judgment;
- a project-management framework;
- a documentation generator;
- formal scientific methodology;
- a guarantee of bug-free software;
- a PoC requirement for trivial work;
- an excuse to block useful agent autonomy;
- a mandate to create skills for every lesson;
- a reason to preserve every intermediate artifact forever.

## Principal risks

### Bureaucratization

The method starts serving itself rather than delivery.

Mitigation: measure overhead and delete steps that repeatedly fail to affect decisions or quality.

### Confirmation bias

Experiments are constructed to justify a preferred implementation.

Mitigation: define falsification conditions before running the PoC.

### Evidence theater

Agents create long reports that look rigorous but demonstrate little.

Mitigation: require traceable, reproducible evidence and distinguish claims from observations.

### Overfitting to `cereja.io`

Rules useful for binary I/O are incorrectly generalized.

Mitigation: only promote project-specific knowledge after demonstrated broader relevance.

### Context explosion

EDD creates so much material that agents become less effective.

Mitigation: lean operational Issues, compact promoted knowledge, retrieval on demand, and explicit context-cost measurement.

### Stale knowledge

Validated guidance remains in use after underlying versions or assumptions change.

Mitigation: preserve provenance, scope, version sensitivity, and revalidation triggers where needed.

### False confidence

Evidence from one platform, workload, dataset, or case is treated as universal.

Mitigation: explicitly record evidence scope and distinguish local validation from general claims.

## Session continuity principle

**A development chat must be disposable.**

The repository and GitHub operational state should be sufficient to determine:

- current objective;
- current task;
- important decisions;
- evidence supporting those decisions;
- open hypotheses;
- blockers;
- next action.

Sessions should load the smallest relevant context by reference rather than replaying entire historical conversations.

## Completion boundary for v0.1

The initial EDD experiment ends when:

- `cereja.io` Read-only MVP reaches its approved acceptance criteria;
- case-study evidence is consolidated;
- EDD metrics and overhead are reviewed;
- patterns/antipatterns and knowledge promotions are audited;
- the protocol is simplified based on evidence;
- a conclusion is recorded: continue, revise substantially, or stop.

Expansion to other domains, additional case studies, tooling, publication, or formal framework status is a separate decision after this boundary.

## Long-term possibility, not current scope

If the first cases support the hypothesis, EDD may later produce:

- a reusable methodology repository;
- tested agent skills and instruction-generation patterns;
- knowledge retrieval conventions;
- GitHub templates/automation;
- additional case studies;
- technical articles;
- an empirical engineering report or research-oriented publication;
- optional tooling to reduce operational cost.

None of these are required to validate v0.1.

## Working thesis

> Software production is becoming cheap. Reliable engineering decisions are not. Evidence-Driven Development explores whether coding agents can become progressively more reliable and context-efficient by making uncertainty, evidence, experimentation, and knowledge reuse first-class parts of the development loop without turning engineering into bureaucracy.
