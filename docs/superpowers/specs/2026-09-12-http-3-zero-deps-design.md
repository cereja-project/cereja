# Cereja HTTP 3.0 — Zero-Dependency Design

## Status

Approved architectural direction for Cereja 3.0. This document defines the target design before implementation.

## Goal

Replace the legacy `cereja._requests` subsystem with a public, zero-dependency HTTP stack that provides native synchronous and asynchronous clients, shared protocol-independent rules, explicit resource ownership, streaming, connection reuse, and a separate transfer layer for downloads.

## Non-goals

The first implementation does not target HTTP/2, HTTP/3, WebSocket, SOCKS, digest authentication, advanced proxy negotiation, resumable downloads, segmented downloads, or a general transport plugin ecosystem.

## Constraints

- Python >= 3.11.
- No mandatory or optional third-party runtime dependency for HTTP.
- Standard library only: `asyncio`, `http.client`, `socket`, `ssl`, `urllib.parse`, `json`, `dataclasses`, `collections`, and related stdlib modules.
- Sync and async APIs must be native. The sync client must not be implemented by running the async client through `run_sync`; the async client must not be implemented by wrapping the sync client in `asyncio.to_thread` for normal network I/O.
- Shared code must contain protocol-independent preparation, validation, models, encoding, header handling, retry decisions, redirect decisions, and error classification.
- I/O execution, stream consumption, connection pooling, and shutdown remain runtime-specific.
- Importing `cereja.http` must not open sockets, start threads, create event loops, or import unrelated Cereja domains.
- Legacy `cereja._requests` compatibility is not a design requirement for Cereja 3.0.

## Package boundaries

```text
cereja/
├── http/
│   ├── __init__.py
│   ├── models.py
│   ├── headers.py
│   ├── url.py
│   ├── errors.py
│   ├── _core/
│   │   ├── prepare.py
│   │   ├── encoding.py
│   │   └── policies.py
│   ├── sync/
│   │   ├── client.py
│   │   ├── transport.py
│   │   ├── pool.py
│   │   └── stream.py
│   └── async_/
│       ├── client.py
│       ├── transport.py
│       ├── pool.py
│       └── stream.py
└── transfers/
    ├── __init__.py
    ├── models.py
    ├── download.py
    └── sinks.py
```

`async_` is used internally to avoid the reserved keyword while the public API remains `cereja.http.AsyncClient`.

A global `cereja.core` package is intentionally avoided. Shared code stays local to `cereja.http._core` until another subsystem has a concrete need for the exact same semantics.

## Public API

The principal API is instance-based so callers can reuse connections and control resource lifetime.

```python
from cereja.http import Client

with Client(timeout=10.0, max_connections=20) as client:
    response = client.get(
        "https://api.example.com/users",
        params={"page": 1},
    )
    response.raise_for_status()
    data = response.json()
```

```python
from cereja.http import AsyncClient

async with AsyncClient(timeout=10.0, max_connections=20) as client:
    response = await client.get(
        "https://api.example.com/users",
        params={"page": 1},
    )
    response.raise_for_status()
    data = response.json()
```

Convenience functions may exist:

```python
from cereja.http import get
response = get("https://example.com")
```

They create a short-lived client and therefore are not the recommended path for repeated requests.

## Core data model

`Request` is a description of an operation. It performs no network I/O and owns no thread, socket, event loop, or connection.

```python
@dataclass(frozen=True, slots=True)
class Request:
    method: str
    url: URL
    headers: Headers
    content: bytes | None
```

`ResponseInfo` stores immutable response metadata that can be shared by materialized and streaming response types.

```python
@dataclass(frozen=True, slots=True)
class ResponseInfo:
    status_code: int
    reason: str
    headers: Headers
    url: URL
    http_version: str
```

`Response` represents a fully materialized body:

```text
status_code
reason
headers
url
content -> bytes
text -> str
json() -> decoded JSON value
raise_for_status() -> None or HTTPStatusError
```

Accessing metadata or body properties must never initiate hidden network work.

## URLs

URL parsing uses `urllib.parse` rather than manual string rewriting.

The URL abstraction must preserve:

- scheme;
- host;
- explicit port;
- path;
- query string;
- percent-encoded components;
- IPv6 literals.

HTTP requests require `http` or `https`. Relative URLs are accepted only when a client has a configured `base_url`.

## Headers

`Headers` provides case-insensitive lookup while preserving original field values and repeated fields where HTTP semantics permit them.

The implementation must not normalize headers into a structure that loses multiple values such as `Set-Cookie`.

Header validation rejects embedded CR/LF values to prevent request smuggling/header injection through the public API.

## Request bodies

The client exposes distinct inputs:

