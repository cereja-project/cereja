# HTTP ownership

Read when changing pool accounting, connection reuse, stream termination, or timeout/cancellation cleanup.

Start at the affected sync or async implementation under `cereja/http/`: `pool.py`, `transport.py`, and `stream.py`. Read `client.py` only if client ownership, redirects, or retries cross the affected boundary. Use `docs/guides/http.md` for public policy and framing contracts.

## Decisions that matter

- Track a slot from reservation through factory creation, checkout, and release/discard. Cereja reserves capacity before creating a connection. Failed or cancelled creation must recover the reservation and wake an eligible waiter. Idle connections at another origin also consume the global limit.
- Separate releasing capacity from making a connection reusable. Determine reuse from validated framing and complete body consumption. An open socket, yielded chunk, or successful status is insufficient. Preserve the guide's early-close behavior and ensure an intermediate redirect response relinquishes ownership before the next acquisition.
- Trace exactly one terminal pool action per checkout. In the async transport, ownership callbacks and stream closed flags can change before awaited pool operations finish. Audit interruptions inside those operations, not only during network reads.
- In particular, inspect `AsyncConnectionPool.discard`: waiting for writer closure and restoring capacity are distinct obligations. A cancellation or close error must not strand accounting. Do not solve this by making every interrupted connection reusable.
- A timeout belongs to a phase. Preserve its HTTP error mapping while propagating external cancellation; do not turn cancellation into a retry. Cleanup can itself suspend or fail. If shielding is necessary, retain and observe the cleanup task and define when ownership ends; shielding alone does not make the caller wait.
- Check pool shutdown against waiting acquisitions and in-flight creation/release. Do not assume closing idle connections proves that checked-out resources have finished.

## Evidence

Locate cases in `tests/http3/test_pool_regressions.py`, `test_async_client.py`, `test_async_timeouts.py`, and `test_sync_client.py`.

For a capacity defect, use a real pool with capacity one, induce the failure, and prove a subsequent acquisition succeeds. For reuse, distinguish reuse after full consumption from replacement after partial consumption or malformed/truncated framing. Use a local server when wire behavior matters; a controlled writer is sufficient to suspend close while retaining real pool accounting. Choose factory failure, pool wait cancellation, body timeout, interrupted discard, or close races according to the changed path.

Python semantics: [task cancellation, timeout, and shield](https://docs.python.org/3.11/library/asyncio-task.html). HTTP policies remain in the Cereja guide.
