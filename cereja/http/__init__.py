"""Zero-dependency HTTP/1.1 clients for Cereja."""

from ._core.encoding import UNSET
from ._core.policies import RetryPolicy
from .async_ import AsyncClient
from .errors import (
    HTTPError, RequestError, ConnectError, TimeoutError, ConnectTimeout,
    ReadTimeout, WriteTimeout, PoolTimeout, ProtocolError, TLSFailure,
    HTTPStatusError, DecodeError, BodyLimitExceeded,
)
from .headers import Headers
from .models import Request, Response, ResponseInfo, Timeout
from .sync import Client
from .url import URL


def request(method, url, **kwargs):
    with Client() as client:
        return client.request(method, url, **kwargs)


def get(url, **kwargs): return request("GET", url, **kwargs)
def post(url, **kwargs): return request("POST", url, **kwargs)
def put(url, **kwargs): return request("PUT", url, **kwargs)
def patch(url, **kwargs): return request("PATCH", url, **kwargs)
def delete(url, **kwargs): return request("DELETE", url, **kwargs)
def head(url, **kwargs): return request("HEAD", url, **kwargs)


__all__ = [
    "URL", "Headers", "Timeout", "RetryPolicy", "Request", "ResponseInfo", "Response",
    "Client", "AsyncClient", "request", "get", "post", "put", "patch", "delete", "head",
    "HTTPError", "RequestError", "ConnectError", "TimeoutError",
    "ConnectTimeout", "ReadTimeout", "WriteTimeout", "PoolTimeout",
    "ProtocolError", "TLSFailure", "HTTPStatusError", "DecodeError", "BodyLimitExceeded",
]
