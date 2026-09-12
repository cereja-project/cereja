"""Legacy request facade backed by :mod:`cereja.http`.

This module exists only as a migration bridge for pre-3.0 internal/user code.
New code must import ``cereja.http`` directly.
"""

import json as _json
from pathlib import Path

from cereja.http import Client, URL

__all__ = [
    "is_url", "download", "get_proxies_list", "post", "get", "put",
    "head", "delete", "connect", "options", "trace", "patch",
]


class _LegacyResponse:
    def __init__(self, response):
        self._response = response

    @property
    def code(self):
        return self._response.status_code

    @property
    def status(self):
        return self._response.reason

    @property
    def headers(self):
        return self._response.headers

    @property
    def success(self):
        return 200 <= self.code < 300

    @property
    def data(self):
        content_type = self._response.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            return self._response.json() if self._response.content else {}
        return self._response.content

    def json(self):
        return self._response.json()


def _send(method, url, *, data=None, headers=None, timeout=None, **kwargs):
    with Client(timeout=timeout if timeout is not None else 5.0) as client:
        if data is not None and "data" not in kwargs and "content" not in kwargs and "json" not in kwargs:
            if isinstance(data, dict):
                kwargs["json"] = data
            else:
                kwargs["content"] = data
        response = client.request(method, url, headers=headers, **kwargs)
    return _LegacyResponse(response)


def download(url, save_on=None, timeout=None, **kwargs):
    response = _send("GET", url, timeout=timeout, **kwargs)
    if save_on is not None:
        Path(save_on).write_bytes(response._response.content)
    return response


def is_url(url):
    try:
        URL.parse(url)
    except (TypeError, ValueError):
        return False
    return True


def get_proxies_list():
    # The 3.0 HTTP core does not fetch or maintain an external proxy list.
    return {}


def post(url, data=None, headers=None, **kwargs):
    return _send("POST", url, data=data, headers=headers, **kwargs)


def get(url, data=None, headers=None, **kwargs):
    return _send("GET", url, data=data, headers=headers, **kwargs)


def put(url, **kwargs):
    return _send("PUT", url, **kwargs)


def head(url, **kwargs):
    return _send("HEAD", url, **kwargs)


def delete(url, **kwargs):
    return _send("DELETE", url, **kwargs)


def connect(url, **kwargs):
    return _send("CONNECT", url, **kwargs)


def options(url, **kwargs):
    return _send("OPTIONS", url, **kwargs)


def trace(url, **kwargs):
    return _send("TRACE", url, **kwargs)


def patch(url, **kwargs):
    return _send("PATCH", url, **kwargs)
