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
from typing import Any, Union

from cereja import string_to_literal
from cereja.config.cj_types import T_NUMBER

__all__ = ["md5", "base64_encode", "base64_decode", "is_base64", "random_hash"]


def md5(o: Union[list, dict, set, str, T_NUMBER]) -> str:
    """Return the MD5 hex digest of the given object.

    Note: MD5 is not suitable for cryptographic purposes. Use SHA-256
    or stronger for security-sensitive hashing.
    """
    if not isinstance(o, str):
        o = repr(o)
    return hashlib.md5(o.encode()).hexdigest()


def base64_encode(content: Any) -> bytes:
    """Encode content to base64 bytes."""
    if not isinstance(content, bytes):
        content = str(content).encode()
    return _b64.b64encode(content)


def base64_decode(content: Union[str, bytes], eval_str: bool = False) -> Union[bytes, Any]:
    """Decode base64 content. If eval_str is True, attempt to evaluate the decoded string as a Python literal."""
    decoded_val = _b64.b64decode(content)
    decoded_val = string_to_literal(decoded_val.decode()) if eval_str else decoded_val
    return decoded_val


def is_base64(content: Union[str, bytes]) -> bool:
    """Check if content is valid base64."""
    try:
        base64_decode(content)
        return True
    except binascii.Error:
        return False


def random_hash(n_bytes: int) -> str:
    """Generate a random hex string with n_bytes of randomness."""
    return secrets.token_hex(nbytes=n_bytes)
