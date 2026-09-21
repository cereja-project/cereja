---
name: cereja-stateful-io
description: Diagnose, review, or change Cereja behavior when correctness depends on resource ownership, cleanup, cancellation or timeout, connection reuse or pool accounting, worker coordination or backpressure, SQLite transactions or cross-process locking, or atomic file publication. Applies across Cereja modules, especially HTTP, transfers, context cache, and concurrently. Do not select solely for a module name, async syntax, file access, CLI, docs, exports, pure parsing, or isolated tests; select when the task actually concerns one of these stateful guarantees.
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
