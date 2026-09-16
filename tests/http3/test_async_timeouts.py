import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from cereja.http import ReadTimeout, WriteTimeout
from cereja.http._core.prepare import prepare_request
from cereja.http.async_.stream import _with_timeout
from cereja.http.async_.transport import AsyncTransport
from cereja.http.models import Timeout


class AsyncTimeoutTest(unittest.IsolatedAsyncioTestCase):
    def operation(self, kind, future, timeout):
        if kind == "read":
            return _with_timeout(future, timeout, "read expired")
        writer = Mock()
        writer.drain = lambda: future
        return AsyncTransport._send_headers(
            None, SimpleNamespace(writer=writer),
            prepare_request("GET", "http://localhost/"), Timeout(write=timeout),
        )

    async def test_success_with_and_without_timeout(self):
        for kind in ("read", "write"):
            for timeout in (None, 5):
                with self.subTest(kind=kind, timeout=timeout):
                    future = asyncio.get_running_loop().create_future()
                    future.set_result(b"ok")
                    result = await self.operation(kind, future, timeout)
                    self.assertEqual(result, b"ok" if kind == "read" else None)

    async def test_expiration_preserves_http_timeout_type(self):
        for kind, error in (("read", ReadTimeout), ("write", WriteTimeout)):
            with self.subTest(kind=kind):
                future = asyncio.get_running_loop().create_future()
                with self.assertRaises(error):
                    await self.operation(kind, future, 0)
                self.assertTrue(future.cancelled())

    async def test_external_cancellation_while_pending(self):
        for kind in ("read", "write"):
            for timeout in (None, 5):
                with self.subTest(kind=kind, timeout=timeout):
                    future = asyncio.get_running_loop().create_future()
                    task = asyncio.create_task(self.operation(kind, future, timeout))
                    # Let the operation start waiting, without a wall-clock delay.
                    await asyncio.sleep(0)
                    self.assertTrue(task.cancel())
                    with self.assertRaises(asyncio.CancelledError):
                        await task
                    self.assertTrue(future.cancelled())

    async def test_external_cancellation_when_io_completes(self):
        for kind in ("read", "write"):
            for timeout in (None, 5):
                with self.subTest(kind=kind, timeout=timeout):
                    future = asyncio.get_running_loop().create_future()
                    task = asyncio.create_task(self.operation(kind, future, timeout))
                    # Cancel before the waiter resumes, with I/O already complete.
                    # Python 3.11 wait_for incorrectly returns the result here.
                    future.add_done_callback(lambda _, target=task: target.cancel())
                    await asyncio.sleep(0)
                    future.set_result(b"ok")
                    with self.assertRaises(asyncio.CancelledError):
                        await task
                    self.assertTrue(task.cancelled())
