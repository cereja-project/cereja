import asyncio
from pathlib import Path
import tempfile
import unittest

from cereja.transfers import async_download, download
from http3._server import running_server


class DownloadTest(unittest.TestCase):
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
