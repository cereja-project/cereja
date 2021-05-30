from urllib import request as urllib_req
from ..utils import string_to_literal
import json

__all__ = ['HttpRequest']

from urllib.error import HTTPError, URLError


class _Http:

    def __init__(self, url, content, headers=None, port=None, time_out=None):
        self.headers = headers or {}
        self._protocol, self._port, self._domains, self._endpoint = self.parse_url(url=url, port=port)
        self._content = content or None
        self.time_out = time_out

    @property
    def protocol(self):
        return self._protocol

    @property
    def port(self):
        return self._port

    @property
    def domains(self):
        return self._domains

    @property
    def endpoint(self):
        return self._endpoint

    @property
    def content(self):
        return self._content

    @property
    def url(self):
        port = f':{self._port}' if self._port else self._port
        endpoint = f"/{self._endpoint}" if self._endpoint else self._endpoint
        return f'{self._protocol}://{self._domains}{port}{endpoint}'

    @property
    def content_type(self):
        return self.headers.get('Content-type')

    @classmethod
    def parse_url(cls, url: str, port=None):

        url = url.replace('://', '.').replace(':', '.')
        url = url.split('/', maxsplit=1)

        url, endpoint = url if len(url) == 2 else (*url, '')

        endpoint = endpoint.split('/')

        protocol = None
        domains = []
        for n, i in enumerate(url.split('.')):

            i = i.strip().lower()
            if not i:
                continue
            if n == 0 and i.startswith('http'):
                protocol = i
                continue

            if i.isdigit():
                port = i
                continue
            domains.append(i)

        protocol = protocol or 'http'

        if not port:
            port = ''

        domains = '.'.join(domains)
        endpoint = '/'.join(endpoint)

        return protocol, port, domains, endpoint


class HttpResponse:
    def __init__(self, code, reason, content):
        self.code = code
        self.reason = reason
        self.content = string_to_literal(content)

    def __repr__(self):
        return f'Response({self.code})'


class HttpRequest(_Http):
    def __init__(self, method, url, data, port, *args, **kwargs):
        self._data = data
        http_content = self.parser(data)
        super().__init__(url=url, content=http_content, port=port, *args, **kwargs)
        if isinstance(self.data, dict):
            self.headers.update({'Content-type': 'application/json'})
        self._method = method

        req = urllib_req.Request(url=self.url, data=self.content, headers=self.headers,
                                 method=self._method)
        try:
            with urllib_req.urlopen(req) as f:
                content = f.read().decode()
            code = f.status
            reason = f.reason
        except HTTPError as err:
            content = err.read().decode()
            code = err.code
            reason = err.reason
        except URLError as err:
            msg = f"{err.reason}: {self.url}"
            raise URLError(msg)
        self._response = HttpResponse(code=code, reason=reason, content=content)

    @property
    def data(self):
        return self._data

    @property
    def response(self) -> 'HttpResponse':
        return self._response

    @classmethod
    def parser(cls, data) -> bytes:
        if isinstance(data, dict):
            return json.dumps(data).encode()

        return str(data).encode() if data else b''

    @classmethod
    def post(cls, url, data=None, port=None, headers=None):
        return cls('POST', url=url, data=data, port=port, headers=headers)

    @classmethod
    def get(cls, url=None, data=None, port=None, headers=None):
        return cls('GET', url=url, data=data, port=port, headers=headers)
