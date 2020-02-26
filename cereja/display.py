import threading

import sys
import time


class Progress(object):

    def __init__(self, style="loading", **kwargs):
        self._style = style
        self._loading_symb = '.'
        self._bar_symb = '#'
        self._current_percent = 0
        self._finish = False
        self._last_percent = None
        self._n_times = 0
        self._max_loading_symb = 3
        self._max_bar_symb = 100
        self._bar = ' ' * self._max_bar_symb

    @property
    def _loading_progress(self):
        self._n_times += 1
        if self._n_times > self._max_loading_symb:
            self._n_times = 0
        n_blanks = ' ' * (self._max_loading_symb - self._n_times)
        return (self._loading_symb * self._n_times) + n_blanks

    @property
    def _bar_progress(self):
        if self._current_percent != self._last_percent:
            self._last_percent = self._current_percent
        return self._bar.replace(' ', self._bar_symb, self._current_percent)

    @property
    def _display(self):
        if self._style == 'bar':
            return self._bar_progress
        return self._loading_progress

    def set_percent(self, value):
        self._current_percent = value

    def _write(self):
        sys.stdout.write(f"\r")

        if self._current_percent == 0:
            sys.stdout.write(f"Awaiting {self._loading_progress}")
        else:
            sys.stdout.write(f"Progress --> [{self._display}] {self._current_percent}%")
        sys.stdout.flush()
        self._last_percent = self._current_percent

    def _looping(self):
        while not self._finish:
            self._write()
            time.sleep(0.5)
        self._write()

    def __enter__(self):
        self.th = threading.Thread(target=self._looping)
        self.th.start()
        return self

    def __exit__(self, *args, **kwargs):
        self._finish = True
        self.th.join()


if __name__ == '__main__':
    pass
