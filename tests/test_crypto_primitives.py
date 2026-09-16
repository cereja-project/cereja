"""Compare optimized primitives with the historical byte-level operations."""
import hashlib
import hmac
import random
import unittest

from cereja.hashtools import _crypto


class CryptoPrimitivesTest(unittest.TestCase):
    def test_xor_boundaries_and_unequal_lengths(self):
        sizes = (0, 1, 31, 32, 33, 65535, 65536, 65537, 131073)
        rng = random.Random(20260915)
        for left in sizes:
            for right in sizes:
                for fill in (0, 255, None):
                    a = rng.randbytes(left) if fill is None else bytes([fill]) * left
                    b = rng.randbytes(right) if fill is None else bytes([fill]) * right
                    with self.subTest(left=left, right=right, fill=fill):
                        expected = bytes(x ^ y for x, y in zip(a, b))
                        self.assertEqual(_crypto._xor_bytes(a, b), expected)
                        self.assertIsInstance(_crypto._xor_bytes(a, b), bytes)

    def test_xor_seeded_random_inputs(self):
        rng = random.Random(20260916)
        for _ in range(100):
            a, b = rng.randbytes(rng.randrange(5000)), rng.randbytes(rng.randrange(5000))
            self.assertEqual(_crypto._xor_bytes(a, b), bytes(x ^ y for x, y in zip(a, b)))

    def test_keystream_matches_independent_block_reference(self):
        rng = random.Random(20260915)
        for length in (0, 1, 31, 32, 33, 63, 64, 65, 65535, 65536, 65537):
            for key_size in (0, 16, 64, 65, 100):
                key, iv = rng.randbytes(key_size), rng.randbytes(16)
                expected = b''.join(
                    hmac.new(key, iv + counter.to_bytes(4, 'big'), hashlib.sha256).digest()
                    for counter in range((length + 31) // 32)
                )[:length]
                with self.subTest(length=length, key_size=key_size):
                    self.assertEqual(_crypto._generate_keystream(key, iv, length), expected)
