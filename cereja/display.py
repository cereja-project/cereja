import threading
import sys
import time

__all__ = 'Progress'


class Progress(object):
    DONE_UNICODE = "\U00002705"
    CLOCKS_UNICODE = ("\U0001F55C", "\U0001F55D", "\U0001F55E", "\U0001F55F", "\U0001F560", "\U0001F561", "\U0001F562",
                      "\U0001F563", "\U0001F564", "\U0001F565", "\U0001F566", "\U0001F567")

    CHERRY_UNICODE = "\U0001F352"

    def __init__(self, style="loading", **kwargs):
        self._style = style
        self._default_loading_symb = "."
        self._default_bar_symb = "="
        self._current_percent = 0
        self._finish = False
        self._last_percent = None
        self._n_times = 0
        self._max_loading_symb = 3
        self._max_percent_value = 100
        self._bar = ' ' * self._max_percent_value
        self._use_loading_with_clock = False
        self._sleep_time = 0.5

    def _default_loading(self):
        self._n_times += 1
        if self._n_times > self._max_loading_symb:
            self._n_times = 0
        n_blanks = ' ' * (self._max_loading_symb - self._n_times)
        if self._finish:
            return self._default_loading_symb * self._max_loading_symb
        return (self._default_loading_symb * self._n_times) + n_blanks

    def _loading_progress_with_clock(self):
        self._n_times += 1
        if len(self.CLOCKS_UNICODE) == self._n_times:
            self._n_times = 0
        return self.CLOCKS_UNICODE[self._n_times - 1]

    def _loading_progress(self):
        return self._loading_progress_with_clock() if self._use_loading_with_clock else self._default_loading()

    def _bar_progress(self):
        if self._current_percent != self._last_percent:
            self._last_percent = self._current_percent
        return self._bar.replace(' ', self._default_bar_symb, round(self._current_percent)).replace(' ', '>', 1)

    def _display(self):
        if self._style == 'bar':
            return self._bar_progress()
        return self._loading_progress_with_clock() if self._use_loading_with_clock else self._loading_progress()

    def _current_value_info(self):
        if self._finish:
            return f"Done! {self.DONE_UNICODE}"
        return f"{self._current_percent}%"

    def _write(self):
        sys.stdout.write(f"\r")
        if self._current_percent == 0:
            sys.stdout.write(f"{self.CHERRY_UNICODE} Awaiting Data {self._loading_progress()}")
        else:
            sys.stdout.write(f"{self.CHERRY_UNICODE} Progress --> [{self._display()}] {self._current_value_info()}")
        self._last_percent = self._current_percent

    def _looping(self):
        while not self._finish:
            self._write()
            time.sleep(self._sleep_time)
        self._write()

    def set_percent(self, percent: float):
        self._current_percent = percent

    def display_only_once(self, percent: float = None):
        if percent is not None:
            self.set_percent(percent)
        self._write()

    def __enter__(self):
        self.th = threading.Thread(target=self._looping)
        self.th.start()
        return self

    def __exit__(self, *args, **kwargs):
        self._finish = True
        self.th.join()


if __name__ == '__main__':
    with Progress() as bar:
        for i in range(1, 100):
            time.sleep(1 / i)
            bar.set_percent(i)
