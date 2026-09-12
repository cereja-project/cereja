"""Asynchronous high-level HTTP client."""

from .._core.encoding import UNSET
from .._core.prepare import prepare_request
from ..errors import ProtocolError
from ..models import Timeout
from .transport import AsyncTransport


_REDIRECTS = {301, 302, 303, 307, 308}


class AsyncClient:
    def __init__(self, *, base_url=None, timeout=5.0, max_connections=20,
                 max_body_bytes=16 * 1024 * 1024, follow_redirects=True,
                 max_redirects=10, ssl_context=None):
        self.base_url = base_url
        self.timeout = Timeout.from_value(timeout)
        self.follow_redirects = bool(follow_redirects)
        self.max_redirects = int(max_redirects)
        self._transport = AsyncTransport(max_connections=max_connections, ssl_context=ssl_context,
                                         max_body_bytes=max_body_bytes)
        self._closed = False

    async def _request_once(self, method, url, *, params=None, headers=None, json=UNSET,
                            data=UNSET, content=UNSET, timeout=None, stream=False):
        request = prepare_request(method, url, base_url=self.base_url, params=params, headers=headers,
                                  json=json, data=data, content=content)
        response = await self._transport.send(
            request, Timeout.from_value(timeout) if timeout is not None else self.timeout, stream=stream
        )
        return request, response

    async def request(self, method, url, *, params=None, headers=None, json=UNSET, data=UNSET,
                      content=UNSET, timeout=None, follow_redirects=None):
        if self._closed:
            raise RuntimeError("AsyncClient is closed")
        follow = self.follow_redirects if follow_redirects is None else bool(follow_redirects)
        current_method, current_url = str(method).upper(), url
        current_json, current_data, current_content = json, data, content
        for hop in range(self.max_redirects + 1):
            request, response = await self._request_once(
                current_method, current_url, params=params if hop == 0 else None,
                headers=headers, json=current_json, data=current_data, content=current_content,
                timeout=timeout,
            )
            if not follow or response.status_code not in _REDIRECTS:
                return response
            location = response.headers.get("location")
            if not location:
                return response
            if hop >= self.max_redirects:
                raise ProtocolError("Maximum redirect count exceeded")
            target = request.url.resolve(location)
            if response.status_code == 303 or (response.status_code in {301, 302} and current_method == "POST"):
                current_method = "GET"
                current_json = current_data = current_content = UNSET
            current_url = str(target)
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
        _request, self.response = await self.client._request_once(self.method, self.url, stream=True, **self.kwargs)
        return self.response

    async def __aexit__(self, exc_type, exc, tb):
        await self.response.aclose()
