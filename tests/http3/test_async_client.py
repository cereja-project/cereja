import asyncio
import unittest

from cereja.http import BodyLimitExceeded, ProtocolError, ReadTimeout
from cereja.http.async_ import AsyncClient
from ._server import running_server


class AsyncClientTest(unittest.IsolatedAsyncioTestCase):
    async def test_native_async_requests_streaming_pool_and_cleanup(self):
        with running_server() as (base, handler):
            async with AsyncClient(max_connections=2) as client:
                self.assertEqual((await client.get(base + "/json")).json(), {"ok": True})
                posted = (await client.post(base + "/fixed", content=b"\x00\xff")).json()
                self.assertEqual(posted["body"].encode("latin1"), b"\x00\xff")
                self.assertEqual((await client.get(base + "/fixed")).content, b"hello")
            self.assertEqual(len(handler.seen_connections), 1)
        with running_server() as (base, _):
            async with AsyncClient() as client:
                async with client.stream("GET", base + "/chunked") as response:
                    self.assertEqual(b"".join([c async for c in response.aiter_bytes(2)]), b"abcdefg")
                self.assertEqual((await client.get(base + "/redirect")).content, b"hello")
                with self.assertRaises(ProtocolError):
                    await client.get(base + "/loop")
                with self.assertRaises(ProtocolError):
                    await client.get(base + "/truncated")
            async with AsyncClient(max_body_bytes=16) as client:
                with self.assertRaises(BodyLimitExceeded):
                    await client.get(base + "/large")
            async with AsyncClient(timeout=0.05) as client:
                with self.assertRaises(ReadTimeout):
                    await client.get(base + "/slow")
            async with AsyncClient(max_connections=1, timeout=1) as client:
                task = asyncio.create_task(client.get(base + "/slow"))
                await asyncio.sleep(0.03)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
                self.assertEqual((await client.get(base + "/fixed")).content, b"hello")


if __name__ == "__main__":
    unittest.main()
