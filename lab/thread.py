import threading
import time

import random


def test(value):
    time.sleep(random.randint(1, 10))
    return value


class Process:
    def __init__(self, function):
        self._function = function
        self._result = []
        self._ths = {}
        self._stop_on = None
        self._current = 0

    def _wrap(self, *args, id_=None, **kwargs):
        self._result.append((id_, self._function(*args, **kwargs)))
        self._current += 1

    def run_on(self, values, **kwargs):
        self._stop_on = len(values)
        for n, value in enumerate(values, 1):
            th = threading.Thread(target=self._wrap, args=(value,), kwargs={'id_': n, **kwargs})
            th.start()
            self._ths[n] = th
        while self._current < self._stop_on:
            if len(self._result) >= 1:
                id_, val = self._result.pop(0)
                self._ths[id_].join()
                yield val


process = Process(test)
for i in process.run_on(range(100)):
    print(i)
