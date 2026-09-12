"""Synchronous high-level HTTP client."""

from .._core.encoding import UNSET
from .._core.prepare import prepare_request
from ..errors import ProtocolError
from ..models import Timeout
from .transport import SyncTransport


_REDIRECTS = {301, 302, 303, 307, 308}


class Client:
    def __init__(self, *, base_url=None, timeout=5.0, max_connections=20,
                 max_body_bytes=16 * 1024 * 1024, follow_redirects=True,
                 max_redirects=10, ssl_context=None):
        self.base_url = base_url
        self.timeout = Timeout.from_value(timeout)
        self.follow_redirects = bool(follow_redirects)
        self.max_redirects = int(max_redirects)
        self._transport = SyncTransport(max_connections=max_connections, ssl_context=ssl_context,
                                        max_body_bytes=max_body_bytes)
        self._closed = False

    def _request_once(self, method, url, *, params=None, headers=None, json=UNSET,
                      data=UNSET, content=UNSET, timeout=None, stream=False):
        request = prepare_request(method, url, base_url=self.base_url, params=params, headers=headers,
                                  json=json, data=data, content=content)
        return request, self._transport.send(request, Timeout.from_value(timeout) if timeout is not None else self.timeout,
                                             stream=stream)

    def request(self, method, url, *, params=None, headers=None, json=UNSET, data=UNSET,
                content=UNSET, timeout=None, follow_redirects=None):
        if self._closed:
            raise RuntimeError("Client is closed")
        follow = self.follow_redirects if follow_redirects is None else bool(follow_redirects)
        current_method, current_url = str(method).upper(), url
        current_json, current_data, current_content = json, data, content
        for hop in range(self.max_redirects + 1):
            request, response = self._request_once(current_method, current_url, params=params if hop == 0 else None,
                                                   headers=headers, json=current_json, data=current_data,
                                                   content=current_content, timeout=timeout)
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
        if self._closed:
            raise RuntimeError("Client is closed")
        _request, response = self._request_once(method, url, stream=True, **kwargs)
        return response

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
