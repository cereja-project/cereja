"""HTTP URL parsing and composition."""

from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit


@dataclass(frozen=True, slots=True)
class URL:
    scheme: str
    host: str
    port: int | None
    path: str
    query: str = ""
    fragment: str = ""

    @classmethod
    def parse(cls, value, *, base_url=None):
        text = str(value)
        if base_url is not None:
            text = urljoin(str(base_url), text)
        parsed = urlsplit(text)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(f"Absolute HTTP(S) URL required: {value!r}")
        return cls(parsed.scheme.lower(), parsed.hostname, parsed.port, parsed.path or "/", parsed.query, parsed.fragment)

    @property
    def default_port(self):
        return 443 if self.scheme == "https" else 80

    @property
    def effective_port(self):
        return self.port or self.default_port

    @property
    def authority(self):
        host = f"[{self.host}]" if ":" in self.host else self.host
        if self.port is not None and self.port != self.default_port:
            return f"{host}:{self.port}"
        return host

    @property
    def origin(self):
        return self.scheme, self.host.lower(), self.effective_port

    @property
    def target(self):
        return self.path + (f"?{self.query}" if self.query else "")

    def with_params(self, params):
        if not params:
            return self
        pairs = parse_qsl(self.query, keep_blank_values=True)
        pairs.extend(params.items() if hasattr(params, "items") else params)
        query = urlencode(pairs, doseq=True)
        return URL(self.scheme, self.host, self.port, self.path, query, self.fragment)

    def resolve(self, location):
        return URL.parse(urljoin(str(self), str(location)))

    def __str__(self):
        return urlunsplit((self.scheme, self.authority, self.path, self.query, self.fragment))