- `params=` for URL query parameters;
- `json=` for JSON encoding;
- `data=` for form-style mappings or explicitly supported scalar form values;
- `content=` for bytes-like or string content.

Mutually exclusive body forms are rejected.

Falsy values are data, not absence. The following must remain distinct:

```text
no body
JSON null
JSON false
JSON 0
JSON {}
bytes b""
```

Raw bytes must remain byte-for-byte identical. The implementation must never serialize bytes using `str(value).encode()`.

## Synchronous transport

The sync implementation is based on stdlib `http.client.HTTPConnection` and `http.client.HTTPSConnection`, with explicit connection reuse managed by Cereja.

The sync pool is keyed at minimum by scheme, normalized host, port, and TLS configuration identity.

A pooled connection is returned to the pool only when the response body has been consumed or the stream has been explicitly closed in a state that safely permits reuse. Broken, timed-out, protocol-invalid, or ambiguously terminated connections are discarded.

The client owns its pool. `Client.close()` and context-manager exit close all pooled connections deterministically.

## Asynchronous transport

The async implementation uses `asyncio.open_connection()` and asyncio stream readers/writers.

The first supported wire protocol is HTTP/1.1. The async transport implements:

- request line and headers;
- TLS through an `ssl.SSLContext`;
- fixed-length request and response bodies;
- `Transfer-Encoding: chunked` response decoding;
- keep-alive reuse;
- connection-close delimited bodies where valid;
- connection pooling;
- cancellation-safe cleanup;
- bounded acquisition of connections.

A cancelled operation must release or discard every owned resource and re-raise `asyncio.CancelledError`. Cancellation must never be converted into retryable transport failure.

## Streams

Sync and async streaming have distinct runtime interfaces.

```text
SyncByteStream
- read(size: int = -1) -> bytes
- iter_bytes(chunk_size: int) -> Iterator[bytes]
- close() -> None

AsyncByteStream
- read(size: int = -1) -> Awaitable[bytes]
- aiter_bytes(chunk_size: int) -> AsyncIterator[bytes]
- aclose() -> Awaitable[None]
```

A streaming response exposes metadata immediately after headers are received but does not materialize the full body.

Closing a stream before complete consumption discards the underlying connection unless the transport can prove safe reuse.

## Timeouts

Timeouts are modeled explicitly instead of one ambiguous scalar internally:

```text
connect
read
write
pool
```

The public API may accept a scalar as shorthand that populates all four values.

A future total-operation deadline may be added separately; it must not be represented as one of the phase timeouts.

## Redirects

Redirect behavior is a core policy shared by sync and async clients.

Initial implementation supports standard HTTP redirect status codes with an explicit maximum hop count.

The policy determines method/body preservation according to HTTP semantics. A redirect that requires replaying a non-replayable body fails rather than silently resending corrupted or incomplete data.

Authorization and other sensitive headers are not forwarded across origins unless explicitly allowed by policy.

## Retry policy

Retries are disabled by default.

When enabled, the shared policy decides whether an operation is retryable based on:

- HTTP method/idempotency;
- failure category;
- attempt count;
- remaining configured policy budget;
- whether the request body is replayable.

Cancellation is never retried. HTTP status responses are not transport failures unless a configured policy explicitly marks a status as retryable.

The sync client waits with blocking sleep. The async client waits with `asyncio.sleep()`.

## Error model

The public hierarchy separates categories that callers need to handle differently:

```text
HTTPError
├── RequestError
│   ├── ConnectError
│   ├── TimeoutError
│   │   ├── ConnectTimeout
│   │   ├── ReadTimeout
│   │   ├── WriteTimeout
│   │   └── PoolTimeout
│   ├── ProtocolError
│   └── TLSFailure
├── HTTPStatusError
├── DecodeError
└── BodyLimitExceeded
```

Underlying exceptions are preserved through exception chaining.

A valid HTTP 404 response is represented as a response and becomes an exception only when `raise_for_status()` is called.

## Memory and body limits

Materialized responses have a configurable maximum body size. Exceeding the limit raises `BodyLimitExceeded` and discards the connection when safe reuse cannot be guaranteed.

Streaming does not accumulate the whole response in memory.

Unknown or missing `Content-Length` never implies that the implementation should blindly read an unlimited body into memory.

## Transfers

File download is removed from the HTTP response implementation and placed in `cereja.transfers`.

`transfers` depends on `cereja.http`; `cereja.http` must not depend on `cereja.transfers`, `cereja.display`, or `cereja.file`.

The transfer flow is:

```text
open HTTP stream
→ validate status/limits
→ consume bounded chunks
→ write destination/temp file
→ finalize destination
→ return DownloadResult
```

Progress is represented as callback/event data. Terminal rendering is an optional consumer outside the HTTP core.

