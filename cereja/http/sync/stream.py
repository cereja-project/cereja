"""Synchronous streaming response."""

from ..models import ResponseInfo, _raise_for_status

_UNSET = object()


class SyncByteStream:
    def __init__(self, response, *, on_complete, on_abort, remaining=_UNSET):
        self._response = response
        self._on_complete = on_complete
        self._on_abort = on_abort
        self._closed = False
        if remaining is _UNSET:
            value = response.getheader("Content-Length")
            self._remaining = int(value) if value is not None else None
        else:
            self._remaining = remaining

    def _finish(self):
        if not self._closed:
            self._closed = True
            self._on_complete()

    def read(self, size=-1):
        if self._closed:
            return b""
        if self._remaining == 0:
            self._finish()
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

    @property
    def filename(self) -> str | None:
        """Advisory server filename, or None when absent or unusable."""
        return self.info.filename

    @property
    def content_type(self) -> str | None:
        """Lowercase media type without parameters, or None if unusable."""
        return self.info.content_type

    @property
    def charset(self) -> str | None:
        """Lowercase declared charset token, without inferring an encoding."""
        return self.info.charset

    @property
    def content_length(self) -> int | None:
        """Declared Content-Length in bytes, not the consumed body size."""
        return self.info.content_length

    def read(self, size=-1):
        return self.stream.read(size)

    def raise_for_status(self):
        """Raise HTTPStatusError for status >= 400 without reading the body."""
        return _raise_for_status(self)

    def iter_bytes(self, chunk_size=65536):
        return self.stream.iter_bytes(chunk_size)

    def close(self):
        self.stream.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
