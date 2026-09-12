# Cereja HTTP 3.0 Zero-Dependency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the legacy private `_requests` subsystem with a zero-dependency public HTTP/1.1 stack that has native synchronous and asynchronous clients, shared semantics, streaming, connection reuse, and a separate download layer.

**Architecture:** Shared immutable models, URL/header handling, request preparation, policies, and errors live under `cereja.http`; network execution is split between stdlib `http.client` for sync and `asyncio` streams for async. `cereja.transfers` composes HTTP streaming with filesystem sinks. Internal consumers are migrated only after the new clients are independently tested.

**Tech Stack:** Python >= 3.11 standard library only: `asyncio`, `http.client`, `socket`, `ssl`, `urllib.parse`, `json`, `dataclasses`, `collections`, `tempfile`, `pathlib`, `unittest`.

**Spec:** `docs/superpowers/specs/2026-09-12-http-3-zero-deps-design.md`

## Global Constraints

- No third-party runtime dependency.
- HTTP/1.1 only for the first implementation.
- Sync client must perform native blocking I/O; async client must perform native asyncio socket I/O.
- No hidden threads/event loops/sockets on import.
- Shared logic must not depend on sync or async execution.
- HTTP must not depend on `cereja.display`, `cereja.file`, or `cereja.transfers`.
- `docs/superpowers/specs/...` and this plan are temporary and must be removed before the final merge PR.

---

### Task 1: Shared HTTP Contracts

**Files:**
- Create: `cereja/http/__init__.py`
- Create: `cereja/http/errors.py`
- Create: `cereja/http/headers.py`
- Create: `cereja/http/url.py`
- Create: `cereja/http/models.py`
- Create: `cereja/http/_core/encoding.py`
- Create: `cereja/http/_core/prepare.py`
- Test: `tests/http/test_core.py`

**Interfaces:**
- Produces `URL`, `Headers`, `Timeout`, `Request`, `ResponseInfo`, `Response`, `prepare_request()` and the public HTTP error hierarchy.

- [ ] Write failing tests proving URL/query handling, IPv6/ports, repeated/case-insensitive headers, CR/LF rejection, raw-byte preservation, falsy JSON preservation, mutually exclusive body arguments, response decoding, and `raise_for_status()`.
- [ ] Run `python -m unittest tests.http.test_core -v` and verify failures are due to missing new API.
- [ ] Implement the minimum shared contracts with no I/O side effects.
- [ ] Re-run the test module and require zero failures.
- [ ] Commit `feat(http): add shared request and response contracts`.

### Task 2: Synchronous Client and Streaming

**Files:**
- Create: `cereja/http/sync/__init__.py`
- Create: `cereja/http/sync/pool.py`
- Create: `cereja/http/sync/stream.py`
- Create: `cereja/http/sync/transport.py`
- Create: `cereja/http/sync/client.py`
- Test: `tests/http/test_sync_client.py`
- Test support: `tests/http/_server.py`

**Interfaces:**
- Produces `Client`, `StreamResponse`, `SyncByteStream`; consumes Task 1 contracts.

- [ ] Add a local socket HTTP/1.1 test server supporting fixed length, chunked, keep-alive, connection close, redirects, delayed bodies, malformed/truncated bodies, and request echoing.
- [ ] Write failing sync integration tests for GET/POST bytes+JSON, connection reuse, streaming, early close, body limits, redirects, read timeout, truncated body and deterministic close.
- [ ] Run `python -m unittest tests.http.test_sync_client -v` and verify expected failures.
- [ ] Implement a bounded `http.client` connection pool keyed by origin and TLS identity; never return unsafe connections to the pool.
- [ ] Implement `Client.request/get/post/put/patch/delete/head`, materialized response handling, streaming, redirects and phase timeouts.
- [ ] Re-run sync tests and require zero failures.
- [ ] Commit `feat(http): add native synchronous HTTP client`.

### Task 3: Asynchronous HTTP/1.1 Transport

**Files:**
- Create: `cereja/http/async_/__init__.py`
- Create: `cereja/http/async_/pool.py`
- Create: `cereja/http/async_/stream.py`
- Create: `cereja/http/async_/transport.py`
- Create: `cereja/http/async_/client.py`
- Test: `tests/http/test_async_client.py`

**Interfaces:**
- Produces `AsyncClient`, `AsyncStreamResponse`, `AsyncByteStream`; consumes the same Task 1 contracts.

