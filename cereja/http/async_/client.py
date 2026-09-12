"""Asynchronous high-level HTTP client."""

import asyncio

from .._core.encoding import UNSET
from .._core.policies import REDIRECT_STATUSES, RetryPolicy, build_redirect_request
from .._core.prepare import prepare_request
from ..errors import ProtocolError, RequestError
from ..models import Timeout
from .transport import AsyncTransport


class AsyncClient:
    def __init__(self, *, base_url=None, timeout=5.0, max_connections=20,
                 max_body_bytes=16 * 1024 * 1024, follow_redirects=True,
                 max_redirects=10, retries=0, ssl_context=None):
        self.base_url = base_url
        self.timeout = Timeout.from_value(timeout)
        self.follow_redirects = bool(follow_redirects)
        self.max_redirects = int(max_redirects)
        self.retry_policy = RetryPolicy.from_value(retries)
        self._transport = AsyncTransport(max_connections=max_connections, ssl_context=ssl_context,
                                         max_body_bytes=max_body_bytes)
        self._closed = False

    async def _send_with_retry(self, request, timeout, *, stream=False):
        attempt = 0
        while True:
            try:
                response = await self._transport.send(request, timeout, stream=stream)
            except asyncio.CancelledError:
                raise
            except RequestError as exc:
                if not self.retry_policy.should_retry(request, error=exc, attempt=attempt):
                    raise
                await asyncio.sleep(self.retry_policy.delay(attempt))
                attempt += 1
                continue
            if not stream and self.retry_policy.should_retry(request, status_code=response.status_code, attempt=attempt):
                await asyncio.sleep(self.retry_policy.delay(attempt))
                attempt += 1
                continue
            return response

    async def request(self, method, url, *, params=None, headers=None, json=UNSET, data=UNSET,
                      content=UNSET, timeout=None, follow_redirects=None):
        if self._closed:
            raise RuntimeError("AsyncClient is closed")
        timeout_config = Timeout.from_value(timeout) if timeout is not None else self.timeout
        request = prepare_request(method, url, base_url=self.base_url, params=params, headers=headers,
                                  json=json, data=data, content=content)
        follow = self.follow_redirects if follow_redirects is None else bool(follow_redirects)
        for hop in range(self.max_redirects + 1):
            response = await self._send_with_retry(request, timeout_config)
            if not follow or response.status_code not in REDIRECT_STATUSES:
                return response
            location = response.headers.get("location")
            if not location:
                return response
            if hop >= self.max_redirects:
                raise ProtocolError("Maximum redirect count exceeded")
            request = build_redirect_request(request, response.status_code, location)
        raise ProtocolError("Maximum redirect count exceeded")

    def stream(self, method, url, **kwargs):
        return _AsyncStreamContext(self, method, url, kwargs)

    async def get(self, url, **kwargs): return await self.request("GET", url, **kwargs)
    async def post(self, url, **kwargs): return await self.request("POST", url, **kwargs)
    async def put(self, url, **kwargs): return await self.request("PUT", url, **kwargs)
    async def patch(self, url, **kwargs): return await self.request("PATCH", url, **kwargs)
    async def delete(self, url, **kwargs): return await self.request("DELETE", url, **kwargs)
    async def head(self, url, **kwargs): return await self.request("HEAD", url, **kwargs)

    async def aclose(self):
        if not self._closed:
            self._closed = True
            await self._transport.close()

    async def __aenter__(self): return self
    async def __aexit__(self, exc_type, exc, tb): await self.aclose()


class _AsyncStreamContext:
    def __init__(self, client, method, url, kwargs):
        self.client = client
        self.method = method
        self.url = url
        self.kwargs = kwargs
        self.response = None

    async def __aenter__(self):
        if self.client._closed:
            raise RuntimeError("AsyncClient is closed")
        timeout = self.kwargs.pop("timeout", None)
        request = prepare_request(self.method, self.url, base_url=self.client.base_url, **self.kwargs)
        timeout_config = Timeout.from_value(timeout) if timeout is not None else self.client.timeout
        self.response = await self.client._send_with_retry(request, timeout_config, stream=True)
        return self.response

    async def __aexit__(self, exc_type, exc, tb):
        await self.response.aclose()
