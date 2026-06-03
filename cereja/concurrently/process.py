"""
Thread-based concurrency utilities for batch and queue-driven workloads.

This module offers three main building blocks:

- ``MultiProcess``: bounded thread execution over an iterable, preserving
  result order by input index.
- ``WorkerQueue``: producer/consumer interface that feeds a background queue
  and executes tasks concurrently.
- ``Processor``: high-throughput processing pipeline based on
  :class:`concurrent.futures.ThreadPoolExecutor`, with optional rate limiting,
  backpressure and progress reporting.

Note:
    Despite legacy names, these implementations are thread-based and do not
    spawn operating-system processes.
"""

import abc
import logging
import os
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from .. import Progress, console
from ..utils import decorators

__all__ = ["MultiProcess", "Processor"]

logger = logging.getLogger(__name__)


class _IMultiProcess(abc.ABC):
    """Minimal protocol for classes that store and retrieve async responses."""

    @abc.abstractmethod
    def _store_response(self, response):
        """Store a single response item produced by a worker."""
        return NotImplementedError

    @abc.abstractmethod
    def _get_response(self):
        """Return all pending responses in the implementation-defined format."""
        return NotImplementedError


class MultiProcess(_IMultiProcess):
    """
    Execute tasks concurrently using native threads.

    Results are produced in the same order as the input sequence when
    ``on_result`` is not provided.

    Args:
        max_threads: Maximum number of concurrent worker threads.
        on_result: Optional callback that receives ``(index, result)`` as soon
            as each task completes. When provided, :meth:`map` returns ``None``.
    """

    def __init__(self, max_threads: int, on_result=None):
        self.max_threads = max_threads
        self._active_threads = 0
        self._lock = threading.Lock()
        self._thread_available = threading.Condition(self._lock)
        self._terminate = False
        self._results = []
        self._exception_err = None
        self._on_result = on_result

    def _create_task(self, function, value, indx, *args, **kwargs):
        """Create and start one worker thread after capacity is available."""
        self.wait_for_available_thread()
        if self._terminate:
            self._terminate = False
            raise ChildProcessError(f"Error on task item {indx}: {self._exception_err}")
        thread = threading.Thread(
                target=self._execute_function_thread,
                name=f"Thread-{indx}",
                args=(function, value, indx, args, kwargs),
        )
        with self._lock:
            self._active_threads += 1
        thread.start()

    def _wait_for_all_threads(self):
        """Block until all active worker threads finish."""
        with self._thread_available:
            while self._active_threads > 0:
                self._thread_available.wait()

    def _get_response(self):
        """Collect and return buffered results ordered by original index."""
        self._wait_for_all_threads()
        results = [val[-1] for val in sorted(self._results, key=lambda val: val[0])]
        self._results = []
        self._terminate = False
        return results

    def _store_response(self, response):
        """Append raw response payload to the internal result buffer."""
        self._results.append(response)

    def _process_response(self, response):
        """Dispatch response to callback or store it internally."""
        if self._on_result is not None:
            self._on_result(response)
        else:
            self._store_response(response)

    @decorators.deprecation(alternative="map")
    def execute(self, function, values, *args, verbose=True, **kwargs) -> list:
        """Deprecated alias for :meth:`map`."""
        return self.map(function, values, *args, verbose=verbose, **kwargs)

    def map(self, function, values, *args, verbose=True, **kwargs) -> list:
        """
        Execute ``function`` for each value and process results.

        Args:
            function: Callable executed per item in ``values``.
            values: Iterable source of input items.
            *args: Extra positional arguments passed to ``function``.
            verbose: Whether to wrap iteration with ``Progress`` feedback.
            **kwargs: Extra keyword arguments passed to ``function``.

        Returns:
            Ordered list of results when ``on_result`` is ``None``;
            otherwise ``None`` after all tasks complete.

        Raises:
            ChildProcessError: Raised internally while scheduling when a prior
                worker failure marked execution for termination.
        """
        self._terminate = False
        data = Progress.prog(
                values,
                custom_state_func=lambda: f"Threads Running: {self._active_threads}",
        ) if verbose else values
        for indx, value in enumerate(data):
            try:
                self._create_task(function, value, indx, *args, **kwargs)
            except ChildProcessError:
                logger.error("Terminating due to an exception in one of the threads. Returning processed data.")
                break

        if self._on_result is None:
            return self._get_response()

        # Keep map() synchronous even when callback mode is enabled.
        self._wait_for_all_threads()
        self._terminate = False
        return None

    def wait_for_available_thread(self):
        """Block until there is a free worker slot."""
        with self._thread_available:
            while self._active_threads >= self.max_threads:
                self._thread_available.wait()

    def _execute_function_thread(self, function, value, indx, args, kwargs):
        """Run user function in a worker thread and track completion state."""
        try:
            if not self._terminate:
                self._process_response((indx, function(value, *args, **kwargs)))
        except Exception as err:
            logger.exception("Error encountered in worker thread %s", indx)
            self._terminate = True
            self._exception_err = err
        finally:
            with self._thread_available:
                self._active_threads -= 1
                self._thread_available.notify_all()


