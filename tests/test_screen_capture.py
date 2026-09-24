"""Desktop capture contracts; native tests draw only into synthetic bitmaps."""

from contextlib import nullcontext
import ctypes
from dataclasses import FrozenInstanceError
import os
from pathlib import Path
import subprocess
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from cereja.system import _screen_capture as capture


PRIMARY = capture.ScreenMonitor("primary", "Primary", 0, 0, 8, 6, True)
LEFT = capture.ScreenMonitor("left", "Left", -8, -2, 8, 6, False)


class FakeBackend:
    def __init__(self):
        self.monitors = (PRIMARY, LEFT)
        self.closed = 0
        self.calls = []

    def list_monitors(self):
        return self.monitors

    def grab(self, left, top, width, height, include_cursor):
        self.calls.append((left, top, width, height, include_cursor))
        return b"\x01\x02\x03\xff" * width * height

    def close(self):
        self.closed += 1


class ScreenCaptureContractTest(unittest.TestCase):
    def setUp(self):
        self.backend = FakeBackend()
        self.factory = patch.object(capture, "_WindowsCaptureBackend", return_value=self.backend)
        self.factory.start()
        self.addCleanup(self.factory.stop)

    def test_default_frame_is_primary_and_owned(self):
        with capture.ScreenCapture() as screen:
            self.assertEqual(screen.list_monitors(), (PRIMARY, LEFT))
            frame = screen.grab()
            self.assertEqual((frame.left, frame.top, frame.width, frame.height), (0, 0, 8, 6))
            self.assertIsInstance(frame.bgra, bytes)
            self.assertEqual(frame.bgra, b"\x01\x02\x03\xff" * 48)
            with self.assertRaises(FrozenInstanceError):
                frame.width = 0
        self.assertEqual(self.backend.closed, 1)
        self.assertEqual(frame.bgra[:4], b"\x01\x02\x03\xff")
        self.assertTrue(self.backend.calls[-1][-1])

    def test_monitor_object_uses_current_bounds(self):
        with capture.ScreenCapture(include_cursor=False) as screen:
            by_id = screen.grab(monitor="left")
            by_object = screen.grab(monitor=LEFT)
            self.assertEqual(by_id, by_object)
            changed = capture.ScreenMonitor("left", "Left", -4, 0, 4, 3, False)
            self.backend.monitors = (PRIMARY, changed)
            frame = screen.grab(monitor=LEFT)
            self.assertEqual((frame.left, frame.width), (-4, 4))
            self.assertFalse(self.backend.calls[-1][-1])

    def test_negative_region_and_invalid_selectors(self):
        with capture.ScreenCapture() as screen:
            frame = screen.grab(region=(-7, -1, 3, 2))
            self.assertEqual((frame.left, frame.top, frame.width, frame.height), (-7, -1, 3, 2))
            cases = (
                ({"monitor": "missing"}, ValueError),
                ({"monitor": 1}, TypeError),
                ({"monitor": PRIMARY, "region": (0, 0, 1, 1)}, ValueError),
                ({"region": (0, 0, 0, 1)}, ValueError),
                ({"region": (0, 0, 1, -1)}, ValueError),
                ({"region": (True, 0, 1, 1)}, TypeError),
                ({"region": (0.5, 0, 1, 1)}, TypeError),
                ({"region": [0, 0, 1, 1]}, TypeError),
                ({"region": (0, 0, 1)}, TypeError),
                ({"region": (-1, 0, 2, 2)}, ValueError),
                ({"region": (100, 0, 1, 1)}, ValueError),
            )
            for args, error in cases:
                with self.subTest(args=args), self.assertRaises(error):
                    screen.grab(**args)
            self.assertEqual(len(self.backend.calls), 1)

    def test_missing_display_and_primary_report_errors(self):
        with capture.ScreenCapture() as screen:
            for monitors in ((), (LEFT,)):
                self.backend.monitors = monitors
                with self.assertRaises(OSError):
                    screen.grab()

    def test_cleanup_on_failure_and_after_close(self):
        screen = capture.ScreenCapture()
        with self.assertRaisesRegex(RuntimeError, "consumer failure"):
            with screen:
                raise RuntimeError("consumer failure")
        screen.close()
        self.assertEqual(self.backend.closed, 1)
        for operation in (screen.grab, screen.list_monitors, screen.__enter__):
            with self.assertRaisesRegex(RuntimeError, "closed"):
                operation()

    def test_native_failure_is_not_a_black_frame(self):
        self.backend.grab = Mock(side_effect=OSError("capture failed"))
        with self.assertRaisesRegex(OSError, "capture failed"):
            with capture.ScreenCapture() as screen:
                screen.grab()
        self.assertEqual(self.backend.closed, 1)

    def test_thread_affinity_includes_close(self):
        with capture.ScreenCapture() as screen:
            failures = []

            def foreign_thread():
                for operation in (screen.grab, screen.list_monitors, screen.close):
                    try:
                        operation()
                    except RuntimeError as error:
                        failures.append(str(error))

            thread = threading.Thread(target=foreign_thread)
            thread.start()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(len(failures), 3)
            self.assertEqual(self.backend.closed, 0)

    def test_cursor_option_is_explicit_boolean(self):
        with self.assertRaises(TypeError):
            capture.ScreenCapture(include_cursor=1)


