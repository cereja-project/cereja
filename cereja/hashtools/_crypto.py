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
import json
import secrets
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
    Generate keystream using HMAC-based key expansion.
    This creates a cryptographically secure stream cipher.
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


def encrypt(data: Union[str, bytes, dict, list], password: Union[str, bytes]) -> str:
    """
    Encrypt data with password using stream cipher with HMAC authentication.

    Args:
        data: Data to encrypt (str, bytes, dict, or list).
        password: Password for encryption.

    Returns:
        Base64-encoded encrypted data with format: salt:iv:ciphertext:hmac.

    Raises:
        CryptoError: If encryption fails.
    """
    try:
        if isinstance(data, (dict, list)):
            data = json.dumps(data).encode("utf-8")
        elif isinstance(data, str):
            data = data.encode("utf-8")
        elif not isinstance(data, bytes):
            data = str(data).encode("utf-8")

        key, salt = generate_key(password)
        encryption_key = key[:16]
        hmac_key = key[16:]

        iv = secrets.token_bytes(16)
        keystream = _generate_keystream(encryption_key, iv, len(data))
        ciphertext = _xor_bytes(data, keystream)

        hmac_obj = hmac.new(hmac_key, salt + iv + ciphertext, hashlib.sha256)
        hmac_digest = hmac_obj.digest()

        result = salt + iv + ciphertext + hmac_digest
        return base64.b64encode(result).decode("ascii")

    except Exception as e:
        raise CryptoError(f"Encryption failed: {str(e)}") from e


def decrypt(encrypted_data: str, password: Union[str, bytes]) -> bytes:
    """
    Decrypt data encrypted with encrypt() function.

    Args:
        encrypted_data: Base64-encoded encrypted data.
        password: Password for decryption.

    Returns:
        Decrypted data as bytes.

    Raises:
        CryptoError: If decryption fails or authentication fails.
    """
    try:
        data = base64.b64decode(encrypted_data)

        if len(data) < 64:  # 16 (salt) + 16 (iv) + 0 (ciphertext) + 32 (hmac)
            raise CryptoError("Invalid encrypted data format")

        salt = data[:16]
        iv = data[16:32]
        hmac_digest = data[-32:]
        ciphertext = data[32:-32]

        key, _ = generate_key(password, salt)
        encryption_key = key[:16]
        hmac_key = key[16:]

        expected_hmac = hmac.new(hmac_key, salt + iv + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(hmac_digest, expected_hmac):
            raise CryptoError("Authentication failed: incorrect password or corrupted data")

        keystream = _generate_keystream(encryption_key, iv, len(ciphertext))
        return _xor_bytes(ciphertext, keystream)

    except CryptoError:
        raise
    except Exception as e:
        raise CryptoError(f"Decryption failed: {str(e)}") from e


def encrypt_file(file_path: str, password: Union[str, bytes], output_path: str = None) -> str:
    """
    Encrypt file contents.

    Args:
        file_path: Path to file to encrypt.
        password: Password for encryption.
        output_path: Path for encrypted file (if None, uses file_path + '.enc').

    Returns:
        Path to encrypted file.

    Raises:
        CryptoError: If encryption fails.
        FileNotFoundError: If input file doesn't exist.
    """
    try:
        with open(file_path, "rb") as f:
            data = f.read()

        encrypted = encrypt(data, password)

        if output_path is None:
            output_path = file_path + ".enc"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(encrypted)

        return output_path

    except FileNotFoundError:
        raise
    except Exception as e:
        raise CryptoError(f"File encryption failed: {str(e)}") from e


def decrypt_file(file_path: str, password: Union[str, bytes], output_path: str = None) -> str:
    """
    Decrypt file contents.

    Args:
        file_path: Path to encrypted file.
        password: Password for decryption.
        output_path: Path for decrypted file (if None, removes '.enc' extension).

    Returns:
        Path to decrypted file.

    Raises:
        CryptoError: If decryption fails.
        FileNotFoundError: If input file doesn't exist.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            encrypted_data = f.read()

        decrypted = decrypt(encrypted_data, password)

        if output_path is None:
            if file_path.endswith(".enc"):
                output_path = file_path[:-4]
            else:
                output_path = file_path + ".dec"

        with open(output_path, "wb") as f:
            f.write(decrypted)

        return output_path

    except FileNotFoundError:
        raise
    except Exception as e:
        raise CryptoError(f"File decryption failed: {str(e)}") from e