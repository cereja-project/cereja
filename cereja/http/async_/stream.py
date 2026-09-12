"""Async HTTP/1.1 response body framing."""

import asyncio

from ..errors import ProtocolError, ReadTimeout


async def _with_timeout(awaitable, timeout, message):
    try:
        if timeout is None:
            return await awaitable
        return await asyncio.wait_for(awaitable, timeout)
    except asyncio.TimeoutError as exc:
        raise ReadTimeout(message) from exc


class AsyncByteStream:
    def __init__(self, reader, *, mode, remaining, read_timeout, on_complete, on_abort, reusable):
        self._reader = reader
        self._mode = mode
        self._remaining = remaining
        self._read_timeout = read_timeout
        self._on_complete = on_complete
        self._on_abort = on_abort
        self._reusable = reusable
        self._closed = False
        self._chunk_remaining = 0
        if mode == "none":
            self._remaining = 0

    async def _finish(self):
        if self._closed:
            return
        self._closed = True
        if self._reusable:
            await self._on_complete()
        else:
            await self._on_abort()

    async def _readline(self):
        return await _with_timeout(self._reader.readline(), self._read_timeout, "Timed out reading HTTP response")

    async def _readexactly(self, size):
        try:
            return await _with_timeout(self._reader.readexactly(size), self._read_timeout,
                                       "Timed out reading HTTP response")
        except asyncio.IncompleteReadError as exc:
            raise ProtocolError(f"Premature EOF: expected {size} bytes") from exc

    async def _read_chunked(self, size):
        if self._chunk_remaining == 0:
            line = await self._readline()
            if not line:
                raise ProtocolError("Premature EOF before chunk size")
            try:
                length = int(line.split(b";", 1)[0].strip(), 16)
            except ValueError as exc:
                raise ProtocolError("Invalid HTTP chunk size") from exc
            if length == 0:
                while True:
                    trailer = await self._readline()
                    if trailer in (b"\r\n", b"\n"):
                        break
                    if not trailer:
                        raise ProtocolError("Premature EOF in chunk trailers")
                await self._finish()
                return b""
            self._chunk_remaining = length
        take = self._chunk_remaining if size < 0 else min(size, self._chunk_remaining)
        data = await self._readexactly(take)
        self._chunk_remaining -= len(data)
        if self._chunk_remaining == 0:
            if await self._readexactly(2) != b"\r\n":
                raise ProtocolError("Invalid HTTP chunk terminator")
        return data

    async def read(self, size=-1):
        if self._closed:
            return b""
        if self._mode == "none":
            await self._finish()
            return b""
        if size == 0:
            return b""
        if size < 0:
            chunks = []
            while True:
                chunk = await self.read(65536)
                if not chunk:
                    return b"".join(chunks)
                chunks.append(chunk)
        if self._mode == "length":
            if self._remaining == 0:
                await self._finish()
                return b""
            take = min(size, self._remaining)
            data = await self._readexactly(take)
            self._remaining -= len(data)
            if self._remaining == 0:
                await self._finish()
            return data
        if self._mode == "chunked":
            return await self._read_chunked(size)
        data = await _with_timeout(self._reader.read(size), self._read_timeout, "Timed out reading HTTP response")
        if not data:
            await self._finish()
        return data

    async def aiter_bytes(self, chunk_size=65536):
        if chunk_size < 1:
            raise ValueError("chunk_size must be >= 1")
        while True:
            chunk = await self.read(chunk_size)
            if not chunk:
                break
            yield chunk

    async def aclose(self):
        if not self._closed:
            self._closed = True
            await self._on_abort()

    @property
    def closed(self):
        return self._closed


class AsyncStreamResponse:
    def __init__(self, request, info, stream):
        self.request = request
        self.info = info
        self.stream = stream

    @property
    def status_code(self): return self.info.status_code
    @property
    def headers(self): return self.info.headers
    @property
    def url(self): return self.info.url

    async def read(self, size=-1): return await self.stream.read(size)
    def aiter_bytes(self, chunk_size=65536): return self.stream.aiter_bytes(chunk_size)
    async def aclose(self): await self.stream.aclose()
    async def __aenter__(self): return self
    async def __aexit__(self, exc_type, exc, tb): await self.aclose()
