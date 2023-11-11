import threading
from .. import Progress

__all__ = ["MultiProcess"]


class MultiProcess:
    """
    MultiProcess is a utility class designed to execute a given function in parallel using multiple threads.

    Attributes:
        max_threads (int): Maximum number of threads to be used for parallel processing.
        _active_threads (int): The number of currently running threads.
        _lock (threading.Lock): A lock to manage access to shared resources.
        _thread_available (threading.Condition): A condition variable associated with `lock` to manage thread synchronization.
        _terminate (bool): A flag indicating if the thread execution should be terminated prematurely.
    """

    def __init__(self, max_threads: int):
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

    def execute(self, function, values, *args, **kwargs) -> list:
        """
        Execute the given function using multiple threads on the provided values.

        Args:
            function (Callable): The function to be executed.
            values (Iterable): A list or other iterable of values on which the function will be executed.

        @return: ordered each given function returns
        """
        for indx, value in enumerate(
                Progress.prog(values, custom_state_func=lambda: f'Threads Running: {self._active_threads}')):
            self.wait_for_available_thread()
            if self._terminate:
                print("Terminating due to an exception in one of the threads. Returning processed data...")
                break
            thread = threading.Thread(target=self._execute_function_thread, name=f'Thread-{indx}',
                                      args=(function, value, indx, args, kwargs))
            with self._lock:
                self._active_threads += 1
            thread.start()
        self._terminate = False
        return self._get_results()

    def _get_results(self):
        with self._thread_available:
            while self._active_threads > 0:
                self._thread_available.wait()
            results = [val[-1] for val in sorted(self._results, key=lambda val: val[0])]
            self._results = []
            return results

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
                self._results.append((indx, function(value, *args, **kwargs)))
        except Exception as e:
            print(f"Error encountered in thread: {e}")
            self._terminate = True
        finally:
            with self._thread_available:
                self._active_threads -= 1
                self._thread_available.notify()
