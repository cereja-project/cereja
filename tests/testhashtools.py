import unittest
import hashlib
from cereja import hashtools


class HashtoolsTest(unittest.TestCase):
    def test_base64_decode(self):
        self.assertEqual(
            hashtools.base64_decode(b"YWJjZGVmIGcgaCBpIGo=", eval_str=True),
            "abcdef g h i j",
        )
        self.assertEqual(
            hashtools.base64_decode(b"eydvaSc6ICd0dWRvIGJlbSd9", eval_str=True),
            {"oi": "tudo bem"},
        )
        self.assertEqual(
            hashtools.base64_decode(b"YWJjZGVmIGcgaCBpIGo="), b"abcdef g h i j"
        )

    def test_base64_encode(self):
        self.assertEqual(
            hashtools.base64_encode("abcdef g h i j"), b"YWJjZGVmIGcgaCBpIGo="
        )
        self.assertEqual(
            hashtools.base64_encode({"oi": "tudo bem"}), b"eydvaSc6ICd0dWRvIGJlbSd9"
        )

    def test_is_base64_valid(self):
        # Valid base64 strings
        self.assertTrue(hashtools.is_base64(b"YWJjZGVmIGcgaCBpIGo="))
        self.assertTrue(hashtools.is_base64(b"SGVsbG8gV29ybGQ="))
        self.assertTrue(hashtools.is_base64(b""))  # empty is valid base64

    def test_is_base64_invalid(self):
        # Invalid base64 (bad padding, invalid chars)
        self.assertFalse(hashtools.is_base64(b"not-valid-base64!!!"))

    def test_md5_string(self):
        expected = hashlib.md5(b"hello").hexdigest()
        self.assertEqual(hashtools.md5("hello"), expected)

    def test_md5_number(self):
        expected = hashlib.md5(b"42").hexdigest()
        self.assertEqual(hashtools.md5(42), expected)

    def test_md5_dict(self):
        d = {"key": "value"}
        expected = hashlib.md5(repr(d).encode()).hexdigest()
        self.assertEqual(hashtools.md5(d), expected)

    def test_md5_list(self):
        lst = [1, 2, 3]
        expected = hashlib.md5(repr(lst).encode()).hexdigest()
        self.assertEqual(hashtools.md5(lst), expected)

    def test_md5_consistency(self):
        # Same input always produces same hash
        self.assertEqual(hashtools.md5("test"), hashtools.md5("test"))

    def test_md5_different_inputs(self):
        self.assertNotEqual(hashtools.md5("hello"), hashtools.md5("world"))

    def test_random_hash_length(self):
        h = hashtools.random_hash(16)
        self.assertEqual(len(h), 32)  # hex: 16 bytes = 32 chars

    def test_random_hash_uniqueness(self):
        h1 = hashtools.random_hash(16)
        h2 = hashtools.random_hash(16)
        self.assertNotEqual(h1, h2)

    def test_random_hash_is_hex(self):
        h = hashtools.random_hash(8)
        int(h, 16)  # Should not raise ValueError


if __name__ == "__main__":
    unittest.main()
