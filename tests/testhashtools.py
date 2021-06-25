import unittest
from cereja import hashtools


class HashtoolsTest(unittest.TestCase):

    def test_base64_decode(self):
        self.assertEqual(hashtools.base64_decode(b'YWJjZGVmIGcgaCBpIGo='), 'abcdef g h i j')
        self.assertEqual(hashtools.base64_decode(b'eydvaSc6ICd0dWRvIGJlbSd9'), {'oi': 'tudo bem'})

    def test_base64_encode(self):
        self.assertEqual(hashtools.base64_encode('abcdef g h i j'), b'YWJjZGVmIGcgaCBpIGo=')
        self.assertEqual(hashtools.base64_encode({'oi': 'tudo bem'}), b'eydvaSc6ICd0dWRvIGJlbSd9')

    def test_is_base64(self):
        pass

    def test_md5(self):
        pass


if __name__ == '__main__':
    unittest.main()
