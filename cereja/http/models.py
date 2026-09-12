"""Shared HTTP request/response models."""

from dataclasses import dataclass
import json as jsonlib

from .errors import DecodeError, HTTPStatusError
from .headers import Headers
from .url import URL


@dataclass(frozen=True, slots=True)
class Timeout:
    connect: float | None = 5.0
    read: float | None = 5.0
    write: float | None = 5.0
    pool: float | None = 5.0

    @classmethod
    def from_value(cls, value):
        if isinstance(value, cls):
            return value
        if value is None:
            return cls(None, None, None, None)
        number = float(value)
        if number < 0:
            raise ValueError("Timeout must be non-negative")
        return cls(number, number, number, number)


@dataclass(frozen=True, slots=True)
class Request:
    method: str
    url: URL
    headers: Headers
    content: bytes | None


@dataclass(frozen=True, slots=True)
class ResponseInfo:
    status_code: int
    reason: str
    headers: Headers
    url: URL
    http_version: str


@dataclass(slots=True)
class Response:
    request: Request
    info: ResponseInfo
    content: bytes

    @classmethod
    def from_parts(cls, *, request, status_code, reason, headers, content, http_version):
        return cls(request, ResponseInfo(status_code, reason, headers, request.url, http_version), content)

    @property
    def status_code(self):
        return self.info.status_code

    @property
    def reason(self):
        return self.info.reason

    @property
    def headers(self):
        return self.info.headers

    @property
    def url(self):
        return self.info.url

    @property
    def text(self):
        content_type = self.headers.get("content-type", "")
        charset = "utf-8"
        for part in content_type.split(";")[1:]:
            key, sep, value = part.strip().partition("=")
            if sep and key.lower() == "charset":
                charset = value.strip().strip('"').strip("'")
                break
        try:
            return self.content.decode(charset)
        except (UnicodeError, LookupError) as exc:
            raise DecodeError(f"Unable to decode response using {charset!r}") from exc

    def json(self):
        try:
            return jsonlib.loads(self.content)
        except (UnicodeError, jsonlib.JSONDecodeError) as exc:
            raise DecodeError("Invalid JSON response") from exc

    def raise_for_status(self):
        if self.status_code >= 400:
            raise HTTPStatusError(
                f"HTTP {self.status_code} {self.reason} for {self.request.method} {self.url}",
                request=self.request,
                response=self,
            )
        return None
