# Persistence, concurrency and performance

## Correctness first

Define the transaction owner and ensure related writes commit or roll back together.
Test failures after the first write against a real database. Preserve driver
transaction mode and avoid commits inside helpers owned by an outer transaction.
Handle invalid inputs without leaving partial state or an open transaction.

Own and close connections/sessions explicitly. Do not share mutable transaction
state across concurrent tasks. Before offloading work to a thread, check the
connection's thread-affinity and lifetime constraints.

`asyncio.to_thread` is useful for blocking I/O; it is not a general speedup for
CPU-bound Python. Cancelling the awaiting coroutine does not guarantee that a
running worker thread stops. Account for cleanup, timeouts and duplicate effects.
For background jobs with retries, define idempotency and failure visibility against
the selected queue's actual delivery contract.

## Optimize a demonstrated bottleneck

Measure query counts, query plans or bounded timing with representative data.
Change one relevant factor and preserve response/transaction semantics. For N+1
queries, evaluate aggregation, batching or loading strategies against the result
shape; do not prescribe one ORM loading strategy universally.

SQLite WAL can improve reader/writer concurrency, but still permits only one writer
at a time and has filesystem/deployment constraints. Do not enable it as a blanket
rule. Tune pools only for a supported driver and measured workload; pool knobs are
not portable across every database configuration.

Introduce caching only with a demonstrated benefit, an acceptable staleness budget,
invalidation behavior and a memory bound. A finite TTL is one mechanism, not a
requirement for every Redis key or durable state. Diagnose before provisioning Redis.

## Sources and applicability

Checked 2026-09-09. Python guidance uses 3.14 documentation (`to_thread` exists from
3.9); SQLAlchemy guidance targets 2.x. Validate runtime versions and deployment
constraints before applying API-specific changes. Cache/job criteria above are
engineering decision rules, not guarantees from a particular provider.

- [Python thread offloading](https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread)
- [SQLite WAL concurrency and limitations](https://www.sqlite.org/wal.html)
- [SQLAlchemy async session concurrency](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Python sqlite3 transaction control](https://docs.python.org/3/library/sqlite3.html#transaction-control)
