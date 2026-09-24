"""Timing and alert helpers retained for the legacy Windows API."""

from ...utils.time import Timer

from .api import get_api
from .constants import AlertSound


class Time:
    """Adapt Timer to the historical Windows timing interface.

    Reading ``time`` starts an idle timer and resets ``last_check_time``.
    Stopping freezes the reported duration until the next explicit ``start``.
    """

    def __init__(self):
        self._timer = Timer(start=False)
        self._last_check_timer = Timer(start=False)
        self._stopped_elapsed = None

    @property
    def t0(self):
        # Timer has no public start timestamp accessor. Only this legacy
        # compatibility property reads its stored timestamp directly.
        return self._timer._start if self._timer.started else None

    @property
    def time(self):
        if not self._timer.started:
            self.start()
        self._last_check_timer.start()
        return self._timer.elapsed if self._stopped_elapsed is None else self._stopped_elapsed

    @property
    def last_check_time(self):
        if not self._last_check_timer.started:
            raise RuntimeError("Time counting has not started. Use Time.start method.")
        return self._last_check_timer.elapsed

    def start(self):
        self._timer.start()
        self._last_check_timer.start()
        self._stopped_elapsed = None

    def stop(self):
        if not self._timer.started:
            raise RuntimeError("Time counting has not started. Use Time.start method.")
        if self._stopped_elapsed is None:
            self._stopped_elapsed = self._timer.elapsed


def play_alert_sound(sound_type=AlertSound.ICONHAND):
    """Play a Windows alert using the shared typed API and sound constants."""
    get_api().MessageBeep(sound_type)
