# HTTP

Cereja provides zero-dependency HTTP/1.1 clients using only the Python standard library.
The synchronous and asynchronous clients share request, response, URL, header, timeout,
redirect, retry, and error semantics, while network I/O remains native to each runtime.

This guide describes the API in this checkout. Examples use placeholder URLs;
replace them with endpoints implementing the illustrated behavior. Sizes are in
bytes and timeouts are in seconds.

## Choose an API

| Task | API |
| --- | --- |
| Make a single request | `cereja.http.get()`, `post()`, or `request()` |
| Reuse connections | `Client` |
| Integrate with an async application | `AsyncClient` |
| Consume a large response incrementally | `client.stream()` |
| Save a file atomically | `cereja.transfers.download()` |
| Save a file asynchronously | `cereja.transfers.async_download()` |
| Download with authentication headers | `download(..., headers=...)` or `async_download(..., headers=...)` |
| Make requests in a terminal | `cereja http` |
| Download large public files in a terminal | `cereja download` |

## Quick start

```python
from cereja.http import get

response = get("https://api.example.com/users", params={"page": 1}, timeout=10)
response.raise_for_status()
users = response.json()
print(users)
```

Module-level helpers create and close a client for each call. They accept request
arguments, not constructor options such as `retries` or `max_connections`. Use a
client when making multiple requests or configuring a connection pool.

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

The CLI does not follow redirects unless `-L` is supplied, unlike the Python
clients. `--timeout` defaults to 5 seconds. CLI `-d` sends raw UTF-8 content,
unlike Python's form-oriented `data=` parameter. Examples above use Bash quoting.
In PowerShell, pass a token from the environment with:

```powershell
cereja http https://api.example.com/profile -H "Authorization: Bearer $env:API_TOKEN"
```

The command outputs HTTP 4xx and 5xx responses without calling `raise_for_status()`.
There is no fail-on-status flag. Handled execution errors return exit code 1;
argument parsing errors use argparse's exit behavior. `-o` replaces an existing
destination after materializing the response.

Verbose redaction applies to known sensitive headers in diagnostics. It does not
sanitize response bodies, arbitrary custom headers, or headers explicitly printed
with `-i` and `-I`.

`-o/--output` writes the materialized response atomically and therefore still obeys
`--max-body` (16 MiB by default). For intentionally large downloads, use `cereja download`
or the streaming `cereja.transfers.download()` API instead of raising the CLI materialization
limit.

## Streaming downloads

`cereja download` is the dedicated command for large files. It streams directly to an
atomic filesystem sink rather than buffering the complete response in memory:

```bash
cereja download https://example.com/archive.zip
cereja download https://example.com/archive.zip -o release.zip
cereja download https://example.com/archive.zip --force
cereja download https://example.com/archive.zip --quiet
```

If `-o/--output` is omitted, the destination name is inferred from the URL path. Existing
files are preserved unless `--force` is explicit. Temporary partial files are removed after
failure, redirects are followed while streaming, and progress/completion output goes to
stderr. The command also supports `--timeout`, `--chunk-size`, and `--insecure`.

The download timeout defaults to 10 seconds and the chunk size to 64 KiB. The
filename comes from the URL, not `Content-Disposition`. There is no `-H` option
for authenticated downloads; use the Python download helpers with `headers` below.

## Synchronous client

Reuse a `Client` when making more than one request so connections can be pooled:

```python
from cereja.http import Client

with Client(timeout=10, max_connections=20) as client:
    response = client.get("https://example.com/api", params={"page": 1})
    response.raise_for_status()
    data = response.json()
```

### Configuration reference

`Client` and `AsyncClient` accept the same constructor options:

| Option | Default | Purpose |
| --- | --- | --- |
| `base_url` | `None` | Resolve relative request URLs |
| `timeout` | `5.0` | Connect, read, write, and pool wait timeouts |
| `max_connections` | `20` | Bound the client's connection pool |
| `max_body_bytes` | `16 * 1024 * 1024` | Limit a materialized response body |
| `follow_redirects` | `True` | Follow supported redirects |
| `max_redirects` | `10` | Bound redirect hops |
| `retries` | `0` | Retry count or `RetryPolicy` |
| `ssl_context` | `None` | Default TLS verification or custom SSL context |

Headers and authentication are supplied per request. The constructor does not
accept `headers`, `auth`, or a cookie jar. There is no automatic token refresh.

Use context managers to close clients reliably. Manual lifecycle management uses
`client.close()` or `await client.aclose()` for async clients.

### Base URLs and methods

```python
from cereja.http import Client

with Client(base_url="https://api.example.com/v1/", timeout=10) as client:
    response = client.get("users/123")
    response.raise_for_status()
    user = response.json()
```

Relative URLs use standard URL joining: `"users/123"` preserves `/v1/` above,
while `"/users/123"` starts at the origin root. Keep a trailing slash on a base
URL representing a directory. Absolute request URLs can select another origin.

The convenience methods are `get`, `post`, `put`, `patch`, `delete`, and `head`.
Other methods use `client.request("OPTIONS", url)` or module-level `request()`.

### Request arguments

| Argument | Purpose |
| --- | --- |
| `params` | Query parameters as a mapping or iterable of pairs |
| `headers` | Headers as a mapping or iterable of pairs |
| `json` | JSON-serializable body |
| `data` | URL-encoded form mapping or string |
| `content` | Raw string or bytes-like body |
| `timeout` | Override the client's phase timeouts |
| `follow_redirects` | Override the client's redirect behavior |

These arguments apply to `request()`, the convenience methods, and `stream()`.
Use at most one of `json`, `data`, and `content`.

## Authentication and headers

### Bearer tokens and API keys

```python
import os

from cereja.http import Client

token = os.environ["API_TOKEN"]
headers = {"Authorization": f"Bearer {token}"}

with Client(base_url="https://api.example.com/", timeout=30) as client:
    response = client.get("profile", headers=headers)
    response.raise_for_status()
    profile = response.json()
```

Pass the header on every request that needs it. For API-key authentication, use
the backend's required header, such as `headers={"X-API-Key": api_key}`. There is
no built-in `auth=` shortcut.

### Basic authentication

For a backend requiring HTTP Basic authentication, construct the header explicitly
and use HTTPS:

```python
import base64
import os

from cereja.http import get

credentials = f"{os.environ['API_USER']}:{os.environ['API_PASSWORD']}"
encoded = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
response = get(
    "https://api.example.com/profile",
    headers={"Authorization": f"Basic {encoded}"},
    timeout=10,
)
response.raise_for_status()
```

Base64 is an encoding, not encryption. Match the credential character encoding
expected by the backend.

### Repeated headers and query parameters

Query parameters are appended to any query already present in the URL. Lists and
repeated pairs support multiple values:

```python
from cereja.http import Client, Headers

headers = Headers({"Accept": "application/json"})
headers.add("X-Tag", "one")
headers.add("X-Tag", "two")

with Client() as client:
    response = client.get(
        "https://api.example.com/search",
        params={"q": "release notes", "tag": ["python", "http"]},
        headers=headers.items(),
    )
    response.raise_for_status()
    cookies = response.headers.get_list("set-cookie")
```

Header lookup is case-insensitive. `get_list()` preserves separate values;
`get()` joins them with a comma and a space. Use `get_list()` for `Set-Cookie`.
Cookies are not automatically stored or sent later. `Headers.set()` replaces all
existing values for a header; `add()` appends another value.

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

### JSON, forms, and raw bodies

```python
from cereja.http import Client

with Client(base_url="https://api.example.com/") as client:
    response = client.post("users", json={"name": "Alex", "active": True})
    response.raise_for_status()
    created_user = response.json()

    response = client.post("forms", data={"name": "Alex", "tag": ["one", "two"]})
    response.raise_for_status()

    response = client.put(
        "files/123",
        content=b"example binary payload",
        headers={"Content-Type": "application/octet-stream"},
    )
    response.raise_for_status()
```

`json=` defaults to `Content-Type: application/json`. `data=` defaults to
`application/x-www-form-urlencoded` and accepts a mapping or pre-encoded string.
An explicit content-type header overrides these defaults. `content=` does not
infer a content type and accepts `str`, `bytes`, `bytearray`, or `memoryview`.
Strings are encoded as UTF-8.

Request bodies are prepared in memory. File handles, generators, streaming uploads,
and automatic multipart encoding are not supported by these body arguments.

Methods and header names are validated as HTTP tokens before transport. Header values reject
unsafe control characters. URL request targets are normalized/percent-encoded before they
reach either the sync or async request line, IDN hosts are normalized, and URL userinfo is
rejected instead of being silently discarded.

