"""Compatibility timing behavior using the shared monotonic Timer."""

import unittest
from unittest.mock import patch

from cereja.system._windows.common import Time, play_alert_sound
from cereja.system._windows.constants import AlertSound


class TestWindowsTime(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        clock = patch('cereja.utils.time.time.monotonic', side_effect=lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)

    def test_first_time_read_starts_timer_and_tracks_last_read(self):
        timer = Time()
        self.assertIsNone(timer.t0)
        self.assertEqual(timer.time, 0)
        self.assertEqual(timer.t0, 100)
        self.now = 102.5
        self.assertEqual(timer.last_check_time, 2.5)
        self.assertEqual(timer.time, 2.5)
        self.now = 103
        self.assertEqual(timer.last_check_time, 0.5)

    def test_explicit_start_stop_and_restart_preserve_elapsed_contract(self):
        timer = Time()
        self.assertIsNone(timer.start())
        self.now = 104
        self.assertEqual(timer.time, 4)
        self.now = 106
        self.assertIsNone(timer.stop())
        self.now = 110
        self.assertEqual(timer.time, 6)
        timer.stop()
        self.now = 112
        self.assertEqual(timer.time, 6)
        self.assertEqual(timer.t0, 100)
        timer.start()
        self.assertEqual(timer.t0, 112)
        self.now = 113.25
        self.assertEqual(timer.time, 1.25)

    def test_last_check_time_advances_even_after_recorded_duration_is_frozen(self):
        timer = Time()
        timer.start()
        self.now = 102
        timer.stop()
        self.now = 105
        self.assertEqual(timer.time, 2)
        self.now = 107
        self.assertEqual(timer.last_check_time, 2)

    def test_idle_operations_report_that_start_is_required(self):
        timer = Time()
        with self.assertRaisesRegex(RuntimeError, 'has not started'):
            timer.stop()
        with self.assertRaisesRegex(RuntimeError, 'has not started'):
            _ = timer.last_check_time
        self.assertIsNone(timer.t0)

    def test_zero_duration_remains_frozen_after_stop(self):
        timer = Time()
        timer.start()
        timer.stop()
        self.now = 105
        self.assertEqual(timer.time, 0)


class TestWindowsAlert(unittest.TestCase):
    def test_alert_defaults_to_shared_enum_and_preserves_numeric_calls(self):
        with patch('cereja.system._windows.common.get_api') as factory:
            play_alert_sound()
            self.assertIs(factory.return_value.MessageBeep.call_args.args[0], AlertSound.ICONHAND)
            play_alert_sound(AlertSound.ICONQUESTION)
            factory.return_value.MessageBeep.assert_called_with(AlertSound.ICONQUESTION)
            play_alert_sound(0x40)
            factory.return_value.MessageBeep.assert_called_with(0x40)


if __name__ == '__main__':
    unittest.main()
