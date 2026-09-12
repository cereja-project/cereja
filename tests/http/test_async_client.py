import asyncio
import unittest

from cereja.http import BodyLimitExceeded, ProtocolError, ReadTimeout
from cereja.http.async_ import AsyncClient
from tests.http._server import running_server


class AsyncClientTest(unittest.IsolatedAsyncioTestCase):
    async def test_get_json_post_and_connection_reuse(self):
        with running_server() as (base, handler):
            async with AsyncClient(max_connections=2) as client:
                self.assertEqual((await client.get(base + "/json")).json(), {"ok": True})
                posted = (await client.post(base + "/fixed", content=b"\x00\xff")).json()
                self.assertEqual(posted["body"].encode("latin1"), b"\x00\xff")
                self.assertEqual((await client.get(base + "/fixed")).content, b"hello")
            self.assertEqual(len(handler.seen_connections), 1)

    async def test_chunked_streaming(self):
        with running_server() as (base, _):
            async with AsyncClient() as client:
                async with client.stream("GET", base + "/chunked") as response:
                    chunks = [chunk async for chunk in response.aiter_bytes(2)]
                    self.assertEqual(b"".join(chunks), b"abcdefg")

    async def test_connection_close_and_redirect(self):
        with running_server() as (base, _):
            async with AsyncClient() as client:
                self.assertEqual((await client.get(base + "/close")).content, b"bye")
                self.assertEqual((await client.get(base + "/redirect")).content, b"hello")
                with self.assertRaises(ProtocolError):
                    await client.get(base + "/loop")

    async def test_body_limit_and_truncated_body(self):
        with running_server() as (base, _):
            async with AsyncClient(max_body_bytes=16) as client:
                with self.assertRaises(BodyLimitExceeded):
                    await client.get(base + "/large")
            async with AsyncClient() as client:
                with self.assertRaises(ProtocolError):
                    await client.get(base + "/truncated")

    async def test_read_timeout(self):
        with running_server() as (base, _):
            async with AsyncClient(timeout=0.05) as client:
                with self.assertRaises(ReadTimeout):
                    await client.get(base + "/slow")

    async def test_cancellation_releases_connection_capacity(self):
        with running_server() as (base, _):
            async with AsyncClient(max_connections=1, timeout=1) as client:
                task = asyncio.create_task(client.get(base + "/slow"))
                await asyncio.sleep(0.03)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
                response = await client.get(base + "/fixed")
                self.assertEqual(response.content, b"hello")

    async def test_pool_bound_allows_waiting_request(self):
        with running_server() as (base, _):
            async with AsyncClient(max_connections=1, timeout=1) as client:
                first, second = await asyncio.gather(
                    client.get(base + "/slow"),
                    client.get(base + "/fixed"),
                )
                self.assertEqual(first.content, b"slow")
                self.assertEqual(second.content, b"hello")


if __name__ == "__main__":
    unittest.main()