## Reading responses

Ordinary requests materialize the body before returning:

| Attribute or method | Meaning |
| --- | --- |
| `status_code` | Numeric HTTP status |
| `reason` | HTTP reason phrase |
| `headers` | Case-insensitive `Headers` object |
| `url` | URL of the returned response, after redirects |
| `filename` | Advisory basename from `Content-Disposition`, or `None` |
| `content_type` | Lowercase declared media type without parameters, or `None` |
| `charset` | Lowercase declared charset token, or `None` |
| `content_length` | Declared non-negative byte length, or `None` |
| `request` | Request associated with the response |
| `info.http_version` | HTTP version reported by the transport |
| `content` | Body as bytes |
| `text` | Decode using the declared charset, defaulting to UTF-8 |
| `json()` | Parse the body as JSON |
| `raise_for_status()` | Raise `HTTPStatusError` for status codes of 400 or higher |

HTTP error statuses do not automatically raise. Call `raise_for_status()` to
reject them. A 3xx status does not raise through this method. Do not call `json()`
on an empty body, such as a successful 204 response.

`json()` parses the bytes regardless of `Content-Type`. Invalid JSON, invalid
character data, and unsupported text charsets raise `DecodeError`.

### Content metadata

Materialized responses, synchronous and asynchronous streaming responses, and their
shared `response.info` expose the same header-only metadata:

```python
from cereja.http import Client

with Client() as client:
    with client.stream("GET", "https://example.com/report") as response:
        response.raise_for_status()
        print(response.content_type)
        print(response.charset)
        print(response.content_length)
```

For headers `Content-Type: Text/Plain; charset="UTF-8"` and `Content-Length: 123`,
these properties return `"text/plain"`, `"utf-8"`, and `123`. They do not consume
or decode the body, mutate headers, or infer values from the URL, file extension,
or downloaded bytes. Streaming metadata is available before consuming any chunks.
Async callers read these properties without `await`.

| Property | Missing or invalid metadata | Additional behavior |
| --- | --- | --- |
| `content_type` | `None` for an absent, repeated, or malformed Content-Type field | Normalizes type/subtype to lowercase and removes parameters |
| `charset` | `None` when missing, empty, syntactically invalid, repeated, or in a malformed Content-Type field | Unquotes and unescapes quoted values, then lowercases the declared token |
| `content_length` | `None` for an absent, repeated, malformed, or unparseable Content-Length field | Accepts zero and ASCII decimal digits with surrounding spaces/tabs |

Quoted parameter values can contain semicolons and escaped quotes. Duplicate
`charset` parameters are treated as ambiguous even if their values match; the media
type itself remains available if the rest of the field is well formed. Unsupported
but syntactically valid charset labels are returned as declared. The properties do
not resolve aliases, consult a codec registry, or guess a replacement encoding.

`charset=None` does not mean the text decoder has no default. Existing `response.text`
behavior is unchanged: it uses UTF-8 when no charset is declared and raises
`DecodeError` if the selected encoding is unsupported or the bytes cannot be
decoded. Its existing handling of malformed charset declarations is unchanged;
the metadata properties are not a new decoding policy.

`content_length` reports the server's declaration, not bytes already read, the
current body buffer size, or a verified final download size. It can be greater
than zero on a HEAD response whose body is empty, and is normally `None` for a
chunked response without Content-Length. Use `len(response.content)` for a
materialized body's actual byte count, or `DownloadResult.bytes_transferred` for
a completed filesystem transfer. Huge values exceeding the interpreter's integer
conversion limit return `None`; signed, fractional, and comma-separated values
are not accepted.

