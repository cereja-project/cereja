"""Native blocking HTTP/1.1 transport using stdlib http.client."""

import http.client
import socket
import ssl

from .._core.framing import response_framing
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
    def _version(response):
        return "HTTP/1.1" if response.version == 11 else "HTTP/1.0"

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
        try:
            headers = Headers(raw.getheaders())
        except ValueError as exc:
            raw.close()
            self.pool.discard(connection)
            raise ProtocolError("Invalid HTTP response headers") from exc
        info = ResponseInfo(raw.status, raw.reason or "", headers, request.url, self._version(raw))
        try:
            mode, remaining, reusable = response_framing(
                request.method, info.status_code, info.headers, info.http_version
            )
        except BaseException:
            raw.close()
            self.pool.discard(connection)
            raise

        def complete():
            if reusable:
                self.pool.release(key, connection)
            else:
                self.pool.discard(connection)

        def abort():
            self.pool.discard(connection)

        if stream:
            return StreamResponse(
                request,
                info,
                SyncByteStream(raw, on_complete=complete, on_abort=abort, remaining=remaining),
            )

        if mode == "none":
            complete()
            return Response(request, info, b"")

        if remaining is not None and self.max_body_bytes is not None and remaining > self.max_body_bytes:
            raw.close()
            abort()
            raise BodyLimitExceeded(f"Response body exceeds {self.max_body_bytes} bytes")

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
            if remaining is not None and total != remaining:
                raise ProtocolError(f"Premature EOF: expected {remaining} bytes, got {total}")
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