- [ ] Write failing async integration tests using `unittest.IsolatedAsyncioTestCase` for fixed/chunked bodies, keep-alive reuse, pool bounds, streaming, early close, read/pool timeout, redirects, truncated bodies and cancellation cleanup.
- [ ] Run `python -m unittest tests.http.test_async_client -v` and verify expected failures.
- [ ] Implement HTTP/1.1 request serialization and status/header parsing over `asyncio.open_connection()` with TLS from `ssl.create_default_context()`.
- [ ] Implement fixed-length, chunked and connection-close response framing with strict EOF/protocol checks.
- [ ] Implement bounded origin pools, cancellation-safe resource release/discard, streaming and deterministic `aclose()`.
- [ ] Re-run async tests and require zero failures.
- [ ] Commit `feat(http): add native asynchronous HTTP client`.

### Task 4: Shared Redirect, Retry and Timeout Policies

**Files:**
- Create: `cereja/http/_core/policies.py`
- Modify: `cereja/http/sync/client.py`
- Modify: `cereja/http/async_/client.py`
- Test: `tests/http/test_policies.py`

**Interfaces:**
- Produces immutable `RetryPolicy`, redirect decision helpers, replayability checks and shared timeout normalization.

- [ ] Write failing policy tests for hop limits, cross-origin authorization stripping, method/body handling for redirect status codes, idempotency, replayability, retryable transport categories and cancellation exclusion.
- [ ] Run `python -m unittest tests.http.test_policies -v` and verify expected failures.
- [ ] Implement pure policy decisions; sync sleeps with `time.sleep`, async sleeps with `asyncio.sleep`.
- [ ] Integrate clients without duplicating decision logic.
- [ ] Run all `tests.http` modules and require zero failures.
- [ ] Commit `feat(http): share redirect retry and timeout policies`.

### Task 5: Transfer Layer

**Files:**
- Create: `cereja/transfers/__init__.py`
- Create: `cereja/transfers/models.py`
- Create: `cereja/transfers/sinks.py`
- Create: `cereja/transfers/download.py`
- Test: `tests/transfers/test_download.py`

**Interfaces:**
- Produces `DownloadResult`, `TransferProgress`, `download()` and `async_download()`; consumes HTTP streaming without importing display or legacy FileIO.

- [ ] Write failing tests for atomic temp-file completion, cleanup on failure, bounded chunks, progress callbacks, sync and async download paths and non-blocking async filesystem boundary.
- [ ] Run `python -m unittest tests.transfers.test_download -v` and verify expected failures.
- [ ] Implement sync sink writes directly and async sink writes via `asyncio.to_thread()` only at filesystem boundaries.
- [ ] Re-run transfer tests and require zero failures.
- [ ] Commit `feat(transfers): separate HTTP downloads from transport`.

### Task 6: Public Lazy API and Internal Consumer Migration

**Files:**
- Modify: `cereja/_exports.py`
- Regenerate: relevant `__init__.pyi` files using `tools/generate_export_stubs.py`
- Modify: `cereja/scraping/b3.py`
- Modify: `cereja/file/_io.py`
- Test: `tests/http/test_imports.py`
- Test: existing scraping/file tests as applicable

**Interfaces:**
- Public API: `from cereja.http import Client, AsyncClient, get, post, ...`; internal consumers receive or create the new client explicitly.

- [ ] Write failing import-isolation tests proving `cereja.http` loads without sockets/threads/event loops and root import stays lazy.
- [ ] Add explicit lazy exports and typing declarations.
- [ ] Migrate B3 and URL-based file loaders away from `_requests`, preferring dependency injection where ownership matters.
- [ ] Run import tests plus affected existing tests.
- [ ] Commit `refactor: migrate internal HTTP consumers to cereja.http`.

### Task 7: Validation, Documentation and Temporary-Artifact Removal

**Files:**
- Create: `docs/guides/http.md`
- Modify: `docs/index.md` / API index as needed
- Create: `benchmarks/http.py`
- Delete before PR: `docs/superpowers/specs/2026-09-12-http-3-zero-deps-design.md`
- Delete before PR: `docs/superpowers/plans/2026-09-12-http-3-zero-deps.md`

**Interfaces:**
- Produces user documentation, benchmark evidence and a merge branch with no Superpowers planning artifacts.

- [ ] Document resource ownership, sync/async choice, streaming, downloads, timeout/retry semantics and HTTP/1.1 scope.
- [ ] Add benchmark cases for legacy `_requests`, new sync client, and async controlled concurrency, measuring latency/throughput/memory without correctness thresholds.
- [ ] Run `python -m unittest discover -s tests -v` plus configured lint/static/export checks.
- [ ] Run wheel/sdist and documentation validation used by CI.
- [ ] Remove both temporary Superpowers documents and verify `git diff master...HEAD -- docs/superpowers` is empty in the final PR content.
- [ ] Open a draft PR with validation evidence; do not merge, tag, or release.
