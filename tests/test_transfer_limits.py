"""Optional bounded transfer policy, independent from HTTP framing tests."""
from contextlib import contextmanager
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cereja.transfers import download


class Response:
    status_code = 200
    def __init__(self, total, chunks):
        self.headers = {} if total is None else {'content-length': str(total)}
        self.chunks = chunks
    def iter_bytes(self, size):
        yield from self.chunks


class Client:
    def __init__(self, response):
        self.response = response
    @contextmanager
    def stream(self, *args, **kwargs):
        yield self.response


class TransferLimitsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.target = self.root / 'result'

    def transfer(self, total, chunks, **kwargs):
        return download('http://fixture.invalid', self.target,
                        client=Client(Response(total, chunks)), **kwargs)

    def test_known_and_unknown_limits_abort_before_publication(self):
        for total in (None, 100):
            with self.assertRaises(ValueError):
                self.transfer(total, [b'12345'], max_bytes=4, overwrite=False)
            self.assertFalse(self.target.exists())
            self.assertEqual(list(self.root.iterdir()), [])

    def test_misleading_length_refused_with_bounded_policy(self):
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            self.transfer(8, [b'abc'], max_bytes=10, overwrite=False)
        self.assertFalse(self.target.exists())

    def test_exclusive_commit_race_keeps_other_writer(self):
        def race():
            self.target.write_bytes(b'keep')
        with self.assertRaises(FileExistsError):
            self.transfer(3, [b'abc'], max_bytes=10, overwrite=False, before_commit=race)
        self.assertEqual(self.target.read_bytes(), b'keep')
        self.assertEqual(list(self.root.iterdir()), [self.target])

    def test_commit_and_flush_failure_clean_staging(self):
        for operation in ('os.link', 'os.fsync'):
            with patch('cereja.transfers.sinks.' + operation, side_effect=OSError('fixture')):
                with self.assertRaises(OSError):
                    self.transfer(None, [b'abc'], max_bytes=10, overwrite=False)
            self.assertEqual(list(self.root.iterdir()), [])

    def test_existing_default_can_replace_target(self):
        self.target.write_bytes(b'old')
        self.transfer(3, [b'abc'])
        self.assertEqual(self.target.read_bytes(), b'abc')

    def test_invalid_policy_rejected_before_client_acquisition(self):
        with patch('cereja.transfers.download.Client', side_effect=AssertionError('client acquired')):
            for kwargs in ({'overwrite': 'yes'}, {'before_commit': 'callback'}, {'max_bytes': 0}):
                with self.subTest(kwargs=kwargs), self.assertRaises((ValueError, TypeError)):
                    download('http://fixture.invalid', self.target, **kwargs)

    def test_negative_length_refused_without_write(self):
        with self.assertRaises(ValueError):
            self.transfer(-1, [], max_bytes=10, overwrite=False)
        self.assertEqual(list(self.root.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
