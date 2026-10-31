"""Directory destinations retain transfer limits and atomic publication."""

import asyncio
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cereja.http import Headers, ResponseInfo, URL
from cereja.transfers import async_download, download


class Response:
    status_code = 200

    def __init__(self, disposition=None, chunks=(b'payload',)):
        self.headers = Headers({'Content-Length': str(sum(map(len, chunks)))})
        if disposition is not None:
            self.headers.add('Content-Disposition', disposition)
        self.info = ResponseInfo(200, 'OK', self.headers, URL.parse('https://example.com/url.zip'), 'HTTP/1.1')
        self.chunks = chunks

    @property
    def filename(self):
        return self.info.filename

    def iter_bytes(self, size):
        yield from self.chunks

    async def aiter_bytes(self, size):
        for chunk in self.chunks:
            yield chunk


class Client:
    def __init__(self, response):
        self.response = response
        self.closed = False
        self.stream_closed = False

    @contextmanager
    def stream(self, *args, **kwargs):
        try:
            yield self.response
        finally:
            self.stream_closed = True

    def close(self):
        self.closed = True


class AsyncClient(Client):
    @asynccontextmanager
    async def stream(self, *args, **kwargs):
        try:
            yield self.response
        finally:
            self.stream_closed = True

    async def aclose(self):
        self.closed = True


class DirectoryDownloadTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    async def transfer(self, asynchronous, response, **kwargs):
        client = AsyncClient(response) if asynchronous else Client(response)
        if asynchronous:
            result = await async_download('https://example.com/url.zip', client=client, **kwargs)
        else:
            result = download('https://example.com/url.zip', client=client, **kwargs)
        self.assertFalse(client.closed)
        self.assertTrue(client.stream_closed)
        return result

    async def test_server_name_extended_name_and_fallback(self):
        cases = (
            ('attachment; filename="report.zip"', 'report.zip'),
            ('attachment; filename="legacy.zip"; filename*=UTF-8\'\'%E2%82%AC.zip', '\u20ac.zip'),
            ('attachment; filename="../../report.zip"', 'report.zip'),
            (None, 'fallback.zip'),
            ('attachment; filename="NUL.txt"', 'fallback.zip'),
            ('attachment; filename="unterminated', 'fallback.zip'),
        )
        for asynchronous in (False, True):
            for index, (header, expected) in enumerate(cases):
                with self.subTest(asynchronous=asynchronous, header=header):
                    directory = self.root / str(asynchronous) / str(index) / 'new'
                    result = await self.transfer(
                        asynchronous, Response(header), destination_dir=directory,
                        fallback_filename='fallback.zip', overwrite=False, max_bytes=7,
                    )
                    self.assertEqual(result.path, directory / expected)
                    self.assertEqual(result.path.read_bytes(), b'payload')
                    self.assertEqual(result.bytes_transferred, 7)
                    self.assertEqual(list(directory.iterdir()), [result.path])

    async def test_default_fallback_and_explicit_file_destination(self):
        for asynchronous in (False, True):
            directory = self.root / str(asynchronous)
            result = await self.transfer(asynchronous, Response(), destination_dir=directory)
            self.assertEqual(result.path, directory / 'download.bin')
            explicit = self.root / f'explicit-{asynchronous}.bin'
            result = await self.transfer(
                asynchronous, Response('attachment; filename="server.zip"'), destination=explicit,
            )
            self.assertEqual(result.path, explicit)
            self.assertEqual(explicit.read_bytes(), b'payload')

    async def test_overwrite_policy_and_competing_writer(self):
        for asynchronous in (False, True):
            directory = self.root / str(asynchronous)
            directory.mkdir()
            target = directory / 'report.zip'
            target.write_bytes(b'keep')
            with self.assertRaises(FileExistsError):
                await self.transfer(
                    asynchronous, Response('attachment; filename="report.zip"'),
                    destination_dir=directory, overwrite=False,
                )
            self.assertEqual(target.read_bytes(), b'keep')
            self.assertEqual(list(directory.iterdir()), [target])
            await self.transfer(
                asynchronous, Response('attachment; filename="report.zip"'),
                destination_dir=directory, overwrite=True,
            )
            self.assertEqual(target.read_bytes(), b'payload')
            target.unlink()

            def race(event):
                target.write_bytes(b'other writer')

            with self.assertRaises(FileExistsError):
                await self.transfer(
                    asynchronous, Response('attachment; filename="report.zip"'),
                    destination_dir=directory, overwrite=False, progress=race,
                )
            self.assertEqual(target.read_bytes(), b'other writer')
            self.assertEqual(list(directory.iterdir()), [target])

    async def test_limit_and_commit_failures_remove_temporary_files(self):
        for asynchronous in (False, True):
            directory = self.root / str(asynchronous)
            directory.mkdir()
            target = directory / 'report.zip'
            target.write_bytes(b'keep')
            for total in (None, 7):
                response = Response('attachment; filename="report.zip"', chunks=(b'ab', b'cdefg'))
                if total is None:
                    response.headers = Headers({'Content-Disposition': 'attachment; filename="report.zip"'})
                    response.info = ResponseInfo(200, 'OK', response.headers, response.info.url, 'HTTP/1.1')
                with self.assertRaises(ValueError):
                    await self.transfer(asynchronous, response, destination_dir=directory, max_bytes=4)
                self.assertEqual(target.read_bytes(), b'keep')
                self.assertEqual(list(directory.iterdir()), [target])
            with patch('cereja.transfers.sinks.os.replace', side_effect=OSError('fixture')):
                with self.assertRaises(OSError):
                    await self.transfer(
                        asynchronous, Response('attachment; filename="report.zip"'), destination_dir=directory,
                    )
            self.assertEqual(target.read_bytes(), b'keep')
            self.assertEqual(list(directory.iterdir()), [target])

    async def test_invalid_destination_options_fail_before_client_creation(self):
        cases = [
            {},
            {'destination': self.root / 'file', 'destination_dir': self.root},
        ]
        for name in ('', '.', '..', '../escape', '/absolute', 'C:\\escape', 'sub\\file',
                     'CON', 'bad:name', 'name.', ' padded ', 'bad\x00name', 123, None):
            cases.append({'destination_dir': self.root, 'fallback_filename': name})
        for asynchronous in (False, True):
            for kwargs in cases:
                with self.subTest(asynchronous=asynchronous, kwargs=kwargs):
                    with patch('cereja.transfers.download.Client', side_effect=AssertionError('client acquired')):
                        with patch('cereja.transfers.download.AsyncClient', side_effect=AssertionError('client acquired')):
                            with self.assertRaises((ValueError, TypeError)):
                                if asynchronous:
                                    await async_download('https://example.com/url.zip', **kwargs)
                                else:
                                    download('https://example.com/url.zip', **kwargs)

    async def test_directory_path_is_not_treated_as_a_file_or_inferred_implicitly(self):
        for asynchronous in (False, True):
            path = self.root / f'file-{asynchronous}'
            path.write_bytes(b'keep')
            with self.assertRaises((FileExistsError, NotADirectoryError)):
                await self.transfer(asynchronous, Response(), destination_dir=path)
            self.assertEqual(path.read_bytes(), b'keep')
            explicit_directory = self.root / f'directory-{asynchronous}'
            explicit_directory.mkdir()
            with self.assertRaises(OSError):
                await self.transfer(asynchronous, Response(), destination=explicit_directory)
            self.assertEqual(list(explicit_directory.iterdir()), [])
            self.assertFalse(list(self.root.glob('*.part')))

    async def test_fallback_respects_overwrite_policy(self):
        for asynchronous in (False, True):
            directory = self.root / str(asynchronous)
            directory.mkdir()
            target = directory / 'fallback.zip'
            target.write_bytes(b'keep')
            with self.assertRaises(FileExistsError):
                await self.transfer(
                    asynchronous, Response(), destination_dir=directory,
                    fallback_filename='fallback.zip', overwrite=False,
                )
            self.assertEqual(target.read_bytes(), b'keep')
            self.assertEqual(list(directory.iterdir()), [target])
            await self.transfer(
                asynchronous, Response(), destination_dir=directory,
                fallback_filename='fallback.zip', overwrite=True,
            )
            self.assertEqual(target.read_bytes(), b'payload')
            self.assertEqual(list(directory.iterdir()), [target])

    async def test_oversized_response_does_not_create_destination_directory(self):
        for asynchronous in (False, True):
            directory = self.root / str(asynchronous)
            with self.assertRaises(ValueError):
                await self.transfer(
                    asynchronous, Response('attachment; filename="report.zip"'),
                    destination_dir=directory, max_bytes=1,
                )
            self.assertFalse(directory.exists())

    async def test_async_cancellation_after_write_cleans_selected_destination(self):
        directory = self.root / 'cancelled'
        directory.mkdir()
        target = directory / 'report.zip'
        target.write_bytes(b'keep')
        entered = asyncio.Event()

        async def progress(event):
            entered.set()
            await asyncio.Future()

        task = asyncio.create_task(self.transfer(
            True, Response('attachment; filename="report.zip"'), destination_dir=directory,
            progress=progress, overwrite=False,
        ))
        try:
            await asyncio.wait_for(entered.wait(), 5)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task, 5)
            self.assertEqual(target.read_bytes(), b'keep')
            self.assertEqual(list(directory.iterdir()), [target])
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


if __name__ == '__main__':
    unittest.main()
