"""Shared HTTP request/response models."""

from dataclasses import dataclass
import json as jsonlib

from ._core.disposition import response_filename
from ._core.metadata import content_length_metadata, content_type_metadata
from .errors import DecodeError, HTTPStatusError
from .headers import Headers
from .url import URL


def _raise_for_status(response):
    if response.status_code >= 400:
        raise HTTPStatusError(
            f"HTTP {response.status_code} {response.info.reason} "
            f"for {response.request.method} {response.url}",
            request=response.request,
            response=response,
        )
    return None


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

    @property
    def filename(self) -> str | None:
        """Advisory basename from Content-Disposition, without consuming the body."""
        return response_filename(self.headers)

    @property
    def content_type(self) -> str | None:
        """Lowercase media type without parameters, or None if unusable."""
        return content_type_metadata(self.headers)[0]

    @property
    def charset(self) -> str | None:
        """Lowercase declared charset token, without inferring an encoding."""
        return content_type_metadata(self.headers)[1]

    @property
    def content_length(self) -> int | None:
        """Declared Content-Length in bytes, not the consumed body size."""
        return content_length_metadata(self.headers)


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
    def filename(self) -> str | None:
        """Advisory server filename, or None when absent or unusable."""
        return self.info.filename

    @property
    def content_type(self) -> str | None:
        """Lowercase media type without parameters, or None if unusable."""
        return self.info.content_type

    @property
    def charset(self) -> str | None:
        """Lowercase declared charset token, without inferring an encoding."""
        return self.info.charset

    @property
    def content_length(self) -> int | None:
        """Declared Content-Length in bytes, not the consumed body size."""
        return self.info.content_length

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
