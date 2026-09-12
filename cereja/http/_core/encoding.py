"""Request body encoding."""

import json
from urllib.parse import urlencode


UNSET = object()


def encode_content(*, json_value=UNSET, data=UNSET, content=UNSET):
    supplied = sum(value is not UNSET for value in (json_value, data, content))
    if supplied > 1:
        raise ValueError("json, data and content are mutually exclusive")
    if json_value is not UNSET:
        return json.dumps(json_value, separators=(",", ":"), ensure_ascii=False).encode("utf-8"), "application/json"
    if data is not UNSET:
        if hasattr(data, "items"):
            return urlencode(data, doseq=True).encode("ascii"), "application/x-www-form-urlencoded"
        if isinstance(data, str):
            return data.encode("utf-8"), "application/x-www-form-urlencoded"
        raise TypeError("data must be a mapping or string")
    if content is not UNSET:
        if isinstance(content, str):
            return content.encode("utf-8"), None
        if isinstance(content, (bytes, bytearray, memoryview)):
            return bytes(content), None
        raise TypeError("content must be str or bytes-like")
    return None, None
