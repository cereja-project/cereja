---
name: cereja-stateful-io
description: Diagnose, refactor, review, or change Cereja code when correctness depends on resource ownership or cleanup, cancellation or timeouts, connection reuse or pool accounting, worker coordination or backpressure, SQLite transactions or cross-process locking, or atomic file publication. Use especially for HTTP, transfers, context cache, and concurrently. Do not use for ordinary module edits, pure parsing, CLI/docs/exports, or tests unrelated to these stateful guarantees.
---

# Cereja stateful I/O

Use this skill for the state transition at risk, not for every edit in a listed package. Repository paths below are relative to the Cereja root. Recheck the affected implementation and tests; observations in references are navigation aids, not permanent API contracts.

Identify who owns the resource, where ownership transfers, what makes the operation complete or committed, and who handles failure before and after that point. Follow the affected transition through success, timeout, cancellation, and partial failure. Do not equate a flag change with completed cleanup.

Read only the relevant reference:

- [HTTP ownership](references/http-ownership.md): pool capacity, stream completion, reuse, transport cleanup, or lifecycle across redirects/retries.
- [Async file publication](references/async-file-publication.md): transfer sink lifecycle, atomic commit/abort, or filesystem work crossing an async/thread boundary.
- [Context persistence](references/context-persistence.md): cache transactions, storage identity, cross-process coordination, recovery, or compatibility.
- [Worker coordination](references/worker-coordination.md): queue drain, thread ownership, shutdown, result delivery, or backpressure.

For a task crossing boundaries, read the references for both sides. For another Cereja component, use the reference for the same mechanism only after locating its actual ownership and persistence contract; do not import HTTP or cache policies into it.

Prefer the simplest solution that preserves the required concurrency, lifecycle, atomicity, and persistence guarantees. Add locks, queues, threads, caches, WAL, pooling, retries, background services, or policy layers only for a concrete requirement or measured bottleneck. Simplicity must not remove necessary cleanup, cancellation propagation, or atomic publication.

Choose evidence for the transition at risk. Keep the real pool, queue, filesystem, database, or process boundary when it is the behavior under test. Controlled failure injection is useful when it preserves that mechanism. Use events or conditions to establish ordering; deadlines bound a broken test rather than substitute for synchronization. Do not expand a small change into every scenario in every reference.

## Refactoring existing stateful code

Preserve externally observable contracts and safety/compatibility invariants; do not assume existing internal structure or historical complexity is required architecture. Characterize accidental behavior to understand the impact, not to declare every defect a contract.

When the requested change exposes a structural obstacle to a stateful guarantee, consider a focused refactoring before or alongside the fix. Look for:

- ownership or state transitions scattered across functions, and duplicated cleanup or commit/abort paths;
- shared mutable state or broad lock scopes whose protected invariant is unclear;
- implicit transaction ownership or methods mixing persistence, transformation, and coordination;
- mixed pool, transport, and retry responsibilities, or accidental sync/async divergence;
- worker lifecycles that are difficult to observe or terminate, and legacy names that obscure actual execution;
- large functions whose failure paths cannot be traced or tested reliably.

These are investigation signals, not automatic reasons to extract classes, merge sync/async implementations, rename public APIs, or rewrite a subsystem. For example, MultiProcess's thread-based behavior warrants explicit reasoning about thread ownership, not an incidental breaking rename.

Before changing structure, identify the concrete obstructed guarantee, stable behavior, and affected ownership boundaries. Locate focused tests or add characterization evidence where behavior is unclear. Keep structural and behavioral changes distinguishable where practical, without requiring a separate commit or workflow.

Choose an incremental change that reduces ownership ambiguity, hidden transitions, or duplicated failure handling. Recheck the affected concurrency, persistence, and failure semantics using the relevant reference. A smaller diff is not preferable if it leaves correctness dependent on an unsafe structure.

A larger refactoring needs evidence that the current structure materially prevents correctness, safe evolution, meaningful testing, or the requested capability. Explain that connection and the affected scope. Keep unrelated debt separate unless it blocks the result or makes the change unsafe.
