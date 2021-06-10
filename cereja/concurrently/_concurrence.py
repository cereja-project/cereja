"""

Copyright (c) 2019 The Cereja Project

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import asyncio
import functools
import os
import threading
import time
from collections import Callable
from concurrent.futures import Future, ThreadPoolExecutor
import logging
from typing import Sequence, Any

from cereja.config.cj_types import FunctionType

__all__ = ['TaskList', 'AsyncToSync', 'SyncToAsync']
logger = logging.getLogger(__name__)

# intern
_exclude = ['AsyncToSync', 'SyncToAsync', 'TaskList']

try:
    import contextvars  # Python 3.7+ only.
except ImportError:
    contextvars = None


class AsyncToSync:
    """
    Utility class which turns an awaitable that only works on the thread with
    the event loop into a synchronous callable that works in a subthread.
    Must be initialised from the main thread.
    """

    # Maps launched Tasks to the threads that launched them
    launch_map = {}

    def __init__(self, awaitable, force_new_loop=False):
        self.awaitable = awaitable
        if force_new_loop:
            # They have asked that we always run in a new sub-loop.
            self.main_event_loop = None
        else:
            try:
                self.main_event_loop = asyncio.get_event_loop()
            except RuntimeError:
                # There's no event loop in this thread. Look for the threadlocal if
                # we're inside SyncToAsync
                self.main_event_loop = getattr(
                        SyncToAsync.threadlocal, "main_event_loop", None
                )

    def __call__(self, *args, **kwargs):
        # You can't call AsyncToSync from a thread with a running event loop
        try:
            event_loop = asyncio.get_event_loop()
        except RuntimeError:
            pass
        else:
            if event_loop.is_running():
                raise RuntimeError(
                        "You cannot use AsyncToSync in the same thread as an async event loop - "
                        "just await the async function directly."
                )
        # Make a future for the return information
        call_result = Future()
        # Get the source thread
        source_thread = threading.current_thread()
        # Use call_soon_threadsafe to schedule a synchronous callback on the
        # main event loop's thread if it's there, otherwise make a new loop
        # in this thread.
        if not (self.main_event_loop and self.main_event_loop.is_running()):
            # Make our own event loop and run inside that.
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                        self.main_wrap(args, kwargs, call_result, source_thread)
                )
            finally:
                try:
                    if hasattr(loop, "shutdown_asyncgens"):
                        loop.run_until_complete(loop.shutdown_asyncgens())
                finally:
                    loop.close()
                    asyncio.set_event_loop(self.main_event_loop)
        else:
            self.main_event_loop.call_soon_threadsafe(
                    self.main_event_loop.create_task,
                    self.main_wrap(args, kwargs, call_result, source_thread),
            )
        # Wait for results from the future.
        return call_result.result()

    def __get__(self, parent, objtype):
        """
        Include self for methods
        """
        return functools.partial(self.__call__, parent)

    async def main_wrap(self, args, kwargs, call_result, source_thread):
        """
        Wraps the awaitable with something that puts the result into the
        result/exception future.
        """
        current_task = SyncToAsync.get_current_task()
        self.launch_map[current_task] = source_thread
        try:
            result = await self.awaitable(*args, **kwargs)
        except Exception as e:
            call_result.set_exception(e)
        else:
            call_result.set_result(result)
        finally:
            del self.launch_map[current_task]


class SyncToAsync:
    """
    Utility class which turns a synchronous callable into an awaitable that
    runs in a threadpool. It also sets a threadlocal inside the thread so
    calls to AsyncToSync can escape it.
    """

    # If they've set ASGI_THREADS, update the default asyncio executor for now
    if "ASGI_THREADS" in os.environ:
        loop = asyncio.get_event_loop()
        loop.set_default_executor(
                ThreadPoolExecutor(max_workers=int(os.environ["ASGI_THREADS"]))
        )

    # Maps launched threads to the coroutines that spawned them
    launch_map = {}

    # Storage for main event loop references
    threadlocal = threading.local()

    def __init__(self, func):
        self.func = func

    async def __call__(self, *args, **kwargs):
        loop = asyncio.get_event_loop()

        if contextvars is not None:
            context = contextvars.copy_context()
            child = functools.partial(self.func, *args, **kwargs)
            func = context.run
            args = (child,)
            kwargs = {}
        else:
            func = self.func

        future = loop.run_in_executor(
                None,
                functools.partial(
                        self.thread_handler,
                        loop,
                        self.get_current_task(),
                        func,
                        *args,
                        **kwargs
                ),
        )
        return await asyncio.wait_for(future, timeout=None)

    def __get__(self, parent, objtype):
        """
        Include self for methods
        """
        return functools.partial(self.__call__, parent)

    def thread_handler(self, loop, source_task, func, *args, **kwargs):
        """
        Wraps the sync application with exception handling.
        """
        # Set the threadlocal for AsyncToSync
        self.threadlocal.main_event_loop = loop
        # Set the task mapping (used for the locals module)
        current_thread = threading.current_thread()
        self.launch_map[current_thread] = source_task
        # Run the function
        try:
            return func(*args, **kwargs)
        finally:
            del self.launch_map[current_thread]

    @staticmethod
    def get_current_task():
        """
        Cross-version implementation of asyncio.current_task()
        Returns None if there is no task.
        """
        try:
            if hasattr(asyncio, "current_task"):
                # Python 3.7 and up
                return asyncio.current_task()
            else:
                # Python 3.6
                return asyncio.Task.current_task()
        except RuntimeError:
            return None


class TaskList:
    """
    Perform functions on a list of values

    It is not yet possible to send more than one argument, be aware of that!

    e.g:

    note that in this example each execution of the function would take 5 seconds and we are forcing 5 executions.
    See the difference in waiting time between execution using concurrency / parallelism and functional execution

    >>>import time
    >>>import cereja as cj
    >>>cj.set_log_level('INFO') # need to see perform log
    INFO:cereja.utils:Update log level to INFO
    >>>task_list = cj.TaskList(lambda foo: time.sleep(5), [1,2,3,4,5])
    >>>task_list.run() # concurrency / parallelism
    INFO:cereja.decorators:[run] performed 5.0174219608306885
    [None, None, None, None, None] # the return is empty because the function returns nothing
    >>>task_list._run_functional()
    INFO:cereja.decorators:[_run_functional] performed 25.0233952999115
    [None, None, None, None, None]

    """

    def __init__(self, func: FunctionType, sequence: Sequence[Any]):
        from ..utils import is_sequence
        if not isinstance(func, Callable):
            raise TypeError(f"{func} is not callable.")

        if not is_sequence(sequence):
            raise TypeError(f"sequence is not valid.")

        self.func = func
        self.sequence = sequence

    @property
    def loop(self):
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop
        return loop

    @SyncToAsync
    def _wrapper(self, val):
        return self.func(val)

    async def _run(self):  # only python3.7
        return await asyncio.gather(*map(self._wrapper, self.sequence))

    def run(self):
        if hasattr(asyncio, 'run'):  # Only python 3.7
            return asyncio.run(self._run())
        return self.loop.run_until_complete(asyncio.gather(*map(self._wrapper, self.sequence)))

    def _run_functional(self):
        return list(map(self.func, self.sequence))
