"""Source fingerprint portability without accepting changed Python content."""
import hashlib
import unittest

from verify import source_fingerprint_match


def digest(data):
    return hashlib.sha256(data).hexdigest()


class SourceFingerprintTests(unittest.TestCase):
    def test_exact_bytes_are_distinguished(self):
        for data in (b'value = 1\n', b'value = 1\r\n'):
            with self.subTest(data=data):
                self.assertEqual(source_fingerprint_match(data, digest(data)), 'exact')

    def test_git_newline_conversion_is_explicit_in_both_directions(self):
        lf = b'value = 1\nprint(value)\n'
        crlf = b'value = 1\r\nprint(value)\r\n'
        self.assertEqual(source_fingerprint_match(lf, digest(crlf)), 'line_endings_only')
        self.assertEqual(source_fingerprint_match(crlf, digest(lf)), 'line_endings_only')

    def test_source_edit_is_rejected_after_newline_conversion(self):
        self.assertIsNone(source_fingerprint_match(b'value = 2\n', digest(b'value = 1\r\n')))

    def test_other_whitespace_and_lone_carriage_return_are_not_normalized(self):
        expected = digest(b'value = 1\r\n')
        for changed in (b'value  = 1\n', b'value = 1 \n', b'value = 1\r'):
            with self.subTest(changed=changed):
                self.assertIsNone(source_fingerprint_match(changed, expected))


if __name__ == '__main__':
    unittest.main()
