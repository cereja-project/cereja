"""Native ABI and legacy automation contracts without touching desktop input."""

import ctypes
from ctypes import wintypes
import importlib
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch


UNDECLARED = object()


class FakeFunction:
    def __init__(self, name):
        self.name = name
        self.argtypes = UNDECLARED
        self.restype = UNDECLARED
        self.calls = []
        self.implementation = None

    def __call__(self, *arguments):
        self.calls.append(arguments)
        if self.implementation is not None:
            return self.implementation(*arguments)
        if self.name == 'VkKeyScanW':
            return ord(getattr(arguments[0], 'value', arguments[0]))
        if self.name == 'MapVirtualKeyW':
            return 0x1E
        return 1


class FakeDLL:
    def __init__(self):
        self.functions = {}

    def __getattr__(self, name):
        return self.functions.setdefault(name, FakeFunction(name))


class TestCommonBindingImports(unittest.TestCase):
    def test_common_module_and_capture_import_without_native_initialization(self):
        root = Path(__file__).resolve().parents[1]
        code = '''
import ctypes
import sys
from unittest.mock import patch
class ForbiddenLoader:
    def __getattr__(self, name):
        raise AssertionError('legacy DLL initialization: ' + name)
with patch.object(ctypes, 'WinDLL', side_effect=AssertionError('DLL initialization'), create=True), \
     patch.object(ctypes, 'windll', ForbiddenLoader(), create=True):
    import cereja.system._windows.types
    import cereja.system._windows.api
    import cereja.system._windows.capture
    import cereja.system._screen_capture
assert 'cereja.system._win32' not in sys.modules
assert 'tkinter' not in sys.modules
assert 'numpy' not in sys.modules
'''
        result = subprocess.run([sys.executable, '-c', code], cwd=root,
                                env=dict(os.environ, PYTHONPATH=str(root)),
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr, '')


