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
