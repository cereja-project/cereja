import threading
import time
from collections import OrderedDict

from .. import Progress
from ..utils.decorators import synchronized

__all__ = ["Buffer", "ProcessSequence"]


class Buffer:
    def __init__(self, data, size: int, stride=None, take_index=False):
        self._size = size
        self._total_taked = 0
        self._data = iter(data)
        self._take_index = take_index
        self._stride = stride or size

    def __iter__(self):
        batch = []

        while True:
            try:
                item = next(self._data)
                self._total_taked += 1
                batch.append(
                        item if not self._take_index else [self._total_taked - 1, item]
                )
                if len(batch) == self._size:
                    yield batch
                    batch = batch[self._stride:]
            except StopIteration:
                if batch:
                    yield batch
                break


class ProcessSequence:
    def __init__(self, func, num_workers: int = 1, args=None, kwargs=None):
        self._num_workers = num_workers
        self._args = args or ()
        self._kwargs = kwargs or {}
        self._func = func
        self._workers = []
        self._running = False
        self._result = OrderedDict()

    @synchronized
    def __func(self, buffer):
        for idx, item in buffer:
            self._result[idx] = self._func(item, *self._args, **self._kwargs)

    def __call__(self, data):
        assert self._running is False, "Process is already running"
        self._running = True
        for buffer in Buffer(data, self._num_workers, take_index=True):
            worker = threading.Thread(target=self.__func, args=(buffer,))
            worker.start()
            self._workers.append(worker)
        for worker in self._workers:
            worker.join()
        result = list(self._result.values())
        self._workers = []
        self._result = OrderedDict()
        self._running = False
        return result


class ThreadController:
    def __init__(self, max_threads):
        self.max_threads = max_threads
        self.active_threads = 0
        self.lock = threading.Lock()
        self.terminate = False
        self._threads = {}

    def execute_function(self, function, values):
        for indx, value in enumerate(Progress.prog(values, custom_state_func=lambda: f'TH: {self.active_threads}')):
            self.wait_for_available_thread()
            if self.terminate:
                break
            thread = threading.Thread(target=self._execute_function_thread, name=f'Thread-{indx}',
                                      args=(function, value))
            thread.start()
            self.active_threads += 1

    def wait_for_available_thread(self):
        while self.active_threads >= self.max_threads:
            time.sleep(0)

    def _execute_function_thread(self, function, value):
        try:
            if not self.terminate:
                function(value)
        except Exception as e:
            self.terminate = True
        finally:
            with self.lock:
                self.active_threads -= 1
                threading.Event().set()