These header semantics are described in
[RFC 9110, Content-Type](https://www.rfc-editor.org/rfc/rfc9110.html#section-8.3)
and [Content-Length](https://www.rfc-editor.org/rfc/rfc9110.html#section-8.6).
The properties do not relax transport framing validation: malformed or repeated
Content-Length on a body-bearing HTTP/1.1 response can raise `ProtocolError`
before a response object is returned. Reading metadata does not change the
transfer helpers' byte-limit checks or the original raw header values.

## Error handling

```python
from cereja.http import Client, DecodeError, HTTPStatusError, RequestError, TimeoutError

with Client(timeout=10) as client:
    try:
        response = client.get("https://api.example.com/users/123")
        response.raise_for_status()
        user = response.json()
    except HTTPStatusError as error:
        print(f"API returned HTTP {error.response.status_code}")
    except TimeoutError:
        print("Request timed out")
    except RequestError as error:
        print(f"Transport failed: {type(error).__name__}")
    except DecodeError:
        print("Response is not valid JSON")
```

`TimeoutError` above is imported from Cereja, not the built-in exception.

| Exception | Condition |
| --- | --- |
| `HTTPError` | Base class for HTTP package errors |
| `RequestError` | Base class for transport errors |
| `ConnectError` | Connection failure |
| `TimeoutError` | Base for `ConnectTimeout`, `ReadTimeout`, `WriteTimeout`, and `PoolTimeout`; a `RequestError` |
| `TLSFailure` | TLS failure; a `RequestError` |
| `ProtocolError` | Invalid protocol behavior or redirect limit; a `RequestError` |
| `HTTPStatusError` | Explicit `raise_for_status()` or a download helper rejected the response |
| `DecodeError` | Text or JSON decoding failed |
| `BodyLimitExceeded` | Materialized response exceeded its configured limit |

Invalid arguments can raise `ValueError` or `TypeError`. Transfer filesystem
operations can raise `OSError`; those exceptions are not HTTP errors.

## Streaming

Materialized responses are bounded by `max_body_bytes`. For large responses, use streaming
instead of accumulating the entire body in memory.

```python
from cereja.http import Client

with Client() as client:
    with client.stream("GET", "https://example.com/large.bin") as response:
        response.raise_for_status()
        for chunk in response.iter_bytes(64 * 1024):
            print(f"Received {len(chunk)} bytes")
```

Streaming responses expose `status_code`, `headers`, `url`, `filename`, `content_type`,
`charset`, `content_length`, `request`, and `info`.
They also support `raise_for_status()`, with the same behavior as materialized
responses: statuses of 400 or higher raise `HTTPStatusError`, preserving the request
and streaming response on the exception. The method reads no body bytes and is
synchronous even on an async response, so call it without `await`. Stream context
managers still close the stream when the exception exits the context.
Streaming responses do not expose `content`, `text`, or `json()`.

The synchronous stream also supports `read(size)`. Unbounded `read()` can load
the remaining body into memory. Chunk size is a consumption setting; do not assume
each chunk is exactly that size. The materialized body limit does not cap streamed
bytes, so enforce a limit in your consumer when required.

The async equivalent uses `async with` and `async for` with `aiter_bytes()`.
A stream that is closed before complete consumption discards its connection rather than
returning an ambiguous connection to the pool. Sync and async streams both support bounded
redirect following.

### Async streaming and concurrency

Enter the async stream context directly, without awaiting `stream()`:

```python
import asyncio
import hashlib

from cereja.http import AsyncClient


async def hash_remote_file(url):
    digest = hashlib.sha256()
    async with AsyncClient(timeout=30) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes(64 * 1024):
                digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    print(asyncio.run(hash_remote_file("https://example.com/large.bin")))
```

For concurrent materialized requests, reuse a client within its async lifecycle:

```python
import asyncio

from cereja.http import AsyncClient


async def fetch_pages():
    async with AsyncClient(base_url="https://api.example.com/", max_connections=4) as client:
        responses = await asyncio.gather(
            client.get("users", params={"page": 1}),
            client.get("users", params={"page": 2}),
        )
        for response in responses:
            response.raise_for_status()
        return [response.json() for response in responses]


if __name__ == "__main__":
    print(asyncio.run(fetch_pages()))
```

Inside an existing async application, use `await fetch_pages()` rather than starting
another event loop. `max_connections` bounds connections, not tasks; bound task
creation separately for large workloads.

## Downloads

Filesystem downloads are intentionally outside the HTTP package:

```python
from cereja.transfers import download

download("https://example.com/archive.bin", "archive.bin")
```

`async_download()` uses native async HTTP and moves blocking local filesystem writes off the
event-loop thread. Downloads write to a temporary file in the destination directory and
atomically replace the destination after successful completion.

### Progress and byte limits

```python
from cereja.transfers import download


def report_progress(event):
    received_mib = event.bytes_transferred / (1024 ** 2)
    if event.total_bytes:
        percent = 100 * event.bytes_transferred / event.total_bytes
        print(f"\r{received_mib:.1f} MiB ({percent:.1f}%)", end="", flush=True)
    else:
        print(f"\r{received_mib:.1f} MiB received", end="", flush=True)


result = download(
    "https://example.com/archive.zip",
    "downloads/archive.zip",
    chunk_size=1024 * 1024,
    timeout=120,
    max_bytes=5 * 1024 ** 3,
    overwrite=False,
    progress=report_progress,
)
print(f"\nSaved {result.bytes_transferred} bytes to {result.path}")
```

The parent directory is created as needed. Failure removes the temporary file.
There is no built-in resume or checksum verification. Progress is reported per
chunk; throttle UI updates in the callback when necessary.

`TransferProgress` contains `bytes_transferred` and `total_bytes`. The total comes
from `Content-Length` and can be `None`, for example with chunked responses.
`DownloadResult` contains `path` (a `Path`), `bytes_transferred`, `total_bytes`, and
`status_code`.

| Keyword | `download()` | `async_download()` |
| --- | --- | --- |
| `destination` | Explicit file path; omit when using `destination_dir` | Same |
| `destination_dir` | Optional directory; select a name from the response | Same |
| `fallback_filename` | Default `"download.bin"`; used only with `destination_dir` | Same |
| `client` | Optional `Client` | Optional `AsyncClient` |
| `progress` | Synchronous callback | Synchronous or coroutine callback |
| `chunk_size` | Default 65536 | Default 65536 |
| `timeout` | Optional phase timeout override | Optional phase timeout override |
| `max_bytes` | Optional positive integer limit; default `None` | Same |
| `overwrite` | Default `True`; use `False` to preserve existing files | Same |
| `before_commit` | Optional synchronous callback before publication | Not available |
| `headers` | Optional request header mapping or iterable of pairs | Same |

`max_bytes` rejects an excessive declared length before writing and also counts
bytes during transfer. With this option, a declared length must match the received
byte count. A limit or length mismatch raises `ValueError`. Both helpers raise
`HTTPStatusError` for HTTP status codes of 400 or higher. These download status
errors remain catchable as `RuntimeError` for compatibility; see below.

The byte limit applies to both helpers, with or without `Content-Length`, and the
chunk that would exceed the limit is rejected before being written. A body exactly
at the limit is allowed. Without `max_bytes`, no transfer byte cap is imposed.
Zero, negative, boolean, and non-integer limits are rejected before creating a client.

`overwrite` must be a boolean. Its default remains `True` in both APIs. With
`overwrite=False`, publication fails with `FileExistsError` if the destination
exists, including when another writer creates it during the transfer. Existing
contents are preserved and the temporary file is removed. This policy uses an
atomic filesystem hard link; an unsupported filesystem raises `OSError` rather
than falling back to an unsafe existence check and replacement.

A supplied client remains owned by the caller and is not closed by the helper.
Without one, the helper creates and closes its own client. `timeout=None` inherits
the client's configuration.

When `headers` is omitted or `None`, the helpers preserve the original
`client.stream("GET", url, timeout=...)` call signature. Borrowed clients only need
to accept a `headers` argument when that option is explicitly supplied.

Async file operations run in worker threads. Cancellation waits for an outstanding
open, write, commit, or abort operation to finish before propagating
`asyncio.CancelledError`; repeated cancellation requests do not let cleanup race
that worker. Cancellation before publication preserves an existing destination
and removes the operation's temporary file. If commit is already running, atomic
publication may finish before cancellation is reported. A published file is not
rolled back, and the helper will not return while a worker could still publish it
later. Cancellation can therefore take as long as the outstanding file operation.

### HTTP errors and RuntimeError compatibility

Both helpers reject status codes of 400 or higher before opening a temporary file,
creating the destination directory, or consuming body bytes. Catch
`cereja.http.HTTPStatusError` to inspect the HTTP failure:

```python
from cereja.http import HTTPStatusError
from cereja.transfers import download

try:
    result = download(
        "https://api.example.com/files/123/download",
        destination_dir="downloads",
        fallback_filename="export.zip",
        overwrite=False,
    )
except HTTPStatusError as error:
    print(f"Download rejected with HTTP {error.response.status_code}")
    print(error.response.headers.get("Retry-After"))
    print(error.request.url)
```

The async helper raises the same exception family when awaited. The exception
retains the original request and streaming response objects, including the final
URL after redirects, status, and headers. The stream is closed before the error
reaches the caller, so its body cannot be read later. Custom borrowed clients that
return a response without a `request` attribute leave `error.request` as `None`.

Previously these helpers raised plain `RuntimeError` for HTTP statuses. To preserve
existing `except RuntimeError` handlers, download status errors now use an internal
subclass of both `HTTPStatusError` and `RuntimeError`. Catch the public classes,
not the internal implementation type. The legacy message format is preserved:
`HTTP <status> while downloading <original URL>`.

Existing RuntimeError handlers need no immediate change. Prefer `HTTPStatusError`
for new HTTP-specific handling, placing it before a broader RuntimeError handler:

```python
from cereja.http import HTTPStatusError
from cereja.transfers import download

try:
    result = download("https://example.com/export", "downloads/export.zip")
except HTTPStatusError as error:
    print(f"HTTP failure: {error.response.status_code}")
except RuntimeError:
    print("Another runtime failure occurred")
```

Only download status errors have this RuntimeError compatibility. The public
`HTTPStatusError` base and errors from ordinary or streaming `raise_for_status()`
retain their existing inheritance. Exact type comparisons such as
`type(error) is RuntimeError` no longer match download status errors; use exception
handlers or `isinstance()` instead. A broad `except HTTPError` also catches them
now, so review handler order if your application catches both families.

Other failures are not wrapped or reclassified: transport failures keep their
`RequestError` types, invalid limits and length mismatches remain `ValueError`,
filesystem failures remain `OSError` (including `FileExistsError`), and callback
exceptions propagate as raised. Existing destination contents are preserved on
an HTTP status failure regardless of `overwrite`.

### Async download

```python
import asyncio

from cereja.transfers import async_download


async def main():
    result = await async_download(
        "https://example.com/archive.zip",
        "downloads/archive.zip",
        chunk_size=1024 * 1024,
        timeout=120,
        max_bytes=5 * 1024 ** 3,
        overwrite=False,
    )
    print(f"Saved {result.bytes_transferred} bytes to {result.path}")


if __name__ == "__main__":
    asyncio.run(main())
```

The async helper has the same size and overwrite controls as the synchronous
helper. `before_commit` remains specific to the synchronous helper.

### Authenticated download

Pass the backend's required headers directly to either helper. The same atomic
publication and byte-limit controls apply to authenticated downloads:

```python
import os

from cereja.transfers import download

result = download(
    "https://api.example.com/files/123/download",
    "downloads/large-file.zip",
    headers={"Authorization": f"Bearer {os.environ['API_TOKEN']}"},
    max_bytes=5 * 1024 ** 3,
    overwrite=False,
    timeout=120,
)
print(result.path)
```

For an async application:

```python
import asyncio
import os

from cereja.transfers import async_download


async def main():
    result = await async_download(
        "https://api.example.com/files/123/download",
        "downloads/large-file.zip",
        headers={"Authorization": f"Bearer {os.environ['API_TOKEN']}"},
        max_bytes=5 * 1024 ** 3,
        overwrite=False,
        timeout=120,
    )
    print(result.path)


if __name__ == "__main__":
    asyncio.run(main())
```

Headers are passed to the HTTP client's GET request, including when you supply
your own client. A mapping is suitable for bearer tokens or API keys; an iterable
of pairs preserves repeated headers. Omit `headers` to keep the unauthenticated
behavior. The normal HTTP redirect rules still apply: Authorization is stripped
across origins, while custom secret headers require the application's redirect
policy described below. A borrowed client can disable automatic redirects.

### Choosing a destination from response metadata

Pass `destination_dir` to either helper to save the file using the server-provided
name. It is an explicit alternative to the existing `destination` file argument:

```python
import os

from cereja.transfers import download

result = download(
    "https://api.example.com/files/123/download",
    destination_dir="downloads/reports",
    fallback_filename="export.zip",
    headers={"Authorization": f"Bearer {os.environ['API_TOKEN']}"},
    max_bytes=5 * 1024 ** 3,
    overwrite=False,
    timeout=120,
)
print(result.path)
```

For example, if the response has `Content-Disposition: attachment; filename="report.zip"`,
the resulting path is `downloads/reports/report.zip`. The name comes from
`response.filename`, including its `filename*` decoding and basename validation.
After redirects, the final response supplies the name.

If the header is absent, malformed, ambiguous, or has no usable filename, the
helper uses `fallback_filename`. The default is `"download.bin"`; no name is inferred
from the URL. A custom fallback must be a string containing a usable basename, with
no path components, surrounding whitespace, reserved device names, or invalid
filename characters. Invalid directory-mode fallbacks fail before creating a
client, even if the server might supply a valid name.

The async interface uses the same options:

```python
import asyncio

from cereja.transfers import async_download


async def main():
    result = await async_download(
        "https://example.com/export",
        destination_dir="downloads/reports",
        fallback_filename="export.zip",
        overwrite=False,
        max_bytes=5 * 1024 ** 3,
    )
    print(result.path)


if __name__ == "__main__":
    asyncio.run(main())
```

The directory is created as needed when opening the temporary file. Both naming
paths use the same atomic sink and byte-limit policy. `overwrite=False` protects
the resolved filename, including fallback names and competing writers; collisions
raise `FileExistsError` rather than generating a numbered filename. `overwrite=True`
replaces that file after successful completion. `DownloadResult.path` reports the
actual chosen path.

Provide exactly one of `destination` and `destination_dir`; providing both or neither
raises `ValueError`. A positional path is always an explicit file destination,
even if it points to an existing directory or has a trailing separator. It is never
silently reinterpreted as directory mode. Explicit file destinations ignore server
filenames, and `fallback_filename` is only used and validated in directory mode.
The download CLI continues to infer its name from the URL when `-o` is omitted.

### Manual streaming to a file

Use HTTP streaming directly when the application needs to inspect headers or
process body chunks itself:

```python
import os
from pathlib import Path

from cereja.http import Client

token = os.environ["API_TOKEN"]
directory = Path("downloads")
directory.mkdir(parents=True, exist_ok=True)

with Client(timeout=120) as client:
    with client.stream(
        "GET",
        "https://api.example.com/files/123/download",
        headers={"Authorization": f"Bearer {token}"},
    ) as response:
        response.raise_for_status()
        destination = directory / (response.filename or "large-file.zip")
        with destination.open("xb") as output:
            for chunk in response.iter_bytes(1024 * 1024):
                output.write(chunk)
```

This recipe writes directly to the destination. `"xb"` prevents overwriting an
existing file, but a failed transfer leaves a partial file. It does not provide
the transfer helper's atomic publication or automatic temporary-file cleanup.

### Server-provided filenames

`response.filename` is available on materialized responses, synchronous and
asynchronous streaming responses, and their shared `response.info`. It reads only
the headers and does not consume body bytes:

```python
from cereja.http import Client

with Client() as client:
    with client.stream("GET", "https://example.com/export") as response:
        print(response.filename)
        print(response.headers.get("Content-Disposition"))
```

For `Content-Disposition: attachment; filename="report.zip"`, the property returns
`"report.zip"`. A valid `filename*` takes precedence over `filename`; UTF-8 and
ISO-8859-1 extended values are supported, including percent-encoded characters.
An unusable extended value falls back to the ordinary `filename`, if present.
Ordinary filenames are not percent-decoded.

The parser follows the filename precedence and advisory-name guidance in
[RFC 6266](https://www.rfc-editor.org/rfc/rfc6266.html#section-4.3). Missing names,
malformed fields, repeated Content-Disposition fields, and duplicate parameter
names return `None`. MIME continuation parameters such as `filename*0` are not
combined. There is no automatic fallback to the URL: the application chooses one,
as in the manual streaming recipe above.

Path components separated by `/` or `\` are discarded. Empty names, dot names,
control characters, Windows-invalid filename characters, trailing dots, and
reserved device names are rejected. Surrounding whitespace is stripped. The name
remains a suggestion: filesystem length limits, collisions, file extensions,
content validation, and permission decisions remain the application's responsibility.
Reading this property never creates or overwrites a file. Transfer helpers use it
only when `destination_dir` is supplied; explicit file destinations and the download
CLI's URL-based inference remain unchanged.

## Timeouts and retries

A scalar timeout configures connect, read, write, and pool-acquisition timeouts. `Timeout`
can be used when the phases need different values.

```python
from cereja.http import Client, Timeout

timeout = Timeout(connect=5, read=60, write=30, pool=10)
with Client(timeout=timeout) as client:
    response = client.get("https://api.example.com/report")
    response.raise_for_status()
```

A per-request scalar, such as `client.get(url, timeout=120)`, overrides all four
phases. Timeouts are not a deadline for the complete transfer: successful successive
reads can keep a download running longer.

`Client(timeout=None)` disables phase timeouts. A request's `timeout=None` inherits
the client's configuration instead. Use a `Timeout` object to disable selected
phases explicitly, such as `Timeout(read=None)`.

Retries are disabled by default. `RetryPolicy` only retries methods and failure categories
explicitly allowed by the policy. Async cancellation is always propagated and never treated
as a retryable transport error.

```python
from cereja.http import Client, RetryPolicy

policy = RetryPolicy(
    max_retries=2,
    backoff=0.5,
    retry_methods=frozenset({"GET", "HEAD"}),
    retry_statuses=frozenset({429, 502, 503, 504}),
)
with Client(retries=policy, timeout=10) as client:
    response = client.get("https://api.example.com/report")
    response.raise_for_status()
```

An integer such as `retries=2` allows two additional attempts for eligible transport
failures. It does not enable status-code retries by itself. Default eligible methods
are GET, HEAD, PUT, DELETE, OPTIONS, and TRACE. POST and PATCH require explicit opt-in.
Retry only when repeating the backend operation is acceptable; a transport failure
can occur after the server receives a request.

Delays follow `backoff * 2 ** attempt`, starting at attempt zero. `Retry-After` is
not automatically honored. Status retries apply to materialized requests, not
streaming responses. Failures while consuming a stream do not automatically restart
or resume the body.

## Redirects and credentials

Redirects have a bounded hop count. Sensitive credentials such as `Authorization` and
cookies are stripped when a redirect crosses origins. Redirects that change a POST to GET
also drop body-specific headers.

Supported redirect statuses are 301, 302, 303, 307, and 308. A 303 changes the method
to GET; 301 and 302 change POST to GET. 307 and 308 preserve method and body. Disable
following globally with `Client(follow_redirects=False)` or per request with
`client.get(url, follow_redirects=False)` to inspect `Location` yourself.

Cross-origin means a different scheme, host, or effective port. The specific
headers stripped are `Authorization`, `Proxy-Authorization`, and `Cookie`.
Custom credential headers such as `X-API-Key` are not removed by that rule. Disable
automatic redirects when your application must validate destinations before
forwarding a custom secret header.

## Custom TLS trust

Certificate and hostname verification are enabled by default. To trust a custom CA
without disabling verification:

```python
import ssl

from cereja.http import Client

context = ssl.create_default_context(cafile="certificates/company-ca.pem")
with Client(ssl_context=context) as client:
    response = client.get("https://api.internal.example.com/health")
    response.raise_for_status()
```

For mutual TLS, call
`context.load_cert_chain(certfile="client.crt", keyfile="client.key")` before
creating the client.

## Response framing

Cereja is intentionally strict when HTTP/1.1 framing is ambiguous. Both transports use the
same framing rules. Responses that combine `Transfer-Encoding` with `Content-Length`, repeat
`Content-Length`, or use transfer codings outside the supported single `chunked` coding are
rejected as protocol errors instead of being guessed differently by sync and async paths.

## Scope

The first implementation targets HTTP/1.1: fixed-length bodies, chunked responses,
connection-close framing, keep-alive reuse, TLS through `ssl`, streaming, redirects,
timeouts, retries, body limits, and bounded connection pools.

HTTP/2, HTTP/3, WebSocket, SOCKS, digest authentication, and advanced proxy negotiation are
outside this implementation.

The API also does not provide a managed cookie jar, automatic multipart encoding,
streaming request bodies, or automatic download resumption. Chunked framing is
distinct from content compression; do not assume automatic gzip or Brotli decoding.

## Legacy `_requests`

`cereja._requests` is a migration surface, not the 3.0 API. Its convenience functions now
route through `cereja.http`; new code should import `cereja.http` directly.

| Legacy facade | Current API |
| --- | --- |
| `response.code` | `response.status_code` |
| `response.status` | `response.reason` |
| `response.success` | Explicit status check or `raise_for_status()` |
| `response.data` | `response.content`, `response.text`, or `response.json()` |
| `_requests.download(..., save_on=...)` | `transfers.download(url, destination, headers=...)` for filesystem downloads |

The legacy download materializes the response in memory and is not the large-file
streaming helper.
