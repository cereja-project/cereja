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
import hmac
import hashlib
import secrets
import base64
from typing import Union, Tuple

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


def _pad(data: bytes, block_size: int = 16) -> bytes:
    """Apply PKCS7 padding to data."""
    padding_length = block_size - (len(data) % block_size)
    padding = bytes([padding_length] * padding_length)
    return data + padding


def _unpad(data: bytes) -> bytes:
    """Remove PKCS7 padding from data."""
    if not data:
        raise CryptoError("Cannot unpad empty data")
    padding_length = data[-1]
    if padding_length > len(data) or padding_length == 0:
        raise CryptoError("Invalid padding")
    # Verify all padding bytes are correct
    if data[-padding_length:] != bytes([padding_length] * padding_length):
        raise CryptoError("Invalid padding")
    return data[:-padding_length]


def _xor_bytes(a: bytes, b: bytes) -> bytes:
    """XOR two byte strings."""
    return bytes(x ^ y for x, y in zip(a, b))


def _generate_keystream(key: bytes, iv: bytes, length: int) -> bytes:
    """
    Generate keystream using HMAC-based key expansion.
    This creates a cryptographically secure stream cipher.
    """
    keystream = b''
    counter = 0
    
    while len(keystream) < length:
        # Use HMAC with counter for key expansion
        h = hmac.new(key, iv + counter.to_bytes(4, 'big'), hashlib.sha256)
        keystream += h.digest()
        counter += 1
    
    return keystream[:length]


def generate_key(password: Union[str, bytes], salt: bytes = None, iterations: int = 100000) -> Tuple[bytes, bytes]:
    """
    Generate encryption key from password using PBKDF2-HMAC-SHA256.
    
    Args:
        password: Password string or bytes
        salt: Salt bytes (if None, generates random salt)
        iterations: Number of PBKDF2 iterations (default: 100000)
    
    Returns:
        Tuple of (key, salt)
    """
    if isinstance(password, str):
        password = password.encode('utf-8')
    
    if salt is None:
        salt = secrets.token_bytes(16)
    
    key = hashlib.pbkdf2_hmac('sha256', password, salt, iterations, dklen=32)
    return key, salt


def encrypt(data: Union[str, bytes, dict, list], password: Union[str, bytes]) -> str:
    """
    Encrypt data with password using stream cipher with HMAC authentication.
    
    Args:
        data: Data to encrypt (str, bytes, dict, or list)
        password: Password for encryption
    
    Returns:
        Base64-encoded encrypted data with format: salt:iv:ciphertext:hmac
    
    Raises:
        CryptoError: If encryption fails
    """
    try:
        # Convert data to bytes
        if isinstance(data, (dict, list)):
            data = str(data).encode('utf-8')
        elif isinstance(data, str):
            data = data.encode('utf-8')
        elif not isinstance(data, bytes):
            data = str(data).encode('utf-8')
        
        # Generate key and salt
        key, salt = generate_key(password)
        encryption_key = key[:16]  # Use first 16 bytes for encryption
        hmac_key = key[16:]  # Use remaining 16 bytes for HMAC
        
        # Generate random IV
        iv = secrets.token_bytes(16)
        
        # Generate keystream and encrypt
        keystream = _generate_keystream(encryption_key, iv, len(data))
        ciphertext = _xor_bytes(data, keystream)
        
        # Calculate HMAC
        hmac_obj = hmac.new(hmac_key, salt + iv + ciphertext, hashlib.sha256)
        hmac_digest = hmac_obj.digest()
        
        # Combine: salt:iv:ciphertext:hmac
        result = salt + iv + ciphertext + hmac_digest
        
        # Encode to base64
        return base64.b64encode(result).decode('ascii')
    
    except Exception as e:
        raise CryptoError(f"Encryption failed: {str(e)}")


def decrypt(encrypted_data: str, password: Union[str, bytes]) -> bytes:
    """
    Decrypt data encrypted with encrypt() function.
    
    Args:
        encrypted_data: Base64-encoded encrypted data
        password: Password for decryption
    
    Returns:
        Decrypted data as bytes
    
    Raises:
        CryptoError: If decryption fails or authentication fails
    """
    try:
        # Decode from base64
        data = base64.b64decode(encrypted_data)
        
        # Extract components
        if len(data) < 64:  # Minimum: 16 (salt) + 16 (iv) + 0 (ciphertext) + 32 (hmac)
            raise CryptoError("Invalid encrypted data format")
        
        salt = data[:16]
        iv = data[16:32]
        hmac_digest = data[-32:]
        ciphertext = data[32:-32]
        
        # Regenerate key
        key, _ = generate_key(password, salt)
        encryption_key = key[:16]
        hmac_key = key[16:]
        
        # Verify HMAC
        expected_hmac = hmac.new(hmac_key, salt + iv + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(hmac_digest, expected_hmac):
            raise CryptoError("Authentication failed: incorrect password or corrupted data")
        
        # Decrypt using stream cipher
        keystream = _generate_keystream(encryption_key, iv, len(ciphertext))
        plaintext = _xor_bytes(ciphertext, keystream)
        
        return plaintext
    
    except CryptoError:
        raise
    except Exception as e:
        raise CryptoError(f"Decryption failed: {str(e)}")


def encrypt_file(file_path: str, password: Union[str, bytes], output_path: str = None) -> str:
    """
    Encrypt file contents.
    
    Args:
        file_path: Path to file to encrypt
        password: Password for encryption
        output_path: Path for encrypted file (if None, uses file_path + '.enc')
    
    Returns:
        Path to encrypted file
    
    Raises:
        CryptoError: If encryption fails
        FileNotFoundError: If input file doesn't exist
    """
    try:
        # Read file
        with open(file_path, 'rb') as f:
            data = f.read()
        
        # Encrypt
        encrypted = encrypt(data, password)
        
        # Determine output path
        if output_path is None:
            output_path = file_path + '.enc'
        
        # Write encrypted file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(encrypted)
        
        return output_path
    
    except FileNotFoundError:
        raise
    except Exception as e:
        raise CryptoError(f"File encryption failed: {str(e)}")


def decrypt_file(file_path: str, password: Union[str, bytes], output_path: str = None) -> str:
    """
    Decrypt file contents.
    
    Args:
        file_path: Path to encrypted file
        password: Password for decryption
        output_path: Path for decrypted file (if None, removes '.enc' extension)
    
    Returns:
        Path to decrypted file
    
    Raises:
        CryptoError: If decryption fails
        FileNotFoundError: If input file doesn't exist
    """
    try:
        # Read encrypted file
        with open(file_path, 'r', encoding='utf-8') as f:
            encrypted_data = f.read()
        
        # Decrypt
        decrypted = decrypt(encrypted_data, password)
        
        # Determine output path
        if output_path is None:
            if file_path.endswith('.enc'):
                output_path = file_path[:-4]
            else:
                output_path = file_path + '.dec'
        
        # Write decrypted file
        with open(output_path, 'wb') as f:
            f.write(decrypted)
        
        return output_path
    
    except FileNotFoundError:
        raise
    except Exception as e:
        raise CryptoError(f"File decryption failed: {str(e)}")
