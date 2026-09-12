"""HTTP exception hierarchy for Cereja."""


class HTTPError(Exception):
    """Base class for Cereja HTTP errors."""


class RequestError(HTTPError):
    """A request could not be completed at the transport layer."""


class ConnectError(RequestError):
    pass


class TimeoutError(RequestError):
    pass


class ConnectTimeout(TimeoutError):
    pass


class ReadTimeout(TimeoutError):
    pass


class WriteTimeout(TimeoutError):
    pass


class PoolTimeout(TimeoutError):
    pass


class ProtocolError(RequestError):
    pass


class TLSFailure(RequestError):
    pass


class HTTPStatusError(HTTPError):
    def __init__(self, message, *, request=None, response=None):
        super().__init__(message)
        self.request = request
        self.response = response


class DecodeError(HTTPError):
    pass


class BodyLimitExceeded(HTTPError):
    pass
