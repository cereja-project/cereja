"""
Copyright (c) 2019 The Cereja Project

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import threading
import time
from urllib import request as urllib_req
import json
import io
from ..config import PROXIES_URL

__all__ = ["HttpRequest", "HttpResponse"]

from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from cereja import Progress


class _Http:
    def __init__(self, url, data=None, headers=None, port=None):
        self.headers = headers or {}
        self._protocol, self._port, self._domains, self._endpoint = self.parse_url(
                url=url, port=port
        )
        self._data = data or None

    @staticmethod
    def is_url(val):
        try:
            result = urlparse(val)
            return all([result.scheme, result.netloc])
        except:
            return False

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
        port = f":{self._port}" if self._port else self._port
        endpoint = f"/{self._endpoint}" if self._endpoint else self._endpoint
        return f"{self._protocol}://{self._domains}{port}{endpoint}"

    @property
    def content_type(self):
        return self.headers.get("Content-type")

    @property
    def content_length(self):
        return self.headers.get("Content-length")

    @classmethod
    def parse_url(cls, url: str, port=None):

        url = url.replace("://", ".")
        url = url.split("/", maxsplit=1)

        domains = url.pop(0).split(".")
        if ":" in domains[-1]:
            domain, port = domains[-1].split(":")
            domains[-1] = domain

        protocol = domains.pop(0) if domains[0].startswith("http") else "https"

        if not port:
            port = ""

        domains = ".".join(domains)
        endpoint = "/".join(url) if url else ""

        return protocol, port, domains, endpoint


class HttpResponse:
    CHUNK_SIZE = 1024 * 1024 * 1  # 1MB

    def __init__(self, request: "HttpRequest", save_on_path=None, timeout=None):
        self._finished = False
        self._timeout = timeout
        self._code = None
        self._status = None
        self._data = None
        self._headers = {}
        self._request = request
        self._save_on_path = save_on_path
        self._total_completed = "0.0%"
        self._th_request = threading.Thread(target=self.__request)
        self._th_request.start()
        while not self.headers and not self._finished:
            time.sleep(0.1)  # await headers

    def __request(self):
        # TODO: send to HttpRequest ?
        try:
            with urllib_req.urlopen(
                    self._request.urllib_req, timeout=self._timeout
            ) as req_file:
                self._code = req_file.status
                self._status = req_file.reason
                if hasattr(req_file, "headers"):
                    self._headers = dict(req_file.headers.items())
                if self.CHUNK_SIZE * 3 > (req_file.length or 0):
                    self._data = req_file.read()
                else:
                    with Progress(
                            name=f"Fetching data",
                            max_value=int(req_file.getheader("Content-Length")),
                            states=("download", "time"),
                    ) as prog:

                        with (
                                open(self._save_on_path, "wb")
                                if self._save_on_path
                                else io.BytesIO()
                        ) as f:
                            total_downloaded = 0
                            while True:
                                chunk = req_file.read(self.CHUNK_SIZE)
                                if not chunk:
                                    break
                                f.write(chunk)
                                total_downloaded += len(chunk)
                                prog.show_progress(total_downloaded)
                                self._total_completed = prog.total_completed

                            self._data = f if self._save_on_path else f.getvalue()
        except HTTPError as err:
            self._data = err.read()
            self._code = err.code
            self._status = err.reason
            if hasattr(err, "headers"):
                self._headers = dict(err.headers.items())
        except URLError as err:
            msg = f"{err.reason}: {self._request.url}"
            self._finished = True
            raise URLError(msg)
        self._finished = True

    def __repr__(self):
        if not self._finished:
            return f"<HttpResponse: Fetching data {self._total_completed}>"
        return f"<HttpResponse: code={self.code}, status={self._status}>"

    @property
    def content_type(self):
        if not self._finished:
            self._th_request.join()
        return self._headers.get("Content-Type")

    @property
    def headers(self):
        if not self._finished:
            self._th_request.join()
        return self._headers

    @property
    def request(self):
        if not self._finished:
            self._th_request.join()
        return self._request

    @property
    def success(self):
        if not self._finished:
            self._th_request.join()
        return self._code == 200

    @property
    def code(self):
        if not self._finished:
            self._th_request.join()
        return self._code

    @property
    def status(self):
        if not self._finished:
            self._th_request.join()
        return self._status

    def json(self):
        if not self._finished:
            self._th_request.join()
        return json.loads(self._data)

    @property
    def data(self):
        self._th_request.join()  # await for request
        if self.content_type == "application/json":
            if not self._data:
                return {}
            return self.json()
        return self._data


class HttpRequest(_Http):
    PROXIES = {}

    def __init__(self, method, url, *args, **kwargs):
        super().__init__(url=url, *args, **kwargs)
        if isinstance(self.data, dict):
            self.headers.update({"Content-type": "application/json"})
        self._count = 0
        self._method = method
        self._req = None

    def __repr__(self):
        return f"Request(url={self.url}, method={self._method})"

    @classmethod
    def get_proxies_list(cls):
        if cls.PROXIES:
            print("já tem proxies")
            return cls.PROXIES
        try:
            cls.PROXIES = json.loads(cls("GET", PROXIES_URL).send_request().data)
        except:
            pass
        return cls.PROXIES

    def send_request(self, save_on=None, timeout=None, **kwargs):
        if "data" in kwargs:
            self._data = self.parser(kwargs.pop("data"))

        if "headers" in kwargs:
            headers = kwargs.pop("headers")
            assert isinstance(headers, dict), TypeError(
                    "Headers type is invalid. send a dict"
            )
            self.headers.update(headers)
        self._count += 1
        return HttpResponse(request=self, save_on_path=save_on, timeout=timeout)

    @property
    def urllib_req(self):
        return urllib_req.Request(
                url=self.url,
                data=self.parser(self.data),
                headers=self.headers,
                method=self._method,
        )

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

        return str(data).encode() if data else b""

    @classmethod
    def build_and_send(cls, method, url, data=None, port=None, headers=None, **kwargs):
        return cls(
                method=method, url=url, data=data, port=port, headers=headers
        ).send_request(**kwargs)
