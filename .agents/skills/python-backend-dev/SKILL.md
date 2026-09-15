---
name: python-backend-dev
description: Design, implement, diagnose, or review Python backend APIs, services, persistence, and background jobs, including their integration tests. Preserve the project's stack and constraints. Generic Python, standalone test organization, and documentation edits do not by themselves trigger this skill.
---

# Python Backend Development

Use backend-specific evidence to choose the smallest correct change. This skill
adds technical decision criteria to Norte's development workflows; it does not
replace their investigation, TDD, review, or verification gates.

## Establish the task boundary

Read the request, relevant entry point, dependency/version declarations, and nearby
tests before selecting an approach. Distinguish implementation from diagnosis or
review: a request for findings does not authorize applying a fix.

Preserve explicit requirements, public contracts, supported Python versions and
existing framework, sync/async model, test runner, and layout. If requirements
conflict with the existing implementation, explain the conflict before choosing a
breaking change. Do not migrate a project just to match examples in this skill.

For a new service, choose dependencies from actual transport, persistence,
deployment and operational needs. No framework, ORM, cache, directory layout or
dependency-free mode is a universal default. Ask only when an unresolved choice
materially changes the requested result.

## Load relevant guidance

Read the selected reference before making decisions in its area. Multiple may be
needed, but do not load all references automatically.

- [Modern stack](references/modern-stack.md): when changing FastAPI, Pydantic v2,
  or SQLAlchemy 2.x integrations. Examples do not prescribe these tools for Flask,
  Django or other stacks; inspect their existing conventions and installed-version
  documentation instead.
- [Standard library](references/standard-library.md): when external dependencies
  are prohibited or the affected implementation uses standard-library facilities.
- [Persistence and concurrency](references/persistence-concurrency.md): when
  changing database transactions, concurrent I/O, job delivery, queries or caching;
  also for evidence-based performance diagnosis.
- [Backend tests](references/backend-testing.md): when writing or assessing tests
  of backend behavior, particularly transport, storage or concurrency semantics.

## Decisions that must survive implementation

- Keep transport validation, business rules and storage responsibilities clear
  within the existing design. Add layers or shared abstractions only for concrete
  complexity or reuse, not to satisfy a template.
- Preserve status codes, exposed fields, error behavior, stored data and transaction
  boundaries unless changing them is part of the request. Validate untrusted input
  at the boundary; type annotations alone do not enforce runtime contracts.
- Parameterize SQL values. Keep credentials and private fields out of responses,
  logs and test evidence. For security-sensitive tokens use an established secure
  API; use library password hashing/encryption rather than inventing primitives.
  Follow the security notes in the standard-library reference when using its APIs.
- Bound expensive work according to the actual contract: payload sizes, list
  results, external-call timeouts and resource lifetimes. Preserve existing limits;
  do not silently break a public endpoint by introducing a new pagination contract.
- Match execution to dependencies: synchronous I/O is valid in a synchronous
  stack; blocking I/O must not stall an async event loop. Define ownership and
  cleanup for connections, sessions and background work.
- Measure a suspected bottleneck before adding caching, pooling changes, indexes
  or concurrency. For diagnosis-only requests, report evidence and a proposed next
  step without implementing it.

## Verification and handoff

Use the active Norte workflow for implementation sequencing and independent review.
If used outside Norte, demonstrate a regression before fixing it, run the affected
checks, and inspect the diff. Select tests that prove the backend semantics at risk;
do not substitute mocked behavior for database or transport evidence.

Report the resulting behavior, executed checks, and material limitations concisely.
Distinguish local tests from deployment verification, and static review from observed
runtime behavior. Missing infrastructure is an unverified condition, not a passing
test. Do not claim that this skill's own effectiveness is proven by package checks.
