# Worker coordination

Read when changing queue drain, backpressure, worker ownership, shutdown, failure delivery, or result ordering.

Start with the affected class in `cereja/concurrently/process.py` and `tests/testconcurrently_process.py`. For sync/async adapters, inspect the specific adapter in `cereja/concurrently/_concurrence.py` before applying thread or event-loop assumptions.

## Decisions that matter

- `MultiProcess` uses native threads. Its name and `ChildProcessError` do not imply process isolation. Track active-thread accounting, failed thread creation, callbacks, and the caller's responsibility for waiting.
- `WorkerQueue` has a daemon dispatcher that starts worker threads. Its input queue acknowledges dispatch with `task_done`; that does not establish completion of the dispatched task. Inspect `_worker`, `_get_response`, and `__exit__` together for drain changes. Queue emptiness, queue join, active-worker completion, result consumption, and service-thread shutdown are distinct conditions.
- Identify who stops and joins each thread. A daemon service is not a cleanup guarantee. For shutdown changes, determine treatment of accepted work, blocked producers/consumers, callbacks, and failures before choosing a sentinel, event, or other mechanism. Avoid joining the current thread or waiting while holding a lock needed by the worker.
- Distinguish input ordering, completion ordering, callback delivery, and ordering among currently available results. A priority queue cannot return an earlier result that has not arrived. Preserve legacy aliases and actual behavior through the repository's public-API rules.
- Do not assume worker exceptions reach the caller: `MultiProcess` records/logs failures, and `Processor` tracks failed inputs and has a result-service thread. Inspect those paths before changing propagation. Specify any intended public behavior change rather than silently converting partial results into a raised exception.
- For `Processor`, count submitted-but-unfinished work separately from queued completions and completed callbacks. Check cleanup when input iteration fails. More threads, polling, or an extra queue is not evidence of better throughput or bounded memory.

## Evidence

Coordinate a worker and caller with events so the assertion occurs while work is known to be unfinished. Test the exact drain/shutdown promise, then release and join test-owned workers. Induce worker and callback failures separately when relevant. Verify capacity is recovered after failed worker creation. To test ordering, complete inputs out of order deliberately; to test backpressure, hold completion and observe the producer's admission boundary. Keep the actual queue/threads or executor under test.

Python baseline sources: [queue completion accounting](https://docs.python.org/3.11/library/queue.html), [thread lifecycle and conditions](https://docs.python.org/3.11/library/threading.html), [executor shutdown and deadlocks](https://docs.python.org/3.11/library/concurrent.futures.html). Do not assume newer queue shutdown APIs exist in Python 3.11.
