import threading
import sys
import time

__all__ = 'Progress'


class Progress(object):
    NON_BMP_MAP = dict.fromkeys(range(0x10000, sys.maxunicode + 1), 0xfffd)
    DONE_UNICODE = "\U00002705"
    CLOCKS_UNICODE = ("\U0001F55C", "\U0001F55D", "\U0001F55E", "\U0001F55F", "\U0001F560", "\U0001F561", "\U0001F562",
                      "\U0001F563", "\U0001F564", "\U0001F565", "\U0001F566", "\U0001F567")

    CHERRY_UNICODE = "\U0001F352"

    def __init__(self, job_name="Progress Tool", style="loading", **kwargs):
        self._style = style
        self._default_loading_symb = "."
        self._default_bar_symb = "="
        self._current_percent = 0
        self._finish = False
        self._last_percent = None
        self._n_times = 0
        self._max_loading_symb = 3
        self._max_percent_value = kwargs.get("max_percent", 100)
        self._bar_size = kwargs.get('bar_size', 30)
        self._bar = ' ' * self._bar_size
        self._use_loading_with_clock = False
        self._sleep_time = 0.5
        self.job_name = job_name
        self.first_time = time.time()

        try:
            sys.stdout.write(f"{self.CHERRY_UNICODE} {self.job_name}: Created!")
            self.non_bmp_supported = True
        except UnicodeEncodeError:
            self.non_bmp_supported = False

    def __parse(self, msg: str):
        if self.non_bmp_supported:
            return msg
        return msg.translate(self.NON_BMP_MAP)

    def __send_msg(self, msg):
        sys.stdout.write(f'\r')
        sys.stdout.write(self.__parse(msg))
        sys.stdout.flush()

    def _time(self):
        return f"Time: {round(time.time() - self.first_time, 2)}s"

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
        current_bar_value = int((self._bar_size / self._max_percent_value) * self._current_percent)
        return self._bar.replace(' ', self._default_bar_symb, current_bar_value).replace(' ', '>', 1)

    def _display(self):
        if self._style == 'bar':
            return self._bar_progress()
        return self._loading_progress_with_clock() if self._use_loading_with_clock else self._loading_progress()

    def _current_value_info(self):
        if self._finish:
            return f"Done! {self.DONE_UNICODE} - {self._time()}"
        if self._current_percent == 0:
            return ''
        return f"{self._current_percent}%"

    def _write(self):
        if self._current_percent == 0:
            self.__send_msg(
                f"{self.CHERRY_UNICODE} {self.job_name}: Awaiting {self._loading_progress()} {self._current_value_info()}")
        else:
            self.__send_msg(f"{self.CHERRY_UNICODE} {self.job_name}: [{self._display()}] {self._current_value_info()}")
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

    with Progress(job_name="Progress Bar Test", style='bar') as bar:
        for i in range(1, 100):
            time.sleep(1 / i)
            bar.set_percent(i)