"""Pure request preparation."""

from .encoding import UNSET, encode_content
from .syntax import validate_token
from ..headers import Headers
from ..models import Request
from ..url import URL


def prepare_request(method, url, *, base_url=None, params=None, headers=None,
                    json=UNSET, data=UNSET, content=UNSET):
    parsed = URL.parse(url, base_url=base_url).with_params(params)
    method = validate_token(str(method).upper(), label="method")
    body, content_type = encode_content(json_value=json, data=data, content=content)
    result_headers = Headers(headers)
    if "host" not in result_headers:
        result_headers.set("Host", parsed.authority)
    if body is not None and "content-length" not in result_headers:
        result_headers.set("Content-Length", str(len(body)))
    if content_type and "content-type" not in result_headers:
        result_headers.set("Content-Type", content_type)
    return Request(method, parsed, result_headers, body)
