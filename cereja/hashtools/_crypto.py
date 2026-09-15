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
import base64
import hashlib
import hmac
import os
import secrets
import tempfile
from typing import Tuple, Union

__all__ = [
    "encrypt",
    "decrypt",
    "generate_key",
    "encrypt_file",
    "decrypt_file",
    "CryptoError",
]


class CryptoError(Exception):
    """Exception raised for cryptography-related errors."""
    pass


def _xor_bytes(a: bytes, b: bytes) -> bytes:
    """XOR two byte strings."""
    return bytes(x ^ y for x, y in zip(a, b))


def _generate_keystream(key: bytes, iv: bytes, length: int) -> bytes:
    """
    Generate the keystream used by the historical Cereja format.
    """
    chunks = []
    counter = 0
    remaining = length

    while remaining > 0:
        h = hmac.new(key, iv + counter.to_bytes(4, "big"), hashlib.sha256)
        digest = h.digest()
        chunks.append(digest)
        remaining -= len(digest)
        counter += 1

    return b"".join(chunks)[:length]


def generate_key(
    password: Union[str, bytes],
    salt: bytes = None,
    iterations: int = 100000,
) -> Tuple[bytes, bytes]:
    """
    Generate encryption key from password using PBKDF2-HMAC-SHA256.

    Args:
        password: Password string or bytes.
        salt: Salt bytes (if None, generates random 16-byte salt).
        iterations: Number of PBKDF2 iterations (default: 100000).

    Returns:
        Tuple of (key, salt).
    """
    if isinstance(password, str):
        password = password.encode("utf-8")

    if salt is None:
        salt = secrets.token_bytes(16)

    key = hashlib.pbkdf2_hmac("sha256", password, salt, iterations, dklen=32)
    return key, salt


_AUTH_ERROR = "Authentication failed: incorrect password or corrupted data"


def encrypt(data: Union[str, bytes, dict, list], password: Union[str, bytes]) -> str:
    """Encrypt using the historical Cereja format and only the standard library.

    Return Base64 of salt + IV + ciphertext + HMAC. Non-bytes values use UTF-8
    encoded ``str(data)`` for compatibility; serialize JSON explicitly if needed.
    This custom construction has not undergone an independent security audit.
    """
    try:
        if not isinstance(data, bytes):
            data = str(data).encode("utf-8")
        key, salt = generate_key(password)
        iv = secrets.token_bytes(16)
        ciphertext = _xor_bytes(data, _generate_keystream(key[:16], iv, len(data)))
        payload = salt + iv + ciphertext
        tag = hmac.new(key[16:], payload, hashlib.sha256).digest()
        return base64.b64encode(payload + tag).decode("ascii")
    except CryptoError:
        raise
    except Exception:
        raise CryptoError("Encryption failed") from None


def decrypt(encrypted_data: str, password: Union[str, bytes]) -> bytes:
    """Authenticate and decrypt the historical unversioned Cereja format.

    Base64 is validated strictly. Authentication completes before generating
    the keystream or returning plaintext. No external dependencies are required.
    """
    try:
        if not isinstance(encrypted_data, str):
            raise CryptoError("Encrypted data must be a string")
        data = base64.b64decode(encrypted_data, validate=True)
        if len(data) < 64:
            raise CryptoError("Invalid encrypted data format")
        salt, iv = data[:16], data[16:32]
        ciphertext, tag = data[32:-32], data[-32:]
        key, _ = generate_key(password, salt)
        expected = hmac.new(key[16:], salt + iv + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected):
            raise CryptoError(_AUTH_ERROR)
        return _xor_bytes(ciphertext, _generate_keystream(key[:16], iv, len(ciphertext)))
    except CryptoError:
        raise
    except Exception:
        raise CryptoError("Decryption failed") from None


def _check_destination(source, destination, overwrite):
    if os.path.normcase(os.path.realpath(source)) == os.path.normcase(os.path.realpath(destination)):
        raise CryptoError("Input and output must be different files")
    if os.path.exists(destination) and os.path.samefile(source, destination):
        raise CryptoError("Input and output must be different files")
    if not overwrite and os.path.lexists(destination):
        raise CryptoError("Output already exists; use overwrite=True")


def _publish(destination, data, overwrite):
    # The temporary stays on the destination filesystem. link() creates the
    # destination exclusively; replace() is used only with explicit permission.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=os.path.dirname(os.path.abspath(destination)),
                                         prefix=".cereja-crypto-", delete=False) as stream:
            temporary = stream.name
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temporary, destination)
        else:
            os.link(temporary, destination)
    finally:
        if temporary is not None and os.path.lexists(temporary):
            os.unlink(temporary)


def _transform_file(file_path, password, output_path, overwrite, *, decrypting):
    try:
        source = os.fsdecode(file_path)
        destination = os.fsdecode(output_path) if output_path is not None else (
            source[:-4] if decrypting and source.endswith(".enc")
            else source + (".dec" if decrypting else ".enc")
        )
        # Open first to preserve FileNotFoundError for a missing input.
        with open(source, "rb") as stream:
            _check_destination(source, destination, overwrite)
            data = stream.read()
        result = (decrypt(data.decode("ascii"), password) if decrypting
                  else encrypt(data, password).encode("ascii"))
        _check_destination(source, destination, overwrite)
        _publish(destination, result, overwrite)
        return destination
    except (CryptoError, FileNotFoundError):
        raise
    except Exception:
        raise CryptoError("File decryption failed" if decrypting else "File encryption failed") from None


def encrypt_file(file_path: str, password: Union[str, bytes], output_path: str = None,
                 *, overwrite: bool = False) -> str:
    """Encrypt a whole file and publish its output atomically.

    Default output is input + '.enc'. Existing outputs require ``overwrite=True``;
    aliases of the input are always rejected. Raises CryptoError on failure and
    FileNotFoundError for missing paths.
    """
    return _transform_file(file_path, password, output_path, overwrite, decrypting=False)


def decrypt_file(file_path: str, password: Union[str, bytes], output_path: str = None,
                 *, overwrite: bool = False) -> str:
    """Authenticate a whole file before publishing plaintext atomically.

    Default output removes '.enc', or appends '.dec'. Existing outputs require
    ``overwrite=True``; aliases of the input are always rejected. Raises
    CryptoError on failure and FileNotFoundError for missing paths.
    """
    return _transform_file(file_path, password, output_path, overwrite, decrypting=True)
