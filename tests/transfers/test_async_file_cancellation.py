"""Cancellation must not race the download's outstanding filesystem worker."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from cereja.http import Headers
from cereja.transfers import async_download
from cereja.transfers.sinks import AtomicFileSink


class Response:
    status_code = 200
    headers = Headers({'Content-Length': '3'})

    async def aiter_bytes(self, size):
        yield b'abc'


class Client:
    @asynccontextmanager
    async def stream(self, *args, **kwargs):
        yield Response()


class AsyncFileCancellationTests(unittest.IsolatedAsyncioTestCase):
    async def check_operation(self, operation, repeated=False, worker_failure=False):
        loop = asyncio.get_running_loop()
        loop_errors = []
        previous_handler = loop.get_exception_handler()
        loop.set_exception_handler(lambda event_loop, context: loop_errors.append(context))
        self.addCleanup(loop.set_exception_handler, previous_handler)
        # One blocked worker and one FIFO cleanup/barrier worker establish order.
        loop.set_default_executor(ThreadPoolExecutor(max_workers=2))
        entered = asyncio.Event()
        release = threading.Event()
        finished = threading.Event()
        overlaps = []
        sinks = []
        original_open = AtomicFileSink.open
        original_abort = AtomicFileSink.abort
        original_commit = AtomicFileSink.commit

        def blocked(call, *args):
            loop.call_soon_threadsafe(entered.set)
            try:
                if not release.wait(5):
                    raise AssertionError('worker was not released')
                if worker_failure:
                    raise OSError('worker failed after cancellation')
                return call(*args)
            finally:
                finished.set()

        def open_sink(sink):
            sinks.append(sink)
            if operation == 'open':
                return blocked(original_open, sink)
            handle = original_open(sink)
            if operation != 'write':
                return handle

            class Handle:
                def write(self, chunk):
                    return blocked(handle.write, chunk)

            return Handle()

        def commit_sink(sink):
            if operation == 'commit':
                return blocked(original_commit, sink)
            return original_commit(sink)

        def abort_sink(sink):
            if not finished.is_set():
                overlaps.append(operation)
            return original_abort(sink)

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'file.bin'
            target.write_bytes(b'keep')
            with patch.object(AtomicFileSink, 'open', open_sink):
                with patch.object(AtomicFileSink, 'commit', commit_sink):
                    with patch.object(AtomicFileSink, 'abort', abort_sink):
                        task = asyncio.create_task(async_download('https://fixture.invalid', target, client=Client()))
                        try:
                            await asyncio.wait_for(entered.wait(), 5)
                            task.cancel()
                            await asyncio.sleep(0)
                            if repeated:
                                task.cancel()
                                await asyncio.sleep(0)
                            # Cancellation handlers enqueue any premature abort
                            # before this barrier on the sole available worker.
                            await asyncio.wait_for(asyncio.to_thread(lambda: None), 5)
                            release.set()
                            with self.assertRaises(asyncio.CancelledError):
                                await asyncio.wait_for(task, 5)
                            self.assertTrue(await asyncio.to_thread(finished.wait, 5))
                            self.assertEqual(overlaps, [])
                            expected = b'abc' if operation == 'commit' and not worker_failure else b'keep'
                            self.assertEqual(target.read_bytes(), expected)
                            self.assertEqual(list(Path(directory).iterdir()), [target])
                            await asyncio.sleep(0)
                            self.assertEqual(loop_errors, [])
                        finally:
                            release.set()
                            if not task.done():
                                task.cancel()
                            await asyncio.gather(task, return_exceptions=True)
                            await asyncio.to_thread(finished.wait, 5)
                            for sink in sinks:
                                original_abort(sink)

    async def test_cancellation_waits_for_open_before_abort(self):
        await self.check_operation('open')

    async def test_cancellation_waits_for_write_before_abort(self):
        await self.check_operation('write')

    async def test_cancellation_waits_for_commit_before_returning(self):
        await self.check_operation('commit')

    async def test_repeated_cancellation_waits_for_worker(self):
        for operation in ('open', 'write', 'commit'):
            with self.subTest(operation=operation):
                await self.check_operation(operation, repeated=True)

    async def test_worker_failure_does_not_mask_cancellation(self):
        await self.check_operation('write', worker_failure=True)


if __name__ == '__main__':
    unittest.main()
