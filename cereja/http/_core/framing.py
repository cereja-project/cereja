"""Shared HTTP/1.1 response framing validation."""

from ..errors import ProtocolError


def response_framing(method, status_code, headers, http_version):
    """Return ``(mode, remaining, reusable)`` for one HTTP response.

    The implementation is deliberately strict about ambiguous framing. Cereja
    supports identity bodies, Content-Length, and a single final ``chunked``
    transfer coding; unsupported or conflicting framing is rejected instead of
    guessing.
    """
    connection = (headers.get("connection") or "").lower()
    reusable = http_version == "HTTP/1.1" and connection != "close"

    if method == "HEAD" or status_code in {204, 304} or 100 <= status_code < 200:
        return "none", 0, reusable

    transfer_values = headers.get_list("transfer-encoding")
    length_values = headers.get_list("content-length")

    if transfer_values:
        if length_values:
            raise ProtocolError("Ambiguous response framing: both Transfer-Encoding and Content-Length")
        codings = [
            token.strip().lower()
            for value in transfer_values
            for token in value.split(",")
        ]
        if not codings or any(not coding for coding in codings):
            raise ProtocolError("Invalid Transfer-Encoding")
        if codings != ["chunked"]:
            raise ProtocolError(f"Unsupported Transfer-Encoding: {', '.join(codings)}")
        return "chunked", None, reusable

    if length_values:
        if len(length_values) != 1:
            raise ProtocolError("Multiple Content-Length headers are not accepted")
        value = length_values[0].strip()
        if not value.isdigit():
            raise ProtocolError("Invalid Content-Length")
        return "length", int(value), reusable

    return "close", None, False
