from urllib import request as urllib_req
import json

__all__ = ['HttpRequest', 'HttpResponse']

from urllib.error import HTTPError, URLError


class _Http:

    def __init__(self, url, data=None, headers=None, port=None, time_out=None):
        self.headers = headers or {}
        self._protocol, self._port, self._domains, self._endpoint = self.parse_url(url=url, port=port)
        self._data = data or None
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
    def data(self):
        return self._data

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
    def __init__(self, request: 'HttpRequest'):
        self._request = request
        self._headers = {}
        try:
            with urllib_req.urlopen(self._request.urllib_req) as f:
                data = f.read()
                code = f.status
                reason = f.reason
                if hasattr(f, 'headers'):
                    self._headers = dict(f.headers.items())
        except HTTPError as err:
            data = err.read()
            code = err.code
            reason = err.reason
            if hasattr(err, 'headers'):
                self._headers = dict(err.headers.items())
        except URLError as err:
            msg = f"{err.reason}: {self._request.url}"
            raise URLError(msg)

        self._code = code
        self._status = reason
        self._data = data

    def __repr__(self):
        return f'Response(code={self.code}, status={self._status})'

    @property
    def content_type(self):
        return self._headers.get('Content-Type')

    @property
    def headers(self):
        return self._headers

    @property
    def request(self):
        return self._request

    @property
    def success(self):
        return self._code == 200

    @property
    def code(self):
        return self._code

    @property
    def status(self):
        return self._status

    @property
    def data(self):
        if self.content_type == 'application/json':
            if not self._data:
                return {}
            return json.loads(self._data)
        return self._data


class HttpRequest(_Http):
    def __init__(self, method, url, *args, **kwargs):
        super().__init__(url=url, *args, **kwargs)
        if isinstance(self.data, dict):
            self.headers.update({'Content-type': 'application/json'})
        self._count = 0
        self._method = method
        self._req = None

    def __repr__(self):
        return f'Request(url={self.url}, method={self._method})'

    def send_request(self, **kwargs):
        if 'data' in kwargs:
            self._data = self.parser(kwargs.pop('data'))

        if 'headers' in kwargs:
            headers = kwargs.pop('headers')
            assert isinstance(headers, dict), TypeError("Headers type is invalid. send a dict")
            self.headers.update(headers)
        self._count += 1
        return HttpResponse(request=self)

    @property
    def urllib_req(self):
        return urllib_req.Request(url=self.url, data=self.parser(self.data), headers=self.headers,
                                  method=self._method)

    @property
    def total_request(self):
        return self._count

    @property
    def data(self):
        return self._data

    @classmethod
    def parser(cls, data) -> bytes:
        if isinstance(data, dict):
            return json.dumps(data).encode()

        return str(data).encode() if data else b''

    @classmethod
    def build_and_send(cls, method, url, data=None, port=None, headers=None):
        return cls(method=method, url=url, data=data, port=port, headers=headers).send_request()