class WorkerQueue(MultiProcess):
    """
    Queue-based concurrent worker built on top of :class:`MultiProcess`.

    Items are enqueued first and consumed by a dedicated service thread that
    dispatches them to worker threads.
    """

    def __init__(self, func_task, max_threads: int = 1, max_size=-1, on_result=None, **task_kwargs):
        """
        Initialize a queue worker.

        Args:
            func_task: Callable executed for each enqueued item.
            max_threads: Maximum concurrent worker threads.
            max_size: Maximum queue size (``-1`` means unbounded).
            on_result: Optional callback receiving ``(index, result)``.
            **task_kwargs: Default keyword arguments for each task execution.
        """
        super().__init__(max_threads, on_result=on_result)
        self._q = queue.Queue(maxsize=max_size)
        self._results = queue.PriorityQueue()
        self._func_task = func_task
        self._task_kwargs = task_kwargs
        self._th_service = threading.Thread(target=self._worker, daemon=True, name="WORKER_QUEUE_SERVICE")
        self._th_service.start()
        self._indx = -1
        self._indx_lock = threading.Lock()

    def put(self, item, block=True, timeout=None, **task_kwargs):
        """Enqueue one item for background processing."""
        with self._indx_lock:
            self._indx += 1
            indx = self._indx
        self._q.put((indx, item, task_kwargs if len(task_kwargs) else {}), block=block, timeout=timeout)

    def _store_response(self, response):
        """Store responses in a priority queue to preserve index ordering."""
        self._results.put_nowait(item=response)

    def get_available_response(self, take_indx=False, timeout=30):
        """Return one ready response, waiting up to ``timeout`` seconds."""
        return self._get(take_indx, timeout=timeout)

    # Backward-compatible alias with previous typo.
    def get_available_reponse(self, take_indx=False, timeout=30):
        """Backward-compatible alias for :meth:`get_available_response`."""
        return self.get_available_response(take_indx, timeout=timeout)

    def _get(self, take_indx=False, timeout=30):
        """Internal single-result retrieval helper."""
        if self._on_result is not None:
            raise RuntimeError("task results are being sent to the callback defined 'on_result'")
        while (self._results.qsize() > 0 or self._active_threads > 0) or not self.is_empty:
            indx, item = self._results.get(timeout=timeout)
            self._results.task_done()
            if take_indx:
                return indx, item
            return item

    def _get_response(self, take_indx=False):
        """Wait for queue drain and return all collected responses ordered."""
        if self._on_result is not None:
            raise RuntimeError("task results are being sent to the callback defined 'on_result'")
        self._q.join()
        self._indx = -1
        result = []
        while self._results.qsize() > 0 or self._active_threads > 0:
            result.append(self._results.get(timeout=1))
            self._results.task_done()
        self._results.join()
        return [val if take_indx else val[-1] for val in sorted(result, key=lambda val: val[0])]

    def get_all_tasks_response(self, take_indx=False):
        """Return all queued task responses after processing completes."""
        return self._get_response(take_indx)

    def put_nowait(self, item, **task_kwargs):
        """Non-blocking variant of :meth:`put`."""
        self.put(item, block=False, **task_kwargs)

    def _worker(self):
        """Continuously consume queue items and schedule worker threads."""
        while True:
            indx, item, kwargs = self._q.get()
            try:
                self._create_task(self._func_task, item, indx, **kwargs)
            except ChildProcessError as err:
                logger.exception("WorkerQueue failed to enqueue item %s: %s", indx, err)
            finally:
                self._q.task_done()

    @property
    def size(self):
        """Current number of items waiting in the input queue."""
        return self._q.qsize()

    @property
    def is_empty(self):
        """Whether the input queue has no pending items."""
        return self._q.empty()

    @property
    def is_full(self):
        """Whether the input queue reached its configured max size."""
        return self._q.full()

    def __enter__(self, *args, **kwargs) -> "WorkerQueue":
        """Enter context-manager mode; pending work is flushed on exit."""
        self._with_context = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Wait for queue completion and report context errors to console."""
        if isinstance(exc_val, Exception) and not isinstance(exc_val, DeprecationWarning):
            console.error(f"{os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}: {exc_val}")
        self._q.join()
        self._with_context = False


class Processor:
    """
    Concurrent processing pipeline with bounded in-flight futures.

    ``Processor`` is suited for large iterables where you need:
    - bounded worker concurrency;
    - optional dispatch interval between submissions;
    - optional callback execution on completion;
    - collection of failed input items for retry/inspection.
    """

    def __init__(
            self,
            num_workers=None,
            max_in_progress=100,
            interval_seconds=None,
            use_progress=True,
            on_result=None,
    ):
        """
        Initialize a processor instance.

        Args:
            num_workers: Maximum executor workers. Defaults to ``10``.
            max_in_progress: Upper bound for submitted-not-finished futures.
            interval_seconds: Optional minimum interval between submissions.
            use_progress: Whether to enable ``Progress`` visualization.
            on_result: Optional callback called with each successful result.
        """
        self._num_workers = num_workers if num_workers is not None else 10
        self._on_result = on_result
        self._total_success = 0
        self._max_in_progress = max_in_progress
        self._interval_seconds = 0 if interval_seconds is None else interval_seconds
        self._process_result_service = None
        self._future_to_data = set()
        self._future_lock = threading.Lock()
        self._metrics_lock = threading.Lock()
        self._completed_futures = queue.Queue()
        self._failure_data = []
        self._stopped = False
        self._executor = None
        self._started_at = 0
        self._progress = Progress(
                name="Processor",
                max_value=100,
                states=("value", "percent", "time"),
                custom_state_func=self.get_status,
                custom_state_name="Tx",
        ) if use_progress else None

    @property
    def in_progress_count(self):
        """Number of futures submitted and not fully handled yet."""
        with self._future_lock:
            return len(self._future_to_data)

    @property
    def total_processed(self):
        """Total processed items (success + failure)."""
        with self._metrics_lock:
            return len(self._failure_data) + self._total_success

    @property
    def interval_seconds(self):
        """Configured submission interval in seconds."""
        return self._interval_seconds

    @property
    def total_active_threads(self):
        """Current number of active threads in the Python interpreter."""
        return threading.active_count()

    def _create_process_result_service(self):
        """Create (or recreate) the result-consumer service thread."""
        if self._process_result_service is not None and self._process_result_service.is_alive():
            self._process_result_service.join()
        self._process_result_service = threading.Thread(
                target=self._process_result,
                daemon=True,
                name="PROCESS_RESULT_SERVICE",
        )
        return self._process_result_service

    def get_failure_data(self):
        """Return a copy of items that failed during processing."""
        with self._metrics_lock:
            return list(self._failure_data)

    def _on_future_done(self, future):
        """Callback attached to each future to queue completion handling."""
        self._completed_futures.put(future)

    def _process_result(self):
        """Drain completed futures and update metrics/progress state."""
        while True:
            if self.stopped and self.in_progress_count == 0 and self._completed_futures.empty():
                break
            try:
                future = self._completed_futures.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                result = future.result()
                if self._on_result is not None:
                    self._on_result(result)
            except Exception:
                logger.exception("Failed to process future result.")
            finally:
                with self._future_lock:
                    self._future_to_data.discard(future)
                if self._progress is not None:
                    self._progress.show_progress(self.total_processed)
                self._completed_futures.task_done()

    def _process(self, func, item, *args, **kwargs):
        """Execute one task, recording success/failure metrics."""
        try:
            result = func(item, *args, **kwargs)
            with self._metrics_lock:
                self._total_success += 1
            return result
        except Exception:
            logger.exception("Failed to process item, storing for review.")
            with self._metrics_lock:
                self._failure_data.append(item)

    def get_status(self):
        """Return throughput and counters for progress custom state."""
        elapsed = time.monotonic() - self._started_at
        elapsed = elapsed if elapsed > 0 else 1e-9
        with self._metrics_lock:
            success = self._total_success
            fail = len(self._failure_data)
        processed = success + fail
        return f"{round(processed / elapsed, 2)} items/s " \
               f"- processing: {self.in_progress_count} " \
               f"- success: {success} " \
               f"- fail: {fail} "

    def process(self, func, data, *args, **kwargs):
        """
        Process all ``data`` items with bounded thread-pool concurrency.

        The method blocks until submission and completion handling finish.
        ``on_result`` callbacks are executed by the internal result service
        thread, not by worker threads.

        Args:
            func: Callable applied to each item.
            data: Iterable of input items.
            *args: Extra positional arguments passed to ``func``.
            **kwargs: Extra keyword arguments passed to ``func``.
        """
        self._stopped = False
        self._create_process_result_service().start()
        self._started_at = time.monotonic()

        if self._progress is not None:
            try:
                self._progress.update_max_value(len(data))
            except TypeError:
                # data can be a generator without __len__
                pass
            self._progress.start()

        try:
            with ThreadPoolExecutor(max_workers=self._num_workers, thread_name_prefix="PROCESS_WORKER") as self._executor:
                for item in data:
                    start_time = time.monotonic()
                    future = self._executor.submit(self._process, func, item, *args, **kwargs)
                    with self._future_lock:
                        self._future_to_data.add(future)
                    future.add_done_callback(self._on_future_done)

                    elapsed_time = time.monotonic() - start_time
                    if elapsed_time < self.interval_seconds:
                        time.sleep(self.interval_seconds - elapsed_time)
                    if self.in_progress_count >= self._max_in_progress:
                        logging.debug(f"In-progress count {self.in_progress_count} exceeds limit {self._max_in_progress}")
                        while self.in_progress_count >= self._max_in_progress * 0.9:
                            time.sleep(0.05)
                            if self.stopped:
                                break
        finally:
            self.stop_process()

    @property
    def stopped(self):
        """Whether the processor has been marked as stopped."""
        return self._stopped

    def stop_process(self):
        """Stop result service and progress output, waiting for clean shutdown."""
        self._stopped = True
        current_thread = threading.current_thread()
        if (
                self._process_result_service is not None
                and self._process_result_service.is_alive()
                and self._process_result_service is not current_thread
        ):
            self._process_result_service.join()
        self._process_result_service = None
        if self._progress is not None:
            self._progress.stop()

    def restart_process(self):
        """Reset counters/state and restart background result service."""
        self.stop_process()
        self._stopped = False
        self._started_at = time.monotonic()
        with self._metrics_lock:
            self._failure_data = []
            self._total_success = 0
        with self._future_lock:
            self._future_to_data.clear()
        self._create_process_result_service().start()
