"""Timing and alert helpers retained for the legacy Windows API."""

import time

from .api import get_api

MB_ICONASTERISK = 0x00000040
MB_ICONEXCLAMATION = 0x00000030
MB_ICONHAND = 0x00000010
MB_ICONQUESTION = 0x00000020
MB_OK = 0x00000000


class Time:
    def __init__(self):
        self._t0 = None
        self._started = False
        self._stopped_on = None
        self._endtime = None
        self._last_time_check = None

    @property
    def t0(self):
        return self._t0

    @property
    def time(self):
        if self._t0 is None:
            self.start()
        self._last_time_check = time.monotonic()
        if self._stopped_on:
            return self._stopped_on - self._t0
        return time.monotonic() - self._t0

    @property
    def last_check_time(self):
        return time.monotonic() - self._last_time_check

    def start(self):
        self._stopped_on = None
        self._t0 = time.monotonic()
        self._last_time_check = self._t0

    def stop(self):
        if self._started:
            self._stopped_on = time.monotonic()
            return
        raise Exception("Time counting has not started. Use Time.start method.")


def play_alert_sound(sound_type=MB_ICONHAND):
    get_api().MessageBeep(sound_type)
