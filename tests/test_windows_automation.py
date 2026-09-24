"""Portable checks for automation behavior with no real desktop input."""

import ctypes
import unittest
from unittest.mock import Mock, patch

from cereja.system._windows import keyboard, mouse
from cereja.system._windows.constants import MouseEvent, VirtualKey
from cereja.utils import time as timer_module


class TestKeyboardTiming(unittest.TestCase):
    def test_hold_uses_existing_timer_and_releases_after_duration(self):
        self.assertIs(keyboard.Timer, timer_module.Timer)
        clock = [10.0]
        messages = []
        device = keyboard.Keyboard.__new__(keyboard.Keyboard)
        device._send_key_down = lambda key: messages.append(("down", key, clock[0]))
        device._send_key_up = lambda key: messages.append(("up", key, clock[0]))

        def advance(seconds):
            clock[0] += seconds

        with patch.object(timer_module.time, "monotonic", side_effect=lambda: clock[0]), \
                patch.object(keyboard.time, "sleep", side_effect=advance):
            device._press_and_wait(65, 0.025)

        self.assertEqual([message[:2] for message in messages], [("down", 65)] * 3 + [("up", 65)])
        self.assertGreaterEqual(messages[-1][2] - 10.0, 0.025)
        self.assertLess(messages[-1][2] - 10.0, 0.04)

    def test_zero_hold_still_sends_release_without_pressing(self):
        device = keyboard.Keyboard.__new__(keyboard.Keyboard)
        device._send_key_down = Mock()
        device._send_key_up = Mock()
        device._press_and_wait(65, 0)
        device._send_key_down.assert_not_called()
        device._send_key_up.assert_called_once_with(65)

    def test_grouped_virtual_keys_do_not_add_enum_names_to_public_key_aliases(self):
        mapping = keyboard.Keyboard._Keyboard__KEY_NAME_TO_CODE
        self.assertEqual(mapping["CTRL"], 17)
        self.assertEqual(mapping["F9"], 120)
        self.assertTrue(all(not name.startswith(("DIGIT_", "OEM_")) for name in mapping))
        self.assertIn("0", mapping)
        self.assertIn("'", mapping)
        self.assertTrue(all(type(value) is int for value in mapping.values()))
        self.assertEqual(VirtualKey.OEM_QUOTE, 222)


class TestMouseFlags(unittest.TestCase):
    def test_right_release_uses_native_flag_and_click_keeps_both_events(self):
        self.assertEqual(MouseEvent.RIGHTUP, 0x0010)
        self.assertEqual(mouse.Mouse._button_envent_map["right_up"], 0x0010)
        self.assertEqual(mouse.Mouse._button_envent_map["right_click"], 0x0018)
        api = Mock()
        with patch.object(mouse, "get_api", return_value=api), patch.object(mouse.time, "sleep"):
            device = mouse.Mouse()
            device.click_right(position=(12, 34))
        api.SetCursorPos.assert_called_once_with(12, 34)
        api.mouse_event.assert_called_once_with(0x0018, 12, 34, 0, 0)
        self.assertEqual(ctypes.c_uint(api.mouse_event.call_args.args[0]).value, 0x0018)
        api.PostMessageW.assert_not_called()
        api.SendMessageW.assert_not_called()


if __name__ == "__main__":
    unittest.main()
