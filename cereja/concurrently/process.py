import abc
import os
import queue
import threading
import time

from ..utils import decorators

from .. import Progress, console

__all__ = ["MultiProcess"]


class _IMultiProcess(abc.ABC):
    @abc.abstractmethod
    def _store_response(self, response):
        return NotImplementedError

    @abc.abstractmethod
    def _get_response(self):
        return NotImplementedError


class MultiProcess(_IMultiProcess):
    """
    MultiProcess is a utility class designed to execute a given function in parallel using multiple threads.

    Attributes:
        max_threads (int): Maximum number of threads to be used for parallel processing.
        _active_threads (int): The number of currently running threads.
        _lock (threading.Lock): A lock to manage access to shared resources.
        _thread_available (threading.Condition): A condition variable associated with `lock` to manage thread synchronization.
        _terminate (bool): A flag indicating if the thread execution should be terminated prematurely.
    """

    def __init__(self, max_threads: int, on_result=None):
        """
        Initializes a new instance of the MultiProcess class.

        Args:
            max_threads (int): The maximum number of threads to be used.
        """
        self.max_threads = max_threads
        self._active_threads = 0
        self._lock = threading.Lock()
        self._thread_available = threading.Condition(self._lock)
        self._terminate = False
        self._results = []
        self._exception_err = None
        self._on_result = on_result

    def _create_task(self, function, value, indx, *args, **kwargs):
        self.wait_for_available_thread()
        if self._terminate:
            self._terminate = False
            raise ChildProcessError(f"Error on task item {indx - 1}: {self._exception_err}")
        thread = threading.Thread(target=self._execute_function_thread, name=f'Thread-{indx}',
                                  args=(function, value, indx, args, kwargs))
        with self._lock:
            self._active_threads += 1
        thread.start()

    def _get_response(self):
        with self._thread_available:
            while self._active_threads > 0:
                self._thread_available.wait()
            results = [val[-1] for val in sorted(self._results, key=lambda val: val[0])]
            self._results = []
            self._terminate = False
            return results

    def _store_response(self, response):
        self._results.append(response)

    def _process_response(self, response):
        if self._on_result is not None:
            self._on_result(response)
        else:
            self._store_response(response)

    @decorators.depreciation(alternative='map')
    def execute(self, function, values, *args, verbose=True, **kwargs) -> list:
        return self.map(function, values, *args, verbose=verbose, **kwargs)

    def map(self, function, values, *args, verbose=True, **kwargs) -> list:
        """
        Execute the given function using multiple threads on the provided values.

        Args:
            function (Callable): The function to be executed.
            values (Iterable): A list or other iterable of values on which the function will be executed.

        @return: ordered each given function returns
        """
        self._terminate = False
        for indx, value in enumerate(
                Progress.prog(values,
                              custom_state_func=lambda: f'Threads Running: {self._active_threads}') if verbose else values):
            try:
                self._create_task(function, value, indx, *args, **kwargs)
            except ChildProcessError:
                print("Terminating due to an exception in one of the threads. Returning processed data...")
                break
        if self._on_result is None:
            return self._get_response()

    def wait_for_available_thread(self):
        """
        Blocks the current thread until a thread becomes available or the maximum thread limit is not reached.
        """
        with self._thread_available:
            while self._active_threads >= self.max_threads:
                self._thread_available.wait()

    def _execute_function_thread(self, function, value, indx, args, kwargs):
        """
        Internal method to execute the function on the given value. Handles exceptions and manages the active thread count.

        Args:
            function (Callable): The function to be executed.
            value: A single value from the values iterable.
        """
        try:
            if not self._terminate:
                self._process_response((indx, function(value, *args, **kwargs)))
        except Exception as e:
            print(f"Error encountered in thread: {e}")
            self._terminate = True
            self._exception_err = e
        finally:
            with self._thread_available:
                self._active_threads -= 1
                self._thread_available.notify()


class WorkerQueue(MultiProcess):
    def __init__(self, func_task, max_threads: int = 1, max_size=-1, on_result=None, **task_kwargs):
        super().__init__(max_threads, on_result=on_result)
        self._q = queue.Queue(maxsize=max_size)
        self._results = queue.PriorityQueue()
        self._func_task = func_task
        self._task_kwargs = task_kwargs
        self._th_service = threading.Thread(target=self._worker, daemon=True).start()
        self._indx = -1

    def put(self, item, block=True, timeout=None, **task_kwargs):
        """Put an item into the queue.

        If optional args 'block' is true and 'timeout' is None (the default),
        block if necessary until a free slot is available. If 'timeout' is
        a non-negative number, it blocks at most 'timeout' seconds and raises
        the Full exception if no free slot was available within that time.
        Otherwise ('block' is false), put an item on the queue if a free slot
        is immediately available, else raise the Full exception ('timeout'
        is ignored in that case).
        """
        self._indx += 1
        self._q.put((self._indx, item, task_kwargs if len(task_kwargs) else {}), block=block, timeout=timeout)

    def _store_response(self, response):
        self._results.put_nowait(item=response)

    def get_available_reponse(self, take_indx=False, timeout=30):
        return self._get(take_indx, timeout=timeout)

    def _get(self, take_indx=False, timeout=30):
        assert self._on_result is None, "task results are being sent to the callback defined 'on_result'"
        while (self._results.qsize() > 0 or self._active_threads > 0) or not self.is_empty:
            indx, item = self._results.get(timeout=timeout)
            self._results.task_done()
            return indx, item if take_indx else item

    def _get_response(self, take_indx=False):
        assert self._on_result is None, "task results are being sent to the callback defined 'on_result'"
        self._q.join()
        self._indx = -1
        result = []

        while self._results.qsize() > 0 or self._active_threads > 0:
            result.append(self._results.get(timeout=1))
            self._results.task_done()
        self._results.join()
        return [val if take_indx else val[-1] for val in sorted(result, key=lambda val: val[0])]

    def get_all_tasks_response(self, take_indx=False):
        return self._get_response(take_indx)

    def put_nowait(self, item, **task_kwargs):
        self.put(item, block=False, **task_kwargs)

    def _worker(self):
        while True:
            indx, item, kwargs = self._q.get()
            self._create_task(self._func_task, item, indx, **kwargs)
            self._q.task_done()

    @property
    def size(self):
        return self._q.qsize()

    @property
    def is_empty(self):
        return self._q.empty()

    @property
    def is_full(self):
        return self._q.full()

    def __enter__(self, *args, **kwargs) -> 'WorkerQueue':
        self._with_context = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if isinstance(exc_val, Exception) and not isinstance(
                exc_val, DeprecationWarning
        ):
            console.error(
                    f"{os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}: {exc_val}"
            )
        self._q.join()
        self._with_context = False
