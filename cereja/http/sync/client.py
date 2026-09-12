"""Synchronous high-level HTTP client."""

import time

from .._core.encoding import UNSET
from .._core.policies import REDIRECT_STATUSES, RetryPolicy, build_redirect_request
from .._core.prepare import prepare_request
from ..errors import ProtocolError, RequestError
from ..models import Timeout
from .transport import SyncTransport


class Client:
    def __init__(self, *, base_url=None, timeout=5.0, max_connections=20,
                 max_body_bytes=16 * 1024 * 1024, follow_redirects=True,
                 max_redirects=10, retries=0, ssl_context=None):
        self.base_url = base_url
        self.timeout = Timeout.from_value(timeout)
        self.follow_redirects = bool(follow_redirects)
        self.max_redirects = int(max_redirects)
        self.retry_policy = RetryPolicy.from_value(retries)
        self._transport = SyncTransport(max_connections=max_connections, ssl_context=ssl_context,
                                        max_body_bytes=max_body_bytes)
        self._closed = False

    def _send_with_retry(self, request, timeout, *, stream=False):
        attempt = 0
        while True:
            try:
                response = self._transport.send(request, timeout, stream=stream)
            except RequestError as exc:
                if not self.retry_policy.should_retry(request, error=exc, attempt=attempt):
                    raise
                time.sleep(self.retry_policy.delay(attempt))
                attempt += 1
                continue
            if not stream and self.retry_policy.should_retry(request, status_code=response.status_code, attempt=attempt):
                time.sleep(self.retry_policy.delay(attempt))
                attempt += 1
                continue
            return response

    def request(self, method, url, *, params=None, headers=None, json=UNSET, data=UNSET,
                content=UNSET, timeout=None, follow_redirects=None):
        if self._closed:
            raise RuntimeError("Client is closed")
        timeout_config = Timeout.from_value(timeout) if timeout is not None else self.timeout
        request = prepare_request(method, url, base_url=self.base_url, params=params, headers=headers,
                                  json=json, data=data, content=content)
        follow = self.follow_redirects if follow_redirects is None else bool(follow_redirects)
        for hop in range(self.max_redirects + 1):
            response = self._send_with_retry(request, timeout_config)
            if not follow or response.status_code not in REDIRECT_STATUSES:
                return response
            location = response.headers.get("location")
            if not location:
                return response
            if hop >= self.max_redirects:
                raise ProtocolError("Maximum redirect count exceeded")
            request = build_redirect_request(request, response.status_code, location)
        raise ProtocolError("Maximum redirect count exceeded")

    def stream(self, method, url, *, params=None, headers=None, json=UNSET, data=UNSET,
               content=UNSET, timeout=None, follow_redirects=None):
        if self._closed:
            raise RuntimeError("Client is closed")
        request = prepare_request(method, url, base_url=self.base_url, params=params, headers=headers,
                                  json=json, data=data, content=content)
        timeout_config = Timeout.from_value(timeout) if timeout is not None else self.timeout
        follow = self.follow_redirects if follow_redirects is None else bool(follow_redirects)
        for hop in range(self.max_redirects + 1):
            response = self._send_with_retry(request, timeout_config, stream=True)
            if not follow or response.status_code not in REDIRECT_STATUSES:
                return response
            location = response.headers.get("location")
            if not location:
                return response
            response.close()
            if hop >= self.max_redirects:
                raise ProtocolError("Maximum redirect count exceeded")
            request = build_redirect_request(request, response.status_code, location)
        raise ProtocolError("Maximum redirect count exceeded")

    def get(self, url, **kwargs): return self.request("GET", url, **kwargs)
    def post(self, url, **kwargs): return self.request("POST", url, **kwargs)
    def put(self, url, **kwargs): return self.request("PUT", url, **kwargs)
    def patch(self, url, **kwargs): return self.request("PATCH", url, **kwargs)
    def delete(self, url, **kwargs): return self.request("DELETE", url, **kwargs)
    def head(self, url, **kwargs): return self.request("HEAD", url, **kwargs)

    def close(self):
        if not self._closed:
            self._closed = True
            self._transport.close()

    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): self.close()
