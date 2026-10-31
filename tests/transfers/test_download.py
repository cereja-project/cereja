import asyncio
from pathlib import Path
import tempfile
import unittest

from cereja.http import HTTPStatusError
from cereja.transfers import async_download, download
from http3._server import running_server


class DownloadTest(unittest.TestCase):
    def test_directory_download_uses_final_response_filename(self):
        with running_server() as (base, _), tempfile.TemporaryDirectory() as directory:
            target_dir = Path(directory) / "new"
            result = download(
                base + "/named-redirect", destination_dir=target_dir,
                fallback_filename="fallback.zip", max_bytes=7, overwrite=False,
            )
            self.assertEqual(result.path, target_dir / "report data.zip")
            self.assertEqual(result.path.read_bytes(), b"payload")
            self.assertEqual(result.status_code, 200)
            self.assertEqual(list(target_dir.iterdir()), [result.path])

    def test_authenticated_download_sends_headers_to_server(self):
        with running_server() as (base, _), tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "payload.bin"
            with self.assertRaisesRegex(HTTPStatusError, "HTTP 401") as caught:
                download(base + "/protected", destination)
            self.assertIsInstance(caught.exception, RuntimeError)
            self.assertEqual(caught.exception.response.status_code, 401)
            self.assertEqual(str(caught.exception.request.url), base + "/protected")
            self.assertTrue(caught.exception.response.stream.closed)
            self.assertEqual(list(Path(directory).iterdir()), [])
            result = download(
                base + "/protected", destination, max_bytes=9, overwrite=False,
                headers=[("Authorization", "Bearer fixture-token"), ("X-Tag", "one"), ("X-Tag", "two")],
            )
            self.assertEqual(destination.read_bytes(), b"protected")
            self.assertEqual(result.bytes_transferred, 9)

    def test_download_is_atomic_and_reports_progress(self):
        with running_server() as (base, _), tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "payload.bin"
            events = []
            result = download(base + "/chunked", destination, progress=events.append, chunk_size=2)
            self.assertEqual(destination.read_bytes(), b"abcdefg")
            self.assertEqual(result.bytes_transferred, 7)
            self.assertEqual(events[-1].bytes_transferred, 7)
            self.assertEqual(list(Path(directory).glob("*.part")), [])

    def test_download_follows_redirect_in_streaming_mode(self):
        with running_server() as (base, _), tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "redirect.bin"
            result = download(base + "/redirect", destination, chunk_size=2)
            self.assertEqual(destination.read_bytes(), b"hello")
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.bytes_transferred, 5)


class AsyncDownloadTest(unittest.IsolatedAsyncioTestCase):
    async def test_directory_download_uses_final_response_filename(self):
        with running_server() as (base, _), tempfile.TemporaryDirectory() as directory:
            target_dir = Path(directory) / "new"
            result = await async_download(
                base + "/named-redirect", destination_dir=target_dir,
                fallback_filename="fallback.zip", max_bytes=7, overwrite=False,
            )
            self.assertEqual(result.path, target_dir / "report data.zip")
            self.assertEqual(result.path.read_bytes(), b"payload")
            self.assertEqual(result.status_code, 200)
            self.assertEqual(list(target_dir.iterdir()), [result.path])

    async def test_authenticated_download_sends_headers_to_server(self):
        with running_server() as (base, _), tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "payload.bin"
            with self.assertRaisesRegex(HTTPStatusError, "HTTP 401") as caught:
                await async_download(base + "/protected", destination)
            self.assertIsInstance(caught.exception, RuntimeError)
            self.assertEqual(caught.exception.response.status_code, 401)
            self.assertEqual(str(caught.exception.request.url), base + "/protected")
            self.assertTrue(caught.exception.response.stream.closed)
            self.assertEqual(list(Path(directory).iterdir()), [])
            result = await async_download(
                base + "/protected", destination, max_bytes=9, overwrite=False,
                headers=[("Authorization", "Bearer fixture-token"), ("X-Tag", "one"), ("X-Tag", "two")],
            )
            self.assertEqual(destination.read_bytes(), b"protected")
            self.assertEqual(result.bytes_transferred, 9)

    async def test_async_download(self):
        with running_server() as (base, _), tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "payload.bin"
            result = await async_download(base + "/fixed", destination, chunk_size=2)
            self.assertEqual(await asyncio.to_thread(destination.read_bytes), b"hello")
            self.assertEqual(result.bytes_transferred, 5)

    async def test_async_download_follows_redirect_in_streaming_mode(self):
        with running_server() as (base, _), tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "redirect.bin"
            result = await async_download(base + "/redirect", destination, chunk_size=2)
            self.assertEqual(await asyncio.to_thread(destination.read_bytes), b"hello")
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.bytes_transferred, 5)


if __name__ == "__main__":
    unittest.main()
