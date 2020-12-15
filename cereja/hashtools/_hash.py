import binascii
import hashlib
import base64 as _b64
from typing import Union
import ast

from cereja.config.cj_types import Number

__all__ = ['md5', 'base64_encode', 'base64_decode', 'is_base64']


def md5(o: Union[list, dict, set, str, Number]):
    if not isinstance(o, str):
        o = repr(o)
    return hashlib.md5(o.encode()).hexdigest()


def base64_encode(content: Union[list, dict, set, Number]):
    assert isinstance(content,
                      (list, dict, tuple, set, int, float, bytes,
                       complex)), f"Type of content {type(content)} is not valid."
    return _b64.b64encode(repr(content).encode()).decode()


def base64_decode(content):
    decode_val = _b64.b64decode(content).decode()
    if isinstance(decode_val, str):
        try:
            decode_val = ast.literal_eval(decode_val)
            return decode_val if isinstance(decode_val, (int, float, complex)) else decode_val
        except:
            pass
    return decode_val


def is_base64(content):
    try:
        base64_decode(content)
        return True
    except binascii.Error:
        return False
