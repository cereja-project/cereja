"""Native blocking HTTP/1.1 transport using stdlib http.client."""

import http.client
import socket
import ssl

from ..errors import (
    BodyLimitExceeded, ConnectError, ConnectTimeout, ProtocolError,
    ReadTimeout, TLSFailure, WriteTimeout,
)
from ..headers import Headers
from ..models import Response, ResponseInfo
from .pool import ConnectionPool
from .stream import StreamResponse, SyncByteStream


class SyncTransport:
    def __init__(self, *, max_connections=20, ssl_context=None, max_body_bytes=16 * 1024 * 1024):
        self.pool = ConnectionPool(max_connections)
        self.ssl_context = ssl_context or ssl.create_default_context()
        self.max_body_bytes = max_body_bytes

    def _key(self, request):
        return request.url.origin + ((id(self.ssl_context) if request.url.scheme == "https" else None),)

    def _create_connection(self, request, timeout):
        kwargs = {"host": request.url.host, "port": request.url.effective_port, "timeout": timeout.connect}
        if request.url.scheme == "https":
            return http.client.HTTPSConnection(context=self.ssl_context, **kwargs)
        return http.client.HTTPConnection(**kwargs)

    @staticmethod
    def _reusable(response):
        connection = (response.getheader("Connection") or "").lower()
        return response.version == 11 and connection != "close"

    @staticmethod
    def _version(response):
        return "HTTP/1.1" if response.version == 11 else "HTTP/1.0"

    @staticmethod
    def _has_body(request, response):
        return not (
            request.method == "HEAD"
            or response.status in {204, 304}
            or 100 <= response.status < 200
        )

    def _perform(self, request, timeout):
        key = self._key(request)
        connection = self.pool.acquire(key, lambda: self._create_connection(request, timeout), timeout.pool)
        phase = "connect"
        try:
            connection.timeout = timeout.connect
            if connection.sock is None:
                connection.connect()
            phase = "write"
            if connection.sock is not None:
                connection.sock.settimeout(timeout.write)
            connection.putrequest(request.method, request.url.target, skip_host=True, skip_accept_encoding=True)
            for name, value in request.headers:
                connection.putheader(name, value)
            if "connection" not in request.headers:
                connection.putheader("Connection", "keep-alive")
            connection.endheaders(request.content)
            phase = "read"
            if connection.sock is not None:
                connection.sock.settimeout(timeout.read)
            response = connection.getresponse()
            return key, connection, response
        except socket.timeout as exc:
            self.pool.discard(connection)
            if phase == "connect":
                raise ConnectTimeout(f"Timed out connecting to {request.url}") from exc
            if phase == "write":
                raise WriteTimeout(f"Timed out writing request to {request.url}") from exc
            raise ReadTimeout(f"Timed out reading from {request.url}") from exc
        except ssl.SSLError as exc:
            self.pool.discard(connection)
            raise TLSFailure(f"TLS failure for {request.url}") from exc
        except (ConnectionError, OSError, http.client.HTTPException) as exc:
            self.pool.discard(connection)
            raise ConnectError(f"Unable to request {request.url}") from exc

    def send(self, request, timeout, *, stream=False):
        key, connection, raw = self._perform(request, timeout)
        reusable = self._reusable(raw)
        info = ResponseInfo(raw.status, raw.reason or "", Headers(raw.getheaders()), request.url, self._version(raw))
        has_body = self._has_body(request, raw)

        def complete():
            if reusable:
                self.pool.release(key, connection)
            else:
                self.pool.discard(connection)

        def abort():
            self.pool.discard(connection)

        if stream:
            if has_body:
                byte_stream = SyncByteStream(raw, on_complete=complete, on_abort=abort)
            else:
                byte_stream = SyncByteStream(raw, on_complete=complete, on_abort=abort, remaining=0)
            return StreamResponse(request, info, byte_stream)

        if not has_body:
            complete()
            return Response(request, info, b"")

        length = raw.getheader("Content-Length")
        if length is not None:
            try:
                expected_length = int(length)
            except ValueError as exc:
                raw.close()
                abort()
                raise ProtocolError("Invalid Content-Length") from exc
            if expected_length < 0:
                raw.close()
                abort()
                raise ProtocolError("Negative Content-Length")
            if self.max_body_bytes is not None and expected_length > self.max_body_bytes:
                raw.close()
                abort()
                raise BodyLimitExceeded(f"Response body exceeds {self.max_body_bytes} bytes")
        else:
            expected_length = None

        chunks = []
        total = 0
        try:
            while True:
                chunk = raw.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if self.max_body_bytes is not None and total > self.max_body_bytes:
                    raise BodyLimitExceeded(f"Response body exceeds {self.max_body_bytes} bytes")
                chunks.append(chunk)
            if expected_length is not None and total != expected_length:
                raise ProtocolError(f"Premature EOF: expected {expected_length} bytes, got {total}")
        except socket.timeout as exc:
            raw.close()
            abort()
            raise ReadTimeout(f"Timed out reading from {request.url}") from exc
        except http.client.IncompleteRead as exc:
            raw.close()
            abort()
            raise ProtocolError("Premature EOF in HTTP response") from exc
        except BaseException:
            raw.close()
            abort()
            raise
        complete()
        return Response(request, info, b"".join(chunks))

    def close(self):
        self.pool.close()