@unittest.skipUnless(sys.platform == 'win32', 'Windows ABI and ctypes calling convention')
class TestWin32BindingABI(unittest.TestCase):
    def setUp(self):
        self.native = importlib.import_module('cereja.system._windows.api')
        self.types = importlib.import_module('cereja.system._windows.types')
        self.user, self.gdi = FakeDLL(), FakeDLL()

        def library(name, **kwargs):
            self.assertTrue(kwargs.get('use_last_error'))
            return {'user32': self.user, 'gdi32': self.gdi}[name]

        self.loader = patch.object(ctypes, 'WinDLL', side_effect=library)
        self.loader.start()
        self.addCleanup(self.loader.stop)
        self.api = self.native._Win32()

    def test_all_loaded_exports_have_declared_arguments_and_return_types(self):
        functions = {**self.user.functions, **self.gdi.functions}
        self.assertGreater(len(functions), 35)
        for name, function in functions.items():
            with self.subTest(function=name):
                self.assertIsNot(function.argtypes, UNDECLARED)
                self.assertIsNot(function.restype, UNDECLARED)
                self.assertIsInstance(function.argtypes, (tuple, list))

    def test_windows_message_and_pointer_output_signatures(self):
        pointer = ctypes.POINTER
        dib_arguments = [
            wintypes.HDC, pointer(self.native._BitmapInfo), wintypes.UINT,
            pointer(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD,
        ]
        expected = {
            'SendMessageW': (ctypes.c_ssize_t, [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]),
            'PostMessageW': (wintypes.BOOL, [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]),
            'GetWindowRect': (wintypes.BOOL, [wintypes.HWND, pointer(wintypes.RECT)]),
            'GetClientRect': (wintypes.BOOL, [wintypes.HWND, pointer(wintypes.RECT)]),
            'ClientToScreen': (wintypes.BOOL, [wintypes.HWND, pointer(wintypes.POINT)]),
            'GetWindowThreadProcessId': (wintypes.DWORD, [wintypes.HWND, pointer(wintypes.DWORD)]),
            'GetWindowTextW': (ctypes.c_int, [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]),
            'GetWindowTextLengthW': (ctypes.c_int, [wintypes.HWND]),
            'SetWindowTextW': (wintypes.BOOL, [wintypes.HWND, wintypes.LPCWSTR]),
            'GetForegroundWindow': (wintypes.HWND, []),
            'GetAsyncKeyState': (ctypes.c_short, [ctypes.c_int]),
            'VkKeyScanW': (ctypes.c_short, [wintypes.WCHAR]),
            'MapVirtualKeyW': (wintypes.UINT, [wintypes.UINT, wintypes.UINT]),
            'mouse_event': (None, [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.DWORD, ctypes.c_size_t]),
            'PrintWindow': (wintypes.BOOL, [wintypes.HWND, wintypes.HDC, wintypes.UINT]),
            'CreateDIBSection': (wintypes.HBITMAP, dib_arguments),
        }
        for name, (restype, argtypes) in expected.items():
            with self.subTest(function=name):
                function = getattr(self.api, name)
                self.assertIs(function.restype, restype)
                self.assertEqual(list(function.argtypes), argtypes)

    def test_message_roundtrip_does_not_truncate_handles_parameters_or_result(self):
        bits = ctypes.sizeof(ctypes.c_void_p) * 8
        hwnd = (1 << (bits - 2)) + 0x1234
        wparam = (1 << bits) - 17
        lparam = -(1 << (bits - 2)) + 71
        expected_result = (1 << (bits - 2)) + 91
        observed = []

        @ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t)
        def native_message(window, message, word, long_word):
            observed.append((window, message, word, long_word))
            return expected_result

        self.user.functions['SendMessageW'] = native_message
        api = self.native._Win32()
        result = api.SendMessageW(hwnd, 0x400, wparam, lparam)
        self.assertEqual(result, expected_result)
        self.assertEqual(observed, [(hwnd, 0x400, wparam, lparam)])
        self.assertEqual(ctypes.sizeof(self.types.LRESULT), ctypes.sizeof(ctypes.c_void_p))
        self.assertEqual(ctypes.sizeof(self.types.ULONG_PTR), ctypes.sizeof(ctypes.c_void_p))

    def test_enum_callback_roundtrip_preserves_hwnd_and_python_context_pointer(self):
        hwnd = (1 << (ctypes.sizeof(ctypes.c_void_p) * 8 - 2)) + 59
        received = []
        context = ctypes.py_object(received)
        address = ctypes.cast(ctypes.pointer(context), ctypes.c_void_p).value

        @self.native.ENUMWINDOWSPROC
        def callback(window, parameter):
            values = ctypes.cast(parameter, ctypes.POINTER(ctypes.py_object)).contents.value
            values.append(window)
            return True

        @ctypes.WINFUNCTYPE(wintypes.BOOL, self.native.ENUMWINDOWSPROC, wintypes.LPARAM)
        def enumerate_windows(visitor, parameter):
            return visitor(hwnd, parameter)

        self.user.functions['EnumWindows'] = enumerate_windows
        api = self.native._Win32()
        self.assertTrue(api.EnumWindows(callback, address))
        self.assertEqual(received, [hwnd])

    def test_monitor_callback_preserves_negative_coordinates_and_context(self):
        observed = []
        handle = (1 << (ctypes.sizeof(ctypes.c_void_p) * 8 - 2)) + 97
        rectangle = wintypes.RECT(-1920, -200, 0, 880)

        @self.native.MONITORENUMPROC
        def callback(monitor, dc, bounds, parameter):
            observed.append((monitor, dc, bounds.contents.left, bounds.contents.top, parameter))
            return True

        self.assertTrue(callback(handle, handle + 1, ctypes.byref(rectangle), -23))
        self.assertEqual(observed, [(handle, handle + 1, -1920, -200, -23)])

    def test_structure_layouts_match_windows_headers(self):
        self.assertEqual(ctypes.sizeof(self.types._BitmapInfoHeader), 40)
        self.assertEqual(ctypes.sizeof(self.types._MonitorInfo), 104)
        self.assertEqual(ctypes.sizeof(self.types.POINT), 8)
        self.assertEqual(ctypes.sizeof(self.types.RECT), 16)
        pointer_size = ctypes.sizeof(ctypes.c_void_p)
        self.assertEqual(ctypes.sizeof(self.types._CursorInfo), 24 if pointer_size == 8 else 20)
        self.assertEqual(ctypes.sizeof(self.types._IconInfo), 32 if pointer_size == 8 else 20)


