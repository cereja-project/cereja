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
import binascii
import hashlib
import base64 as _b64
import secrets
from typing import Union

from cereja import string_to_literal
from cereja.config.cj_types import Number

__all__ = ["md5", "base64_encode", "base64_decode", "is_base64"]


def md5(o: Union[list, dict, set, str, Number]):
    if not isinstance(o, str):
        o = repr(o)
    return hashlib.md5(o.encode()).hexdigest()


def base64_encode(content) -> bytes:
    if not isinstance(content, bytes):
        content = str(content).encode()
    return _b64.b64encode(content)


def base64_decode(content, eval_str=False):
    decoded_val = _b64.b64decode(content)
    decoded_val = string_to_literal(decoded_val.decode()) if eval_str else decoded_val
    return decoded_val


def is_base64(content):
    try:
        base64_decode(content)
        return True
    except binascii.Error:
        return False


def random_hash(n_bytes):
    return secrets.token_hex(nbytes=n_bytes)
