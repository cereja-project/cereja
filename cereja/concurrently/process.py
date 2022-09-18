import threading

__all__ = ["Buffer", "ProcessSequence"]

from collections import OrderedDict

from ..utils.decorators import synchronized


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
        self._running = False
        return list(self._result.values())
