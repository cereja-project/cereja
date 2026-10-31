"""Download status errors preserve typed HTTP metadata and legacy catches."""

from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cereja.http import Headers, HTTPError, HTTPStatusError, Request, RequestError, ResponseInfo, URL
from cereja.http.async_.stream import AsyncStreamResponse
from cereja.http.sync.stream import StreamResponse
from cereja.transfers import async_download, download


class UnreadBody:
    closed = False

    def iter_bytes(self, size):
        raise AssertionError('error body consumed')

    def aiter_bytes(self, size):
        raise AssertionError('error body consumed')

    def close(self):
        self.closed = True

    async def aclose(self):
        self.closed = True


class Client:
    def __init__(self, response):
        self.response = response
        self.closed = False

    @contextmanager
    def stream(self, *args, **kwargs):
        with self.response:
            yield self.response

    def close(self):
        self.closed = True


class AsyncClient(Client):
    @asynccontextmanager
    async def stream(self, *args, **kwargs):
        async with self.response:
            yield self.response

    async def aclose(self):
        self.closed = True


class DownloadStatusErrorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def client(self, asynchronous, status):
        url = URL.parse('https://example.com/final')
        request = Request('GET', url, Headers(), None)
        headers = Headers({'Content-Length': '100', 'Retry-After': '30'})
        info = ResponseInfo(status, 'Example status', headers, url, 'HTTP/1.1')
        response_type = AsyncStreamResponse if asynchronous else StreamResponse
        client_type = AsyncClient if asynchronous else Client
        return client_type(response_type(request, info, UnreadBody()))

    async def transfer(self, asynchronous, **kwargs):
        if asynchronous:
            return await async_download('https://example.com/original', **kwargs)
        return download('https://example.com/original', **kwargs)

    async def test_status_error_preserves_metadata_and_legacy_message(self):
        for asynchronous in (False, True):
            for status in (400, 401, 403, 404, 429, 500, 503):
                for owned in (False, True):
                    for directory_mode in (False, True):
                        with self.subTest(asyncio=asynchronous, status=status, owned=owned, directory=directory_mode):
                            client = self.client(asynchronous, status)
                            destination = ({'destination_dir': self.root / 'new'} if directory_mode
                                           else {'destination': self.root / 'new' / 'file.bin'})
                            kwargs = {} if owned else {'client': client}
                            factory = 'AsyncClient' if asynchronous else 'Client'
                            with patch('cereja.transfers.download.' + factory, return_value=client):
                                with patch('cereja.transfers.download.AtomicFileSink',
                                           side_effect=AssertionError('sink created for HTTP error')):
                                    with self.assertRaises(HTTPStatusError) as caught:
                                        await self.transfer(asynchronous, **destination, **kwargs)
                            error = caught.exception
                            self.assertIsInstance(error, RuntimeError)
                            self.assertIsInstance(error, HTTPError)
                            self.assertIs(error.request, client.response.request)
                            self.assertIs(error.response, client.response)
                            self.assertEqual(error.response.status_code, status)
                            self.assertEqual(error.response.headers['Retry-After'], '30')
                            self.assertEqual(str(error.request.url), 'https://example.com/final')
                            self.assertEqual(
                                str(error), f'HTTP {status} while downloading https://example.com/original',
                            )
                            self.assertTrue(client.response.stream.closed)
                            self.assertEqual(client.closed, owned)
                            self.assertEqual(list(self.root.iterdir()), [])

    async def test_runtime_error_handler_still_catches_download_status_error(self):
        for asynchronous in (False, True):
            client = self.client(asynchronous, 404)
            with self.assertRaises(RuntimeError) as caught:
                await self.transfer(asynchronous, destination=self.root / 'file.bin', client=client)
            self.assertIsInstance(caught.exception, HTTPStatusError)

    async def test_existing_destination_is_preserved_on_http_error(self):
        target = self.root / 'keep.bin'
        target.write_bytes(b'keep')
        for asynchronous in (False, True):
            for overwrite in (False, True):
                client = self.client(asynchronous, 500)
                with self.assertRaises(HTTPStatusError):
                    await self.transfer(asynchronous, destination=target, client=client, overwrite=overwrite)
                self.assertEqual(target.read_bytes(), b'keep')
                self.assertEqual(list(self.root.iterdir()), [target])

    async def test_other_failures_propagate_without_reclassification(self):
        for asynchronous in (False, True):
            for failure in (RequestError('transport failed'), ValueError('invalid header'),
                            RuntimeError('custom failure')):
                client = self.client(asynchronous, 500)
                with patch.object(client, 'stream', side_effect=failure):
                    with self.assertRaises(type(failure)) as caught:
                        await self.transfer(asynchronous, destination=self.root / 'file.bin', client=client)
                self.assertIs(caught.exception, failure)
                self.assertNotIsInstance(caught.exception, HTTPStatusError)
                self.assertFalse(client.closed)
                self.assertEqual(list(self.root.iterdir()), [])

    async def test_legacy_borrowed_response_without_request_keeps_runtime_error_catch(self):
        for asynchronous in (False, True):
            client = self.client(asynchronous, 404)
            del client.response.request
            with self.assertRaises(RuntimeError) as caught:
                await self.transfer(asynchronous, destination=self.root / 'file.bin', client=client)
            self.assertIsInstance(caught.exception, HTTPStatusError)
            self.assertIsNone(caught.exception.request)
            self.assertIs(caught.exception.response, client.response)


if __name__ == '__main__':
    unittest.main()
