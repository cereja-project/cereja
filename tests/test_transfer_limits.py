"""Optional bounded transfer policy, independent from HTTP framing tests."""
import asyncio
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cereja.transfers import async_download, download


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
        self.stream_options = None
        self.closed = False
        self.stream_closed = False
    @contextmanager
    def stream(self, *args, **kwargs):
        self.stream_options = kwargs
        try:
            yield self.response
        finally:
            self.stream_closed = True

    def close(self):
        self.closed = True


class AsyncResponse(Response):
    async def aiter_bytes(self, size):
        for chunk in self.chunks:
            yield chunk


class AsyncClient(Client):
    @asynccontextmanager
    async def stream(self, *args, **kwargs):
        self.stream_options = kwargs
        try:
            yield self.response
        finally:
            self.stream_closed = True

    async def aclose(self):
        self.closed = True


class TransferLimitsTests(unittest.TestCase):
    def test_legacy_borrowed_client_stream_signature_still_works(self):
        class LegacyClient(Client):
            @contextmanager
            def stream(self, method, url, *, timeout=None):
                yield self.response

        result = download('http://fixture.invalid', self.target,
                          client=LegacyClient(Response(3, [b'abc'])))
        self.assertEqual(result.bytes_transferred, 3)
        self.assertEqual(self.target.read_bytes(), b'abc')

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
            for kwargs in ({'overwrite': 'yes'}, {'before_commit': 'callback'}, {'max_bytes': 0},
                           {'overwrite': 1}, {'max_bytes': -1}, {'max_bytes': True}, {'max_bytes': 1.5}):
                with self.subTest(kwargs=kwargs), self.assertRaises((ValueError, TypeError)):
                    download('http://fixture.invalid', self.target, **kwargs)

    def test_negative_length_refused_without_write(self):
        with self.assertRaises(ValueError):
            self.transfer(-1, [], max_bytes=10, overwrite=False)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_headers_forwarded_without_mutation(self):
        for headers in ({'Authorization': 'Bearer fixture-token'},
                        [('Authorization', 'Bearer fixture-token'), ('X-Tag', 'one'), ('X-Tag', 'two')]):
            client = Client(Response(3, [b'abc']))
            original = headers.copy()
            result = download('http://fixture.invalid', self.target, client=client,
                              headers=headers, max_bytes=3)
            self.assertIs(client.stream_options['headers'], headers)
            self.assertEqual(headers, original)
            self.assertEqual(result.bytes_transferred, 3)
            self.assertEqual(self.target.read_bytes(), b'abc')
            self.assertTrue(client.stream_closed)
            self.assertFalse(client.closed)

    def test_size_failures_preserve_existing_file_and_close_only_owned_client(self):
        for total, chunks, limit in ((100, [b'abc'], 4), (None, [b'ab', b'cde'], 4),
                                    (3, [b'ab', b'cde'], 4), (8, [b'abc'], 10), (2, [b'abc'], 10)):
            self.target.write_bytes(b'keep')
            for owned in (False, True):
                client = Client(Response(total, chunks))
                kwargs = {} if owned else {'client': client}
                with patch('cereja.transfers.download.Client', return_value=client):
                    with self.assertRaises(ValueError):
                        download('http://fixture.invalid', self.target, max_bytes=limit, **kwargs)
                self.assertTrue(client.stream_closed)
                self.assertEqual(client.closed, owned)
                self.assertEqual(self.target.read_bytes(), b'keep')
                self.assertEqual(list(self.root.iterdir()), [self.target])

    def test_exact_limit_and_empty_body_can_be_published(self):
        for total, chunks, expected in ((3, [b'a', b'bc'], b'abc'),
                                        (None, [b'a', b'bc'], b'abc'), (0, [], b'')):
            self.target.unlink(missing_ok=True)
            result = self.transfer(total, chunks, max_bytes=3, overwrite=False)
            self.assertEqual(result.bytes_transferred, len(expected))
            self.assertEqual(self.target.read_bytes(), expected)
            self.assertEqual(list(self.root.iterdir()), [self.target])