@unittest.skipUnless(sys.platform == "win32", "Win32 structures and calls")
class NativeLifecycleTest(unittest.TestCase):
    def setUp(self):
        ctypes.set_last_error(0)
        self.buffer = ctypes.create_string_buffer(8 * 6 * 4)
        self.api = SimpleNamespace(
            GetDC=Mock(return_value=11), CreateCompatibleDC=Mock(return_value=12),
            CreateDIBSection=Mock(side_effect=self.create_dib),
            SelectObject=Mock(return_value=13), DeleteObject=Mock(return_value=True),
            DeleteDC=Mock(return_value=True), ReleaseDC=Mock(return_value=True),
            GdiFlush=Mock(return_value=True), BitBlt=Mock(return_value=True),
            GetCursorInfo=Mock(side_effect=self.cursor_info),
            CopyIcon=Mock(return_value=21), GetIconInfo=Mock(side_effect=self.icon_info),
            DrawIconEx=Mock(return_value=True), DestroyIcon=Mock(return_value=True),
            physical_pixels=nullcontext,
        )
        self.backend = object.__new__(capture._WindowsCaptureBackend)
        self.backend.api = self.api
        self.backend.surface = None
        self.addCleanup(self.backend.close)

    def create_dib(self, dc, pointer, usage, bits, section, offset):
        info = ctypes.cast(pointer, ctypes.POINTER(capture._BitmapInfo)).contents
        self.assertEqual((info.bmiHeader.biWidth, info.bmiHeader.biHeight), (8, -6))
        ctypes.cast(bits, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.addressof(self.buffer)
        return 14

    def cursor_info(self, pointer):
        cursor = ctypes.cast(pointer, ctypes.POINTER(capture._CursorInfo)).contents
        self.assertEqual(cursor.cbSize, ctypes.sizeof(capture._CursorInfo))
        cursor.flags, cursor.hCursor = 1, 20
        cursor.ptScreenPos.x, cursor.ptScreenPos.y = -7, -1
        return True

    def icon_info(self, icon, pointer):
        info = ctypes.cast(pointer, ctypes.POINTER(capture._IconInfo)).contents
        info.xHotspot, info.yHotspot = 2, 3
        info.hbmMask, info.hbmColor = 22, 23
        return True

    def test_native_calls_preserve_coordinates_and_own_pixels(self):
        ctypes.memmove(self.buffer, b"\x01\x02\x03\x00" * 48, 192)
        first = self.backend.grab(-8, -2, 8, 6, True)
        self.api.BitBlt.assert_called_with(12, 0, 0, 8, 6, 11, -8, -2, 0x40CC0020)
        self.api.DrawIconEx.assert_called_with(12, -1, -2, 21, 0, 0, 0, None, 3)
        ctypes.memset(self.buffer, 9, 192)
        second = self.backend.grab(-8, -2, 8, 6, False)
        self.assertEqual(first, b"\x01\x02\x03\xff" * 48)
        self.assertEqual(second, b"\x09\x09\x09\xff" * 48)
        self.api.CreateDIBSection.assert_called_once()
        self.api.GetCursorInfo.assert_called_once()
        self.backend.close()
        self.api.SelectObject.assert_called_with(12, 13)
        self.api.ReleaseDC.assert_called_once_with(None, 11)
        self.assertEqual(first[:4], b"\x01\x02\x03\xff")
        self.assertEqual([call.args[0] for call in self.api.DeleteObject.call_args_list], [22, 23, 14])
        self.api.DestroyIcon.assert_called_once_with(21)

    def test_allocation_failure_releases_partial_resources(self):
        self.api.CreateDIBSection.side_effect = None
        self.api.CreateDIBSection.return_value = None
        with self.assertRaisesRegex(OSError, "CreateDIBSection"):
            self.backend.grab(0, 0, 8, 6, False)
        self.api.DeleteDC.assert_called_once_with(12)
        self.api.ReleaseDC.assert_called_once_with(None, 11)
        self.assertIsNone(self.backend.surface)

    def test_capture_failure_propagates_and_close_releases_surface(self):
        self.api.BitBlt.return_value = False
        with self.assertRaisesRegex(OSError, "BitBlt"):
            self.backend.grab(0, 0, 8, 6, False)
        self.backend.close()
        self.api.DeleteObject.assert_called_once_with(14)
        self.api.ReleaseDC.assert_called_once_with(None, 11)

    def test_cursor_failure_frees_owned_handles(self):
        self.api.DrawIconEx.return_value = False
        with self.assertRaisesRegex(OSError, "DrawIconEx"):
            self.backend.draw_cursor(12, 0, 0)
        self.assertEqual([call.args[0] for call in self.api.DeleteObject.call_args_list], [22, 23])
        self.api.DestroyIcon.assert_called_once_with(21)

    def test_hidden_or_suppressed_cursor_is_not_copied(self):
        for flags in (0, 2, 3):
            def hidden(pointer):
                ctypes.cast(pointer, ctypes.POINTER(capture._CursorInfo)).contents.flags = flags
                return True
            self.api.GetCursorInfo.side_effect = hidden
            self.backend.draw_cursor(12, 0, 0)
        self.api.CopyIcon.assert_not_called()

    def test_dpi_context_restored_on_exception(self):
        api = object.__new__(capture._Win32)
        api.SetThreadDpiAwarenessContext = Mock(side_effect=[37, 41])
        with self.assertRaisesRegex(ValueError, "body"):
            with api.physical_pixels():
                raise ValueError("body")
        self.assertEqual(api.SetThreadDpiAwarenessContext.call_args_list[-1].args, (37,))

    def test_cleanup_attempts_all_handles_after_delete_failure(self):
        self.backend.grab(0, 0, 8, 6, False)
        self.api.DeleteObject.return_value = False
        with self.assertRaisesRegex(OSError, "DeleteObject"):
            self.backend.close()
        self.api.DeleteDC.assert_called_once_with(12)
        self.api.ReleaseDC.assert_called_once_with(None, 11)

    def test_monitor_enumeration_orders_primary_and_preserves_negative_bounds(self):
        self.api.monitor_callback = lambda callback: callback

        def information(handle, pointer):
            info = ctypes.cast(pointer, ctypes.POINTER(capture._MonitorInfo)).contents
            self.assertEqual(info.cbSize, ctypes.sizeof(capture._MonitorInfo))
            info.szDevice = rf"\\.\DISPLAY{handle}"
            bounds = (0, 0, 8, 6) if handle == 1 else (-8, -2, 0, 4)
            info.rcMonitor = ctypes.wintypes.RECT(*bounds)
            info.dwFlags = int(handle == 1)
            return True

        self.api.GetMonitorInfoW = Mock(side_effect=information)
        self.api.EnumDisplayMonitors = lambda _dc, _rect, callback, _arg: (
            callback(2, None, None, 0) and callback(1, None, None, 0)
        )
        monitors = self.backend.list_monitors()
        self.assertEqual(monitors[0].id, r"\\.\DISPLAY1")
        self.assertEqual(monitors[0].name, "DISPLAY1")
        self.assertTrue(monitors[0].is_primary)
        self.assertEqual((monitors[1].left, monitors[1].top), (-8, -2))

    def test_monitor_callback_error_propagates_instead_of_partial_results(self):
        self.api.monitor_callback = lambda callback: callback
        self.api.GetMonitorInfoW = Mock(return_value=False)
        self.api.EnumDisplayMonitors = lambda _dc, _rect, callback, _arg: callback(1, None, None, 0)
        with self.assertRaisesRegex(OSError, "GetMonitorInfoW"):
            self.backend.list_monitors()


@unittest.skipUnless(sys.platform == "win32", "Synthetic native Windows DIBs")
class SyntheticDibTest(unittest.TestCase):
    """Exercise GDI composition without reading or capturing the desktop."""

    def setUp(self):
        self.api = capture._Win32()
        self.target = capture._Surface(self.api, 2, 2)
        self.addCleanup(self.target.close)
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.gdi = ctypes.WinDLL("gdi32", use_last_error=True)
        self.user.CreateIconIndirect.argtypes = [ctypes.POINTER(capture._IconInfo)]
        self.user.CreateIconIndirect.restype = ctypes.wintypes.HANDLE
        self.gdi.CreateBitmap.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.wintypes.UINT,
                                         ctypes.wintypes.UINT, ctypes.c_void_p]
        self.gdi.CreateBitmap.restype = ctypes.wintypes.HBITMAP

    def bitmap(self, width, height, data):
        buffer = ctypes.create_string_buffer(data)
        bitmap = capture._checked(self.gdi.CreateBitmap(width, height, 1, 1, buffer), "CreateBitmap")
        self.addCleanup(self.api.DeleteObject, bitmap)
        return bitmap

    def cursor(self, mask, color=None, hotspot=(0, 0)):
        info = capture._IconInfo(False, hotspot[0], hotspot[1], mask, color)
        handle = capture._checked(self.user.CreateIconIndirect(ctypes.byref(info)), "CreateIconIndirect")
        self.addCleanup(self.api.DestroyIcon, handle)
        return handle

    def draw(self, icon, position=(0, 0), origin=(0, 0)):
        backend = object.__new__(capture._WindowsCaptureBackend)
        backend.api = self.api
        original = self.api.GetCursorInfo

        def synthetic_cursor(pointer):
            info = ctypes.cast(pointer, ctypes.POINTER(capture._CursorInfo)).contents
            info.flags, info.hCursor = 1, icon
            info.ptScreenPos.x, info.ptScreenPos.y = position
            return True

        self.api.GetCursorInfo = synthetic_cursor
        try:
            backend.draw_cursor(self.target.dc, *origin)
        finally:
            self.api.GetCursorInfo = original
        return self.target.copy_bytes()

    def test_monochrome_transparency_white_inversion_and_black(self):
        ctypes.memmove(self.target.bits, b"\x14\x28\x3c\xff" * 4, 16)
        # Two AND rows followed by two XOR rows, each word-aligned.
        mask = self.bitmap(2, 4, b"\x80\x00\x80\x00\x40\x00\x80\x00")
        icon = self.cursor(mask)
        pixels = self.draw(icon)
        self.assertEqual(pixels, b"\x14\x28\x3c\xff\xff\xff\xff\xff"
                                b"\xeb\xd7\xc3\xff\x00\x00\x00\xff")

    def test_alpha_color_transparency_and_top_down_order(self):
        ctypes.memmove(self.target.bits, b"\x14\x28\x3c\xff" * 4, 16)
        color = capture._Surface(self.api, 2, 2)
        self.addCleanup(color.close)
        # CreateIconIndirect accepts the straight-alpha color bitmap.
        ctypes.memmove(color.bits, b"\x00\x00\xff\x80\xff\x00\x00\xff"
                                  b"\x00\x00\x00\x00\x00\xff\x00\xff", 16)
        mask = self.bitmap(2, 2, b"\x00\x00" * 2)
        pixels = self.draw(self.cursor(mask, color.bitmap))
        # Alpha rounding may differ by one across GDI versions.
        for actual, expected in zip(pixels[:3], (10, 20, 158)):
            self.assertLessEqual(abs(actual - expected), 1)
        self.assertEqual(pixels[3:], b"\xff\xff\x00\x00\xff"
                                    b"\x14\x28\x3c\xff\x00\xff\x00\xff")

    def test_hotspot_clips_at_negative_desktop_origin(self):
        ctypes.memmove(self.target.bits, b"\x14\x28\x3c\xff" * 4, 16)
        mask = self.bitmap(2, 4, b"\x80\x00\x80\x00\x40\x00\x80\x00")
        pixels = self.draw(self.cursor(mask, hotspot=(1, 1)), position=(-8, -2), origin=(-8, -2))
        self.assertEqual(pixels, b"\x00\x00\x00\xff" + b"\x14\x28\x3c\xff" * 3)


class ScreenCaptureImportTest(unittest.TestCase):
    def test_lazy_platform_exports_have_no_native_initialization(self):
        root = Path(__file__).resolve().parents[1]
        code = '''
import ctypes
from unittest.mock import patch
import sys
import cereja
import cereja.system
with patch.object(ctypes, "WinDLL", side_effect=AssertionError("native init"), create=True):
    for name in ("ScreenCapture", "ScreenFrame", "ScreenMonitor"):
        if sys.platform == "win32":
            assert name in dir(cereja)
            assert getattr(cereja, name) is getattr(cereja.system, name)
        else:
            assert name not in dir(cereja)
            assert name not in dir(cereja.system)
assert "cereja.system._win32" not in sys.modules
assert "tkinter" not in sys.modules
assert "numpy" not in sys.modules
'''
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=root,
            env=dict(os.environ, PYTHONPATH=str(root)), capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
