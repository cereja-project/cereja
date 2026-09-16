"""Native asyncio HTTP/1.1 transport."""

import asyncio
from dataclasses import dataclass
import ssl

from .._core.framing import response_framing
from ..errors import BodyLimitExceeded, ConnectError, ConnectTimeout, ProtocolError, TLSFailure, WriteTimeout
from ..headers import Headers
from ..models import Response, ResponseInfo
from .pool import AsyncConnectionPool
from .stream import AsyncByteStream, AsyncStreamResponse, _with_timeout


@dataclass(slots=True)
class Connection:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter


class AsyncTransport:
    def __init__(self, *, max_connections=20, ssl_context=None, max_body_bytes=16 * 1024 * 1024):
        self.pool = AsyncConnectionPool(max_connections)
        self.ssl_context = ssl_context or ssl.create_default_context()
        self.max_body_bytes = max_body_bytes

    def _key(self, request):
        return request.url.origin + ((id(self.ssl_context) if request.url.scheme == "https" else None),)

    async def _open(self, request, timeout):
        kwargs = {}
        if request.url.scheme == "https":
            kwargs.update(ssl=self.ssl_context, server_hostname=request.url.host)
        try:
            coro = asyncio.open_connection(request.url.host, request.url.effective_port, **kwargs)
            if timeout.connect is None:
                reader, writer = await coro
            else:
                async with asyncio.timeout(timeout.connect):
                    reader, writer = await coro
            return Connection(reader, writer)
        except asyncio.TimeoutError as exc:
            raise ConnectTimeout(f"Timed out connecting to {request.url}") from exc
        except ssl.SSLError as exc:
            raise TLSFailure(f"TLS failure for {request.url}") from exc
        except (ConnectionError, OSError) as exc:
            raise ConnectError(f"Unable to connect to {request.url}") from exc

    async def _send_headers(self, connection, request, timeout):
        lines = [f"{request.method} {request.url.target} HTTP/1.1\r\n".encode("ascii")]
        for name, value in request.headers:
            lines.append(f"{name}: {value}\r\n".encode("latin-1"))
        if "connection" not in request.headers:
            lines.append(b"Connection: keep-alive\r\n")
        lines.append(b"\r\n")
        connection.writer.write(b"".join(lines))
        if request.content:
            connection.writer.write(request.content)
        try:
            if timeout.write is None:
                await connection.writer.drain()
            else:
                async with asyncio.timeout(timeout.write):
                    await connection.writer.drain()
        except asyncio.TimeoutError as exc:
            raise WriteTimeout(f"Timed out writing request to {request.url}") from exc

    async def _readline(self, reader, timeout):
        return await _with_timeout(reader.readline(), timeout.read, "Timed out reading HTTP response headers")

    async def _read_response_head(self, connection, request, timeout):
        while True:
            line = await self._readline(connection.reader, timeout)
            if not line:
                raise ProtocolError("EOF before HTTP status line")
            try:
                version, code, reason = line.decode("latin-1").rstrip("\r\n").split(" ", 2)
                status = int(code)
            except (ValueError, UnicodeError) as exc:
                raise ProtocolError(f"Invalid HTTP status line: {line!r}") from exc
            if version not in {"HTTP/1.0", "HTTP/1.1"}:
                raise ProtocolError(f"Unsupported HTTP version: {version}")
            headers = Headers()
            while True:
                raw = await self._readline(connection.reader, timeout)
                if raw in (b"\r\n", b"\n"):
                    break
                if not raw:
                    raise ProtocolError("EOF in HTTP headers")
                if b":" not in raw:
                    raise ProtocolError(f"Malformed HTTP header: {raw!r}")
                name, value = raw.split(b":", 1)
                try:
                    headers.add(name.decode("ascii"), value.decode("latin-1").strip())
                except (UnicodeError, ValueError) as exc:
                    raise ProtocolError(f"Invalid HTTP header: {raw!r}") from exc
            if 100 <= status < 200 and status != 101:
                continue
            return ResponseInfo(status, reason, headers, request.url, version)

    async def send(self, request, timeout, *, stream=False):
        key = self._key(request)
        connection = await self.pool.acquire(key, lambda: self._open(request, timeout), timeout.pool)
        owned = True
        try:
            await self._send_headers(connection, request, timeout)
            info = await self._read_response_head(connection, request, timeout)
            mode, remaining, reusable = response_framing(
                request.method, info.status_code, info.headers, info.http_version
            )

            async def complete():
                nonlocal owned
                if owned:
                    owned = False
                    await self.pool.release(key, connection)

            async def abort():
                nonlocal owned
                if owned:
                    owned = False
                    await self.pool.discard(connection)

            body = AsyncByteStream(
                connection.reader,
                mode=mode,
                remaining=remaining,
                read_timeout=timeout.read,
                on_complete=complete,
                on_abort=abort,
                reusable=reusable,
            )
            if stream:
                return AsyncStreamResponse(request, info, body)
            if remaining is not None and self.max_body_bytes is not None and remaining > self.max_body_bytes:
                await body.aclose()
                raise BodyLimitExceeded(f"Response body exceeds {self.max_body_bytes} bytes")
            chunks = []
            total = 0
            async for chunk in body.aiter_bytes():
                total += len(chunk)
                if self.max_body_bytes is not None and total > self.max_body_bytes:
                    await body.aclose()
                    raise BodyLimitExceeded(f"Response body exceeds {self.max_body_bytes} bytes")
                chunks.append(chunk)
            return Response(request, info, b"".join(chunks))
        except asyncio.CancelledError:
            if owned:
                await self.pool.discard(connection)
                owned = False
            raise
        except BaseException:
            if owned:
                await self.pool.discard(connection)
                owned = False
            raise

    async def close(self):
        await self.pool.close()
