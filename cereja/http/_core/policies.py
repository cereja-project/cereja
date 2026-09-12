"""Pure redirect and retry decisions shared by sync and async clients."""

from dataclasses import dataclass, field

from ..errors import RequestError
from ..headers import Headers
from ..models import Request


IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "PUT", "DELETE", "OPTIONS", "TRACE"})
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_retries: int = 0
    backoff: float = 0.0
    retry_methods: frozenset[str] = field(default_factory=lambda: IDEMPOTENT_METHODS)
    retry_statuses: frozenset[int] = field(default_factory=frozenset)

    def __post_init__(self):
        if self.max_retries < 0 or self.backoff < 0:
            raise ValueError("Retry values must be non-negative")

    @classmethod
    def from_value(cls, value):
        if isinstance(value, cls):
            return value
        if value in (None, False, 0):
            return cls()
        if isinstance(value, int):
            return cls(max_retries=value)
        raise TypeError("retries must be an integer or RetryPolicy")

    def should_retry(self, request, *, error=None, status_code=None, attempt=0):
        if attempt >= self.max_retries or request.method not in self.retry_methods:
            return False
        if error is not None:
            return isinstance(error, RequestError)
        return status_code in self.retry_statuses

    def delay(self, attempt):
        return self.backoff * (2 ** attempt)


def build_redirect_request(request: Request, status_code: int, location: str) -> Request:
    if status_code not in REDIRECT_STATUSES:
        raise ValueError(f"Not a redirect status: {status_code}")
    target = request.url.resolve(location)
    method = request.method
    content = request.content
    drop_body = status_code == 303 or (status_code in {301, 302} and method == "POST")
    if drop_body:
        method = "GET"
        content = None

    headers = Headers()
    cross_origin = target.origin != request.url.origin
    for name, value in request.headers:
        lower = name.lower()
        if lower == "host":
            continue
        if cross_origin and lower in {"authorization", "proxy-authorization", "cookie"}:
            continue
        if drop_body and lower in {"content-length", "content-type", "transfer-encoding"}:
            continue
        headers.add(name, value)
    headers.set("Host", target.authority)
    if content is not None and "content-length" not in headers:
        headers.set("Content-Length", str(len(content)))
    return Request(method, target, headers, content)
