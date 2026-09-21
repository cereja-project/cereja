# Async file publication

Read when changing transfer ownership, sink commit/abort, atomic publication, or blocking filesystem work in async code.

Start with `cereja/transfers/download.py`, `sinks.py`, and `tests/transfers/test_download.py`; consult the download sections of `docs/guides/http.md`. Inspect CLI code only when overwrite policy or command behavior is involved.

## Decisions that matter

- Separate borrowed clients from clients created by the transfer. The transfer owns its response and sink; an injected client has a different lifetime. Follow failures in opening the stream or sink as well as failures after data arrives.
- Native async HTTP does not make file operations nonblocking. Cereja offloads sink open/write/commit/abort with `asyncio.to_thread`. Awaiting each call orders normal execution, but cancelling that await does not stop a running worker.
- Before aborting, closing, or removing a file, account for any still-running open, write, or commit. Otherwise cleanup can finish before a late open creates a partial file, or race a write/replace. Define ownership until the worker finishes and propagate cancellation after the required cleanup. Do not prescribe a new executor or lock without identifying the race it resolves.
- Treat replacement as the publication point. Decide what cancellation means before replacement and after publication has already occurred; do not promise rollback of an already published destination. If shielding is used, keep the task observable and coordinate its completion, including repeated cancellation.
- The current sink creates a temporary file in the destination directory, flushes, fsyncs and closes it, then calls `os.replace`. Preserve the old destination on pre-publication failure and remove only the temporary artifact owned by this operation.
- Atomic visibility, no-overwrite policy, and crash durability are separate guarantees. The sink replaces existing files; a CLI existence check is a separate policy and does not prove race-free no-clobber behavior. File fsync plus replacement, without an established directory/platform durability protocol, does not establish full crash durability.

## Evidence

Use a real temporary directory with an existing destination. Inject a failure after an actual first write and verify old bytes and absence of owned partial files. For cancellation, block a real sink operation with events, cancel its waiter, then release the worker and check that no file appears or changes after declared cleanup. Exercise commit failure or cancellation around publication only when that boundary changes. Check event-loop responsiveness with a coordinated blocking operation, not elapsed-time guesses.

Sources: [running futures cannot be cancelled](https://docs.python.org/3.11/library/concurrent.futures.html#concurrent.futures.Future.cancel), [to_thread](https://docs.python.org/3.11/library/asyncio-task.html#asyncio.to_thread), [temporary files](https://docs.python.org/3.11/library/tempfile.html), [replace and fsync](https://docs.python.org/3.11/library/os.html#os.replace).
