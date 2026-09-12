# HTTP

Cereja provides zero-dependency HTTP/1.1 clients using only the Python standard library.
The synchronous and asynchronous clients share request, response, URL, header, timeout,
redirect, retry, and error semantics, while network I/O remains native to each runtime.

## Synchronous client

Reuse a `Client` when making more than one request so connections can be pooled:

```python
from cereja.http import Client

with Client(timeout=10, max_connections=20) as client:
    response = client.get("https://example.com/api", params={"page": 1})
    response.raise_for_status()
    data = response.json()
```

## Asynchronous client

`AsyncClient` performs network I/O with asyncio streams. It does not run the synchronous
client in a worker thread.

```python
from cereja.http import AsyncClient

async with AsyncClient(timeout=10, max_connections=20) as client:
    response = await client.get("https://example.com/api", params={"page": 1})
    response.raise_for_status()
    data = response.json()
```

## Request bodies

Use one body representation per request:

- `json=` encodes JSON, including `None`, `False`, `0`, and empty containers;
- `data=` encodes form data;
- `content=` sends strings or bytes-like content without interpreting raw bytes.

`params=` modifies the query string independently of the request body.

## Streaming

Materialized responses are bounded by `max_body_bytes`. For large responses, use streaming
instead of accumulating the entire body in memory.

```python
with Client() as client:
    with client.stream("GET", "https://example.com/large.bin") as response:
        for chunk in response.iter_bytes(64 * 1024):
            consume(chunk)
```

The async equivalent uses `async with` and `async for` with `aiter_bytes()`.
A stream that is closed before complete consumption discards its connection rather than
returning an ambiguous connection to the pool.

## Downloads

Filesystem downloads are intentionally outside the HTTP package:

```python
from cereja.transfers import download

download("https://example.com/archive.bin", "archive.bin")
```

`async_download()` uses native async HTTP and moves blocking local filesystem writes off the
event-loop thread. Downloads write to a temporary file in the destination directory and
atomically replace the destination after successful completion.

## Timeouts and retries

A scalar timeout configures connect, read, write, and pool-acquisition timeouts. `Timeout`
can be used when the phases need different values.

Retries are disabled by default. `RetryPolicy` only retries methods and failure categories
explicitly allowed by the policy. Async cancellation is always propagated and never treated
as a retryable transport error.

## Redirects and credentials

Redirects have a bounded hop count. Sensitive credentials such as `Authorization` and
cookies are stripped when a redirect crosses origins. Redirects that change a POST to GET
also drop body-specific headers.

## Scope

The first implementation targets HTTP/1.1: fixed-length bodies, chunked responses,
connection-close framing, keep-alive reuse, TLS through `ssl`, streaming, redirects,
timeouts, retries, body limits, and bounded connection pools.

HTTP/2, HTTP/3, WebSocket, SOCKS, digest authentication, and advanced proxy negotiation are
outside this implementation.

## Legacy `_requests`

`cereja._requests` is a migration surface, not the 3.0 API. Its convenience functions now
route through `cereja.http`; new code should import `cereja.http` directly.
