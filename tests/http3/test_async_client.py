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

    async def test_cancellation_discards_connection_and_frees_pool_slot(self):
        request_received = asyncio.Event()
        connection_closed = asyncio.Event()
        handlers = []
        connections = []

        async def handle(reader, writer):
            handlers.append(asyncio.current_task())
            connections.append(writer)
            try:
                headers = await reader.readuntil(b"\r\n\r\n")
                if headers.startswith(b"GET /blocked "):
                    # Keep the response pending until the client closes the socket.
                    request_received.set()
                    await reader.read()
                    connection_closed.set()
                else:
                    writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n"
                                 b"Connection: close\r\n\r\nhello")
                    await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        base = f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}"
        task = None
        try:
            async with server, AsyncClient(max_connections=1, timeout=5) as client:
                # This deadline guards a broken test; events control cancellation.
                async with asyncio.timeout(5):
                    task = asyncio.create_task(client.get(base + "/blocked"))
                    await request_received.wait()
                    self.assertFalse(task.done())
                    self.assertTrue(task.cancel())
                    with self.assertRaises(asyncio.CancelledError):
                        await task
                    await connection_closed.wait()
                    self.assertEqual((await client.get(base + "/fixed")).content, b"hello")
                    self.assertEqual(len(connections), 2)
        finally:
            if task is not None:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            for handler in handlers:
                if not handler.done():
                    handler.cancel()
            results = await asyncio.gather(*handlers, return_exceptions=True)
            for result in results:
                if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
                    raise result


if __name__ == "__main__":
    unittest.main()