Async downloads must not perform unbounded blocking filesystem writes on the event-loop thread. The implementation may use `asyncio.to_thread()` specifically at the filesystem boundary because local file APIs are synchronous; this does not make the HTTP transport thread-backed.

## Internal consumers

Existing consumers such as `cereja.scraping.b3` and URL-based file loaders must stop depending on the private legacy `_requests` package.

Where practical, services receive a client instance rather than constructing hidden global clients. This enables connection reuse, deterministic tests, and explicit lifetime ownership.

## Legacy package

`cereja._requests` is not the target API for Cereja 3.0.

Migration may proceed by building `cereja.http` independently, migrating internal consumers, then removing `_requests` once no 3.0 code depends on it. A compatibility shim is optional and must not constrain the new design.

## Connection ownership

Whoever creates a client owns and closes it.

A component that receives an existing client as a dependency must not close it unless ownership was explicitly transferred.

Sync and async clients may share immutable configuration objects but must not share live sockets, locks, pools, or event-loop-bound resources.

## Concurrency limits

Connection-pool size and application work admission are separate concerns.

The HTTP client bounds live connections through `max_connections`. Higher-level code that creates many operations concurrently is responsible for its own work queue/semaphore unless a dedicated batch API is added later.

The HTTP package must not create an unbounded task queue internally.

## TLS

HTTPS verifies certificates and hostnames by default using `ssl.create_default_context()` semantics.

Verification can be configured explicitly through supported stdlib SSL configuration, but insecure verification is never enabled implicitly.

## Logging and sensitive information

The HTTP core does not print.

Diagnostic logging must avoid request bodies and redact authorization/cookie credentials by default.

## HTTP/1.1 scope

The async parser and transport must correctly handle at least:

- `Content-Length`;
- chunked transfer coding;
- responses with no body by method/status semantics;
- connection-close delimited bodies where permitted;
- informational responses needed to reach the final response;
- malformed status lines/headers as protocol errors;
- premature EOF as protocol error where a body length was promised.

HTTP/2 and HTTP/3 are explicitly outside the first implementation.

## Testing strategy

Unit tests cover pure shared logic without network mocks that pretend to prove wire semantics.

Integration tests use local controlled servers and exercise real sockets for both clients.

Required scenarios include:

- request preparation and byte preservation;
- URL/query encoding;
- case-insensitive and repeated headers;
- JSON falsy values;
- fixed-length responses;
- chunked responses;
- missing `Content-Length`;
- connection reuse;
- server-requested connection close;
- truncated bodies;
- connect/read/pool timeouts;
- redirects and redirect loops;
- retry policy decisions;
- cancellation during connect/read in async mode;
- early stream close;
- body-size limit;
- TLS verification against controlled test certificates where practical;
- no sockets/threads/event loops as import side effects.

Equivalent sync and async scenarios should assert the same response/error semantics when the runtime behavior is conceptually identical.

## Performance validation

Performance work compares:

1. legacy `_requests` where meaningful;
2. new `Client`;
3. new `AsyncClient` under controlled concurrency.

Measurements include median latency, high-percentile latency, throughput, memory, live connection count, and event-loop responsiveness for async workloads.

Performance numbers are evidence, not hard-coded universal thresholds. Deterministic regression tests enforce connection reuse, bounded memory, bounded concurrency, and absence of hidden threads.

## Implementation sequence

1. Shared models, headers, URL parsing, request preparation, and error hierarchy.
2. Sync HTTP/1.1 client with deterministic connection reuse and streaming.
3. Async HTTP/1.1 client using asyncio streams and equivalent contracts.
4. Redirect, timeout, body-limit, and retry policies shared by both clients.
5. Transfer layer for file downloads and progress events.
6. Migration of internal consumers away from `_requests`.
7. Benchmarks, documentation, public lazy exports, and removal or isolation of the legacy package.

Each stage must be independently testable and must not require later stages to validate its own core behavior.

## Acceptance criteria

The design is ready for Cereja 3.0 when all of the following are true:

- `cereja.http` has zero third-party runtime dependencies.
- Sync network I/O is genuinely synchronous; async network I/O is genuinely asyncio-based.
- Shared request/response semantics are not duplicated between runtime implementations.
- HTTP imports have no execution side effects.
- Connections are reused safely and closed deterministically.
- Streaming does not require materializing full bodies.
- Cancellation and failures do not leak sockets or pool permits.
- Downloads are outside the HTTP core.
- Existing internal consumers no longer require `cereja._requests`.
- The complete test suite passes on the supported Python versions and operating systems.
- Benchmarks demonstrate the costs and gains of the new implementation without relying on timing thresholds as correctness tests.
