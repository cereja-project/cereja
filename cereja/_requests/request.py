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
from ._http import HttpRequest, HttpResponse

__all__ = ['post', 'get', 'put', 'head', 'delete', 'connect', 'options', 'trace', 'patch']


def post(url, data=None, headers=None, **kwargs) -> HttpResponse:
    """
    The POST method is used to submit an entity to the specified resource, often causing a change in state or side
    effects on the server.

    """
    return HttpRequest.build_and_send(method='POST', url=url, data=data, headers=headers, **kwargs)


def get(url, data=None, headers=None, **kwargs) -> HttpResponse:
    """
    The GET method requests a representation of the specified resource. Requests using GET should only retrieve data.
    """
    return HttpRequest.build_and_send(method='GET', url=url, data=data, headers=headers, **kwargs)


def put(url, **kwargs) -> HttpResponse:
    """
    The PUT method replaces all current representations of the target resource with the request payload.
    """
    return HttpRequest.build_and_send(method='PUT', url=url, **kwargs)


def head(url, **kwargs) -> HttpResponse:
    """
    The HEAD method asks for a response identical to that of a GET request, but without the response body.
    """
    return HttpRequest.build_and_send(method='HEAD', url=url, **kwargs)


def delete(url, **kwargs) -> HttpResponse:
    """
    The DELETE method deletes the specified resource.
    """
    return HttpRequest.build_and_send(method='DELETE', url=url, **kwargs)


def connect(url, **kwargs) -> HttpResponse:
    """
    The CONNECT method establishes a tunnel to the server identified by the target resource.
    """
    return HttpRequest.build_and_send(method='CONNECT', url=url, **kwargs)


def options(url, **kwargs) -> HttpResponse:
    """
    The OPTIONS method is used to describe the communication options for the target resource.
    """
    return HttpRequest.build_and_send(method='OPTIONS', url=url, **kwargs)


def trace(url, **kwargs) -> HttpResponse:
    """
    The TRACE method performs a message loop-back test along the path to the target resource.
    """
    return HttpRequest.build_and_send(method='TRACE', url=url, **kwargs)


def patch(url, **kwargs) -> HttpResponse:
    """
    The PATCH method is used to apply partial modifications to a resource.
    """
    return HttpRequest.build_and_send(method='PATCH', url=url, **kwargs)