@unittest.skipUnless(sys.platform == 'win32', 'Legacy Windows API')
class TestLegacySharedBindings(unittest.TestCase):
    def setUp(self):
        self.native = importlib.import_module('cereja.system._windows.api')
        self.user, self.gdi = FakeDLL(), FakeDLL()
        with patch.object(ctypes, 'WinDLL', side_effect=lambda name, **_: {'user32': self.user, 'gdi32': self.gdi}[name]):
            self.api = self.native._Win32()
        self.window_module = importlib.import_module('cereja.system._windows.window')
        self.keyboard_module = importlib.import_module('cereja.system._windows.keyboard')
        self.mouse_module = importlib.import_module('cereja.system._windows.mouse')
        self.common_module = importlib.import_module('cereja.system._windows.common')
        keyboard = self.keyboard_module.Keyboard
        for attribute in ('_Keyboard__KEY_NAME_TO_CODE', '_Keyboard__KEY_CODE_TO_NAME', '_Keyboard__KEY_MAP_READY'):
            original = getattr(keyboard, attribute)
            self.addCleanup(setattr, keyboard, attribute, original)
        keyboard._Keyboard__KEY_MAP_READY = False
        for module in (self.native, self.window_module, self.keyboard_module, self.mouse_module, self.common_module):
            patcher = patch.object(module, 'get_api', return_value=self.api, create=True)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.hwnd = (1 << (ctypes.sizeof(ctypes.c_void_p) * 8 - 2)) + 17
        for function in self.user.functions.values():
            function.calls.clear()

    def assert_no_foreground_or_global_input(self):
        for name in ('SetForegroundWindow', 'BringWindowToTop', 'SetCursorPos', 'mouse_event', 'ShowWindow'):
            with self.subTest(function=name):
                self.assertEqual(getattr(self.api, name).calls, [])

    def test_background_mouse_click_uses_shared_message_api_only(self):
        mouse = self.mouse_module.Mouse(hwnd=self.hwnd, is_async=True)
        self.assertIs(mouse.user32, self.api)
        mouse.click_left(position=(12, 34))
        self.assertEqual(self.api.PostMessageW.calls, [
            (self.hwnd, 0x200, 0, (34 << 16) | 12),
            (self.hwnd, 0x201, 1, (34 << 16) | 12),
            (self.hwnd, 0x202, 0, (34 << 16) | 12),
        ])
        self.assertEqual(self.api.SendMessageW.calls, [])
        self.assert_no_foreground_or_global_input()

    def test_background_multiple_clicks_keep_down_up_pairs_and_button_flags(self):
        for button, down, up, flag in (('left', 0x201, 0x202, 1), ('right', 0x204, 0x205, 2)):
            with self.subTest(button=button), patch.object(self.mouse_module.time, 'sleep'):
                self.api.PostMessageW.calls.clear()
                mouse = self.mouse_module.Mouse(hwnd=self.hwnd)
                getattr(mouse, 'click_' + button)(position=(5, 7), n_clicks=2)
                coordinate = (7 << 16) | 5
                self.assertEqual(self.api.PostMessageW.calls, [
                    (self.hwnd, 0x200, 0, coordinate),
                    (self.hwnd, down, flag, coordinate), (self.hwnd, up, 0, coordinate),
                    (self.hwnd, down, flag, coordinate), (self.hwnd, up, 0, coordinate),
                ])
                self.assert_no_foreground_or_global_input()

    def test_invalid_click_count_posts_no_mouse_messages(self):
        mouse = self.mouse_module.Mouse(hwnd=self.hwnd)
        for count in (0, -1):
            with self.subTest(count=count), self.assertRaises(ValueError):
                mouse.click_left(position=(5, 7), n_clicks=count)
        self.assertEqual(self.api.PostMessageW.calls, [])
        self.assert_no_foreground_or_global_input()

    def test_background_keyboard_combo_preserves_target_and_event_order(self):
        for asynchronous in (False, True):
            with self.subTest(asynchronous=asynchronous), patch.object(self.keyboard_module.time, 'sleep'):
                self.api.PostMessageW.calls.clear()
                self.api.SendMessageW.calls.clear()
                keyboard = self.keyboard_module.Keyboard(hwnd=self.hwnd, is_async=asynchronous)
                keyboard.key_press('CTRL+A')
                expected = self.api.PostMessageW if asynchronous else self.api.SendMessageW
                other = self.api.SendMessageW if asynchronous else self.api.PostMessageW
                self.assertEqual([(hwnd, message, vk) for hwnd, message, vk, _ in expected.calls], [
                    (self.hwnd, 0x100, 17), (self.hwnd, 0x100, 65),
                    (self.hwnd, 0x101, 65), (self.hwnd, 0x101, 17),
                ])
                for _, message, _, lparam in expected.calls:
                    self.assertEqual(lparam & 0xFFFF, 1)
                    self.assertEqual((lparam >> 16) & 0xFF, 0x1E)
                    self.assertEqual(bool(lparam & (1 << 31)), message == 0x101)
                self.assertEqual(other.calls, [])
                self.assert_no_foreground_or_global_input()

    def test_window_geometry_and_process_id_use_typed_output_pointers(self):
        def bounds(hwnd, output):
            self.assertEqual(hwnd, self.hwnd)
            ctypes.cast(output, ctypes.POINTER(wintypes.RECT))[0] = wintypes.RECT(-1920, -30, -1280, 450)
            return True

        def process_id(hwnd, output):
            self.assertEqual(hwnd, self.hwnd)
            ctypes.cast(output, ctypes.POINTER(wintypes.DWORD))[0] = 0xF1234567
            return 41

        self.api.GetWindowRect.implementation = bounds
        self.api.GetWindowThreadProcessId.implementation = process_id
        window = self.window_module.Window(self.hwnd)
        self.assertEqual(window.dimensions, (-1920, -30, -1280, 450))
        self.assertEqual(window.size, (640, 480))
        self.assertEqual(window.pid, 0xF1234567)
        window.dimensions = (-1200, -20, -600, 380)
        self.assertEqual(self.api.SetWindowPos.calls, [(self.hwnd, 0, -1200, -20, 600, 400, 0)])

    def test_legacy_enumeration_roundtrip_uses_a_valid_python_context_pointer(self):
        handles = [self.hwnd, self.hwnd + 1]

        def enumerate_windows(callback, parameter):
            # Passing a py_object directly to a declared LPARAM is invalid.
            parameter = wintypes.LPARAM(parameter).value
            for hwnd in handles:
                if not callback(hwnd, parameter):
                    return False
            return True

        self.api.EnumWindows.implementation = enumerate_windows
        windows = self.window_module.Window.get_all_windows()
        self.assertEqual([window.hwnd for window in windows], handles)

    def test_public_exports_and_legacy_shim_preserve_class_identity(self):
        import cereja
        import cereja.system
        from cereja.system import _win32

        for name, canonical in (('Window', self.window_module.Window),
                                ('Keyboard', self.keyboard_module.Keyboard),
                                ('Mouse', self.mouse_module.Mouse)):
            with self.subTest(name=name):
                self.assertIs(getattr(_win32, name), canonical)
                self.assertIs(getattr(cereja.system, name), canonical)
                self.assertIs(getattr(cereja, name), canonical)


if __name__ == '__main__':
    unittest.main()