class AsyncTransferLimitsTests(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_borrowed_client_stream_signature_still_works(self):
        class LegacyClient(AsyncClient):
            @asynccontextmanager
            async def stream(self, method, url, *, timeout=None):
                yield self.response

        result = await async_download('http://fixture.invalid', self.target,
                                      client=LegacyClient(AsyncResponse(3, [b'abc'])))
        self.assertEqual(result.bytes_transferred, 3)
        self.assertEqual(self.target.read_bytes(), b'abc')

    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.target = self.root / 'result'

    async def transfer(self, total, chunks, **kwargs):
        return await async_download('http://fixture.invalid', self.target,
                                    client=AsyncClient(AsyncResponse(total, chunks)), **kwargs)

    async def test_headers_forwarded_and_progress_reported(self):
        for headers in ({'Authorization': 'Bearer fixture-token'},
                        [('Authorization', 'Bearer fixture-token'), ('X-Tag', 'one'), ('X-Tag', 'two')]):
            client = AsyncClient(AsyncResponse(3, [b'a', b'bc']))
            events = []
            original = headers.copy()

            async def progress(event):
                events.append(event)

            result = await async_download('http://fixture.invalid', self.target,
                                          client=client, headers=headers, progress=progress,
                                          max_bytes=3, overwrite=True)
            self.assertIs(client.stream_options['headers'], headers)
            self.assertEqual(headers, original)
            self.assertEqual(result.bytes_transferred, 3)
            self.assertEqual(result.total_bytes, 3)
            self.assertEqual(events[-1].bytes_transferred, 3)
            self.assertTrue(client.stream_closed)
            self.assertFalse(client.closed)
            self.assertEqual(self.target.read_bytes(), b'abc')
            self.assertEqual(list(self.root.iterdir()), [self.target])

    async def test_known_unknown_and_misleading_lengths_preserve_existing_file(self):
        for total, chunks, limit in (
            (100, [b'abc'], 4),
            (None, [b'ab', b'cde'], 4),
            (3, [b'ab', b'cde'], 4),
            (8, [b'abc'], 10),
            (2, [b'abc'], 10),
            (-1, [], 10),
        ):
            with self.subTest(total=total, chunks=chunks):
                self.target.write_bytes(b'keep')
                with self.assertRaises(ValueError):
                    await self.transfer(total, chunks, max_bytes=limit)
                self.assertEqual(self.target.read_bytes(), b'keep')
                self.assertEqual(list(self.root.iterdir()), [self.target])

    async def test_size_failure_closes_only_owned_client(self):
        for owned in (False, True):
            client = AsyncClient(AsyncResponse(None, [b'ab', b'cde']))
            kwargs = {} if owned else {'client': client}
            with patch('cereja.transfers.download.AsyncClient', return_value=client):
                with self.assertRaises(ValueError):
                    await async_download('http://fixture.invalid', self.target, max_bytes=4, **kwargs)
            self.assertTrue(client.stream_closed)
            self.assertEqual(client.closed, owned)
            self.assertEqual(list(self.root.iterdir()), [])

    async def test_exact_limit_and_empty_body_can_be_published(self):
        for total, chunks, expected in ((3, [b'a', b'bc'], b'abc'),
                                        (None, [b'a', b'bc'], b'abc'), (0, [], b'')):
            self.target.unlink(missing_ok=True)
            result = await self.transfer(total, chunks, max_bytes=3, overwrite=False)
            self.assertEqual(result.bytes_transferred, len(expected))
            self.assertEqual(self.target.read_bytes(), expected)
            self.assertEqual(list(self.root.iterdir()), [self.target])

    async def test_existing_file_and_commit_race_are_not_overwritten(self):
        self.target.write_bytes(b'keep')
        with self.assertRaises(FileExistsError):
            await self.transfer(3, [b'abc'], overwrite=False)
        self.assertEqual(self.target.read_bytes(), b'keep')
        self.assertEqual(list(self.root.iterdir()), [self.target])
        self.target.unlink()

        def race(event):
            self.target.write_bytes(b'other writer')

        with self.assertRaises(FileExistsError):
            await self.transfer(3, [b'abc'], overwrite=False, progress=race)
        self.assertEqual(self.target.read_bytes(), b'other writer')
        self.assertEqual(list(self.root.iterdir()), [self.target])

    async def test_existing_default_can_replace_target(self):
        self.target.write_bytes(b'old')
        await self.transfer(3, [b'abc'])
        self.assertEqual(self.target.read_bytes(), b'abc')

    async def test_commit_and_flush_failure_clean_staging(self):
        for operation in ('os.link', 'os.fsync'):
            with patch('cereja.transfers.sinks.' + operation, side_effect=OSError('fixture')):
                with self.assertRaises(OSError):
                    await self.transfer(None, [b'abc'], max_bytes=10, overwrite=False)
            self.assertEqual(list(self.root.iterdir()), [])

    async def test_invalid_policy_rejected_before_client_acquisition(self):
        with patch('cereja.transfers.download.AsyncClient', side_effect=AssertionError('client acquired')):
            for kwargs in ({'overwrite': 'yes'}, {'overwrite': 1}, {'max_bytes': 0},
                           {'max_bytes': -1}, {'max_bytes': True}, {'max_bytes': 1.5}):
                with self.subTest(kwargs=kwargs), self.assertRaises((ValueError, TypeError)):
                    await async_download('http://fixture.invalid', self.target, **kwargs)

    async def test_progress_failure_after_write_preserves_target(self):
        self.target.write_bytes(b'keep')

        def fail(event):
            raise RuntimeError('progress failed')

        with self.assertRaisesRegex(RuntimeError, 'progress failed'):
            await self.transfer(None, [b'abc'], max_bytes=10, progress=fail)
        self.assertEqual(self.target.read_bytes(), b'keep')
        self.assertEqual(list(self.root.iterdir()), [self.target])

    async def test_cancellation_before_publication_cleans_staging(self):
        self.target.write_bytes(b'keep')
        reached_progress = asyncio.Event()

        async def progress(event):
            reached_progress.set()
            await asyncio.Future()

        task = asyncio.create_task(self.transfer(None, [b'abc'], max_bytes=10,
                                                 overwrite=False, progress=progress))
        try:
            await asyncio.wait_for(reached_progress.wait(), 5)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task, 5)
            self.assertEqual(self.target.read_bytes(), b'keep')
            self.assertEqual(list(self.root.iterdir()), [self.target])
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


if __name__ == '__main__':
    unittest.main()
