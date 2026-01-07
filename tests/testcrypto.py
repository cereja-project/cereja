import unittest
import os
import tempfile
from cereja import hashtools


class CryptoTest(unittest.TestCase):
    """Test suite for cryptography utilities."""
    
    def test_encrypt_decrypt_string(self):
        """Test basic string encryption and decryption."""
        original = "Hello, Cereja! 🍒"
        password = "my_secure_password"
        
        # Encrypt
        encrypted = hashtools.encrypt(original, password)
        self.assertIsInstance(encrypted, str)
        self.assertNotEqual(encrypted, original)
        
        # Decrypt
        decrypted = hashtools.decrypt(encrypted, password)
        self.assertEqual(decrypted.decode('utf-8'), original)
    
    def test_encrypt_decrypt_bytes(self):
        """Test bytes encryption and decryption."""
        original = b"Binary data \x00\x01\x02\xff"
        password = "test_password"
        
        encrypted = hashtools.encrypt(original, password)
        decrypted = hashtools.decrypt(encrypted, password)
        
        self.assertEqual(decrypted, original)
    
    def test_encrypt_decrypt_dict(self):
        """Test dictionary encryption and decryption."""
        original = {"name": "Cereja", "type": "library", "emoji": "🍒"}
        password = "dict_password"
        
        encrypted = hashtools.encrypt(original, password)
        decrypted = hashtools.decrypt(encrypted, password)
        
        # Compare string representation
        self.assertEqual(decrypted.decode('utf-8'), str(original))
    
    def test_encrypt_decrypt_list(self):
        """Test list encryption and decryption."""
        original = [1, 2, 3, "cereja", True, None]
        password = "list_password"
        
        encrypted = hashtools.encrypt(original, password)
        decrypted = hashtools.decrypt(encrypted, password)
        
        self.assertEqual(decrypted.decode('utf-8'), str(original))
    
    def test_wrong_password(self):
        """Test that wrong password raises error."""
        original = "Secret message"
        password = "correct_password"
        wrong_password = "wrong_password"
        
        encrypted = hashtools.encrypt(original, password)
        
        with self.assertRaises(hashtools.CryptoError) as context:
            hashtools.decrypt(encrypted, wrong_password)
        
        self.assertIn("Authentication failed", str(context.exception))
    
    def test_empty_data(self):
        """Test encryption of empty data."""
        original = ""
        password = "password"
        
        encrypted = hashtools.encrypt(original, password)
        decrypted = hashtools.decrypt(encrypted, password)
        
        self.assertEqual(decrypted.decode('utf-8'), original)
    
    def test_long_data(self):
        """Test encryption of long data."""
        original = "A" * 10000  # 10KB of data
        password = "long_password"
        
        encrypted = hashtools.encrypt(original, password)
        decrypted = hashtools.decrypt(encrypted, password)
        
        self.assertEqual(decrypted.decode('utf-8'), original)
    
    def test_special_characters(self):
        """Test encryption with special characters."""
        original = "Special chars: !@#$%^&*()_+-=[]{}|;':\",./<>?`~\n\t\r"
        password = "special_password"
        
        encrypted = hashtools.encrypt(original, password)
        decrypted = hashtools.decrypt(encrypted, password)
        
        self.assertEqual(decrypted.decode('utf-8'), original)
    
    def test_unicode_data(self):
        """Test encryption with unicode characters."""
        original = "Unicode: 你好世界 مرحبا العالم Привет мир 🌍🌎🌏"
        password = "unicode_password"
        
        encrypted = hashtools.encrypt(original, password)
        decrypted = hashtools.decrypt(encrypted, password)
        
        self.assertEqual(decrypted.decode('utf-8'), original)
    
    def test_different_passwords_different_output(self):
        """Test that different passwords produce different ciphertext."""
        original = "Same message"
        password1 = "password1"
        password2 = "password2"
        
        encrypted1 = hashtools.encrypt(original, password1)
        encrypted2 = hashtools.encrypt(original, password2)
        
        self.assertNotEqual(encrypted1, encrypted2)
    
    def test_same_data_different_output(self):
        """Test that encrypting same data twice produces different output (due to random IV)."""
        original = "Same message"
        password = "same_password"
        
        encrypted1 = hashtools.encrypt(original, password)
        encrypted2 = hashtools.encrypt(original, password)
        
        # Should be different due to random IV
        self.assertNotEqual(encrypted1, encrypted2)
        
        # But both should decrypt to same value
        decrypted1 = hashtools.decrypt(encrypted1, password)
        decrypted2 = hashtools.decrypt(encrypted2, password)
        self.assertEqual(decrypted1, decrypted2)
    
    def test_invalid_encrypted_data(self):
        """Test that invalid encrypted data raises error."""
        password = "password"
        
        # Too short data
        with self.assertRaises(hashtools.CryptoError):
            hashtools.decrypt("invalid", password)
        
        # Corrupted data
        with self.assertRaises(hashtools.CryptoError):
            hashtools.decrypt("YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXo=", password)
    
    def test_generate_key(self):
        """Test key generation."""
        password = "test_password"
        
        # Generate key with random salt
        key1, salt1 = hashtools.generate_key(password)
        self.assertEqual(len(key1), 32)  # 256 bits
        self.assertEqual(len(salt1), 16)  # 128 bits
        
        # Generate key with same salt should produce same key
        key2, salt2 = hashtools.generate_key(password, salt=salt1)
        self.assertEqual(key1, key2)
        self.assertEqual(salt1, salt2)
        
        # Different salt should produce different key
        key3, salt3 = hashtools.generate_key(password)
        self.assertNotEqual(key1, key3)
        self.assertNotEqual(salt1, salt3)
    
    def test_encrypt_file(self):
        """Test file encryption."""
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            temp_file = f.name
            f.write("This is a test file for encryption.\nLine 2\nLine 3")
        
        try:
            password = "file_password"
            
            # Encrypt file
            encrypted_file = hashtools.encrypt_file(temp_file, password)
            self.assertTrue(os.path.exists(encrypted_file))
            self.assertEqual(encrypted_file, temp_file + '.enc')
            
            # Decrypt file
            decrypted_file = hashtools.decrypt_file(encrypted_file, password)
            self.assertTrue(os.path.exists(decrypted_file))
            
            # Verify content
            with open(decrypted_file, 'r') as f:
                content = f.read()
            self.assertEqual(content, "This is a test file for encryption.\nLine 2\nLine 3")
            
            # Cleanup
            os.remove(encrypted_file)
            os.remove(decrypted_file)
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    def test_encrypt_file_custom_output(self):
        """Test file encryption with custom output path."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            temp_file = f.name
            f.write("Custom output test")
        
        try:
            password = "custom_password"
            custom_output = temp_file + '.encrypted'
            
            # Encrypt with custom output
            encrypted_file = hashtools.encrypt_file(temp_file, password, output_path=custom_output)
            self.assertEqual(encrypted_file, custom_output)
            self.assertTrue(os.path.exists(custom_output))
            
            # Decrypt with custom output
            custom_decrypt = temp_file + '.decrypted'
            decrypted_file = hashtools.decrypt_file(encrypted_file, password, output_path=custom_decrypt)
            self.assertEqual(decrypted_file, custom_decrypt)
            
            # Verify content
            with open(decrypted_file, 'r') as f:
                content = f.read()
            self.assertEqual(content, "Custom output test")
            
            # Cleanup
            os.remove(custom_output)
            os.remove(custom_decrypt)
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    def test_encrypt_file_wrong_password(self):
        """Test file decryption with wrong password."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            temp_file = f.name
            f.write("Secret file content")
        
        try:
            password = "correct_password"
            wrong_password = "wrong_password"
            
            # Encrypt file
            encrypted_file = hashtools.encrypt_file(temp_file, password)
            
            # Try to decrypt with wrong password
            with self.assertRaises(hashtools.CryptoError):
                hashtools.decrypt_file(encrypted_file, wrong_password)
            
            # Cleanup
            os.remove(encrypted_file)
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    def test_encrypt_nonexistent_file(self):
        """Test encryption of non-existent file."""
        with self.assertRaises(FileNotFoundError):
            hashtools.encrypt_file("nonexistent_file.txt", "password")
    
    def test_decrypt_nonexistent_file(self):
        """Test decryption of non-existent file."""
        with self.assertRaises(FileNotFoundError):
            hashtools.decrypt_file("nonexistent_file.enc", "password")


if __name__ == "__main__":
    unittest.main()
