# HTTP

Cereja provides zero-dependency HTTP/1.1 clients using only the Python standard library.
The synchronous and asynchronous clients share request, response, URL, header, timeout,
redirect, retry, and error semantics, while network I/O remains native to each runtime.

## Command line

`cereja http` exposes the synchronous client as a small curl-like command without adding
third-party dependencies. A URL alone performs GET:

```bash
cereja http https://example.com
```

The method can be positional or explicit:

```bash
cereja http POST https://example.com/users --json '{"name":"Joab"}'
cereja http -X POST https://example.com/users -d "raw body"
```

Headers and query parameters are repeatable:

```bash
cereja http https://example.com/users \
  -H "Authorization: Bearer token" \
  -H "Accept: application/json" \
  -q page=1 \
  -q limit=20
```

Useful response options include:

```bash
cereja http -i https://example.com        # response headers + body
cereja http -I https://example.com        # HEAD / headers only
cereja http -L https://example.com        # follow redirects
cereja http --pretty https://example.com  # pretty-print JSON
cereja http -v https://example.com        # diagnostics on stderr
cereja http https://example.com -o body.bin
```

The response body is written to stdout by default, so normal shell composition works:

```bash
cereja http https://example.com/api | jq .
```

Verbose diagnostics are written to stderr. Sensitive request/response headers such as
`Authorization`, cookies, and common API-key headers are redacted. TLS certificate and
hostname verification are enabled by default; `--insecure` must be supplied explicitly to
disable them.

`-o/--output` on `cereja http` writes a materialized response atomically and therefore still
obeys `--max-body` (16 MiB by default). For large files, use the dedicated streaming command.

## Download command

`cereja download` streams the response directly to an atomic filesystem sink instead of
materializing the complete body in memory:

```bash
cereja download https://example.com/archive.zip
cereja download https://example.com/archive.zip -o release.zip
```

When `-o/--output` is omitted, the destination filename is inferred from the URL path. A URL
without a filename requires an explicit output path. Existing files are protected by default:

```bash
cereja download https://example.com/archive.zip -o release.zip --force
```

The command follows HTTP redirects in streaming mode, reports transfer progress on stderr,
and writes nothing to stdout. Useful options include:

```bash
cereja download URL --timeout 30
cereja download URL --chunk-size 131072
cereja download URL --quiet
cereja download URL --insecure
```

`--quiet` disables progress/completion output. TLS verification remains enabled unless
`--insecure` is explicitly selected. Failed transfers leave the previous destination intact
and remove the temporary partial file.

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
Streaming redirects follow the same bounded redirect policy as materialized requests. A stream
that is closed before complete consumption discards its connection rather than returning an
ambiguous connection to the pool.

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