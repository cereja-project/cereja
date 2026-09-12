"""Synchronous streaming response."""

from ..models import ResponseInfo


class SyncByteStream:
    def __init__(self, response, *, on_complete, on_abort):
        self._response = response
        self._on_complete = on_complete
        self._on_abort = on_abort
        self._closed = False
        value = response.getheader("Content-Length")
        self._remaining = int(value) if value is not None else None

    def _finish(self):
        if not self._closed:
            self._closed = True
            self._on_complete()

    def read(self, size=-1):
        if self._closed:
            return b""
        data = self._response.read(size)
        if self._remaining is not None:
            self._remaining -= len(data)
            if self._remaining <= 0:
                self._finish()
        elif size < 0 or not data:
            self._finish()
        return data

    def iter_bytes(self, chunk_size=65536):
        if chunk_size < 1:
            raise ValueError("chunk_size must be >= 1")
        while True:
            chunk = self.read(chunk_size)
            if not chunk:
                break
            yield chunk

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._response.close()
        self._on_abort()

    @property
    def closed(self):
        return self._closed


class StreamResponse:
    def __init__(self, request, info: ResponseInfo, stream: SyncByteStream):
        self.request = request
        self.info = info
        self.stream = stream

    @property
    def status_code(self):
        return self.info.status_code

    @property
    def headers(self):
        return self.info.headers

    @property
    def url(self):
        return self.info.url

    def read(self, size=-1):
        return self.stream.read(size)

    def iter_bytes(self, chunk_size=65536):
        return self.stream.iter_bytes(chunk_size)

    def close(self):
        self.stream.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
