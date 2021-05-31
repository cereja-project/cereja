from ._http import HttpRequest
from ._http import HttpResponse

__all__ = ['post', 'get', 'put', 'head', 'delete', 'connect', 'options', 'trace', 'patch']


def post(url, data=None, port=None, headers=None) -> HttpResponse:
    return HttpRequest.build_and_send(method='POST', url=url, data=data, port=port, headers=headers)


def get(url, data=None, port=None, headers=None) -> HttpResponse:
    return HttpRequest.build_and_send(method='GET', url=url, data=data, port=port, headers=headers)


def put(url, *args, **kwargs) -> HttpResponse:
    return HttpRequest.build_and_send(method='PUT', url=url, *args, **kwargs)


def head(url, *args, **kwargs) -> HttpResponse:
    return HttpRequest.build_and_send(method='HEAD', url=url, *args, **kwargs)


def delete(url, *args, **kwargs) -> HttpResponse:
    return HttpRequest.build_and_send(method='DELETE', url=url, *args, **kwargs)


def connect(url, *args, **kwargs) -> HttpResponse:
    return HttpRequest.build_and_send(method='CONNECT', url=url, *args, **kwargs)


def options(url, *args, **kwargs) -> HttpResponse:
    return HttpRequest.build_and_send(method='OPTIONS', url=url, *args, **kwargs)


def trace(url, *args, **kwargs) -> HttpResponse:
    return HttpRequest.build_and_send(method='TRACE', url=url, *args, **kwargs)


def patch(url, *args, **kwargs) -> HttpResponse:
    return HttpRequest.build_and_send(method='PATCH', url=url, *args, **kwargs)
