# Context persistence

Read when changing context-cache transaction ownership, locking, storage identity, compatibility, recovery, or persistent publication.

Start with the affected symbols in `cereja/system/_context/cache_db.py` and `cache.py`. Consult `docs/guides/context-cache.md` and the matching cases in `tests/test_context_cache_db.py` or `tests/test_context_cache.py`. Search these large files by symbol or invariant.

## Decisions that matter

- Distinguish the lifecycle of `ContextCacheDatabase` from a SQLite connection's transaction context. The Cereja wrapper closes its connection and releases its path lock; `with connection:` handles a pending transaction but does not close the connection or unconditionally begin a transaction. Identify who begins, commits, rolls back, and closes.
- `commit_scan` materializes its input before opening its publication transaction. Preserve that boundary when iterables or helpers can fail or touch the database. Avoid helper commits that split the scan, association cleanup, and generation update. Inspect stale scan tokens, admission savepoints, and `publish_unchanged_scan` when changing publication.
- Thread affinity, transaction ownership, SQLite writer locking, and the cache path lock solve different problems. Disabling `check_same_thread` does not establish exclusive transaction ownership. Separate `to_thread` calls do not guarantee the same worker. A Python thread lock does not coordinate independent processes.
- The cache already uses WAL, disables automatic checkpoints, and coordinates storage lifecycle through `_CachePathLock` with platform file locks. Preserve the relationship between that lock, SQLite transactions, checkpointing, quota accounting, and sidecar validation. WAL allows one writer at a time; busy timeout is bounded waiting, not a repair strategy. Do not add WAL as a generic optimization or assume WAL means every concurrent opener is admitted.
- Read the guide's conservative refusal/fallback rules before altering recovery. Check application/schema identity, recognized migration, sidecars, file identity before/after open, and source signatures before reusing content. Do not erase unfamiliar storage to make opening succeed. A filesystem signature check is not proof against every hostile swap.
- Separate a committed mutation from later checkpoint, measurement, or lock-restoration failure. Preserve observable errors and attempt independent cleanup obligations even if one fails; do not report complete success or claim that post-commit failure rolled the mutation back.

## Evidence

Use a temporary on-disk SQLite database and reopen through a new connection to establish persistence. For atomic publication, fail after a real mutation and verify previous state after rollback/reopen. Keep real locking for contention tests; use separate processes for process coordination claims. Relevant existing examples include input materialization before transaction, bounded-commit lock restoration, unchanged-scan rollback, concurrent-writer fallback, and post-commit clear failures.

Sources: [Python SQLite transactions and connection lifecycle](https://docs.python.org/3.11/library/sqlite3.html), [SQLite transactions](https://www.sqlite.org/lang_transaction.html), [WAL](https://www.sqlite.org/wal.html), [locking](https://www.sqlite.org/lockingv3.html). Consult [atomic commit assumptions](https://www.sqlite.org/atomiccommit.html) only for durability/recovery changes.
