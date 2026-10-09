from collections import deque
import ctypes
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest

from cereja.ui._capabilities import CapabilityOptions
from cereja.ui.events import EOFEvent, InputErrorEvent, KeyEvent, ResizeEvent, WakeEvent
from cereja.ui import _win32
from cereja.ui.windows import WindowsBackend
from cereja.ui.terminal import TerminalCleanupError


def native_error(code):
    error = OSError(code, "fixture native failure")
    error.winerror = code
    return error


def key(unit=0, vk=0, *, modifiers=0, repeat=1, down=True):
    record = _win32.INPUT_RECORD()
    record.EventType = 1
    event = record.Event.KeyEvent
    event.bKeyDown = down
    event.wRepeatCount = repeat
    event.wVirtualKeyCode = vk
    event.uChar.UnicodeChar = unit
    event.dwControlKeyState = modifiers
    return record


def resize(width, height):
    record = _win32.INPUT_RECORD()
    record.EventType = 4
    record.Event.WindowBufferSizeEvent.dwSize.X = width
    record.Event.WindowBufferSizeEvent.dwSize.Y = height
    return record


class FakeAPI:
    def __init__(self):
        self.modes = {10: 0x47, 11: 3}
        self.cursor = (25, True)
        self.screen = (80, 25, 3, 4)
        self.log = []
        self.failures = {}
        self.records = deque()
        self.wait_results = deque()
        self.write_counts = deque()
        self.written = bytearray()
        self.next_event = 99
        self.event = threading.Event()
        self.wait_started = threading.Event()
        self.block_wait = False
        self.alternate = False
        self.wait_release = None
        self.two_wakes = threading.Event()

    def step(self, name, *args):
        self.log.append((name, *args))
        failure = self.failures.pop(name, None)
        if failure is not None:
            raise failure

    def stream_handle(self, stream):
        return getattr(stream, "handle", None)

    def get_mode(self, handle):
        self.step("get_mode", handle)
        return self.modes.get(handle)

    def set_mode(self, handle, mode):
        self.step(f"set_mode:{handle}", mode)
        self.modes[handle] = mode

    def get_cursor(self, handle):
        self.step("get_cursor", handle)
        return self.cursor

    def set_cursor(self, handle, size, visible):
        self.step("set_cursor", handle, size, visible)
        self.cursor = size, visible

    def get_screen(self, handle):
        self.step("get_screen", handle)
        return self.screen

    def set_position(self, handle, x, y):
        self.step("set_position", handle, x, y)
        if self.alternate and y >= self.screen[1]:
            raise native_error(87)

    def create_event(self):
        self.step("create_event")
        self.event.clear()
        self.next_event += 1
        return self.next_event

    def set_event(self, handle):
        self.step("set_event", handle)
        self.event.set()
        if sum(op[0] == "set_event" for op in self.log) >= 2:
            self.two_wakes.set()

    def close_handle(self, handle):
        self.step("close_handle", handle)

    def wait(self, handles, milliseconds):
        self.step("wait", tuple(handles), milliseconds)
        if self.block_wait:
            self.wait_started.set()
            if not self.event.wait(2):
                raise RuntimeError("fixture was not woken")
            if self.wait_release is not None and not self.wait_release.wait(2):
                raise RuntimeError("fixture wait was not released")
            return 0
        return self.wait_results.popleft() if self.wait_results else 0x102

    def read_input(self, handle, limit):
        self.step("read_input", handle, limit)
        return self.records.popleft() if self.records else ()

    def input_pending(self, handle):
        self.step('input_pending', handle)
        return len(self.records[0]) if self.records else 0

    def write_console(self, handle, data):
        self.step("write_console", handle, data)
        count = self.write_counts.popleft() if self.write_counts else len(data) // 2
        if type(count) is int and 0 < count <= len(data) // 2:
            self.written.extend(data[:count * 2])
            if data[:count * 2] == "\x1b[?1049h".encode("utf-16-le"):
                self.alternate = True
            elif data[:count * 2] == "\x1b[?1049l".encode("utf-16-le"):
                self.alternate = False
        return count


class WindowsBackendTests(unittest.TestCase):
    def test_sustained_wake_also_inspects_ready_key_and_paused_admission_does_not(self):
        backend, api, _ = self.acquired()
        api.records.append((key(ord('x')),))
        api.wait_results.extend((0, 0, 0))
        self.assertEqual(backend.wait(0, read_input=False), (WakeEvent(),))
        self.assertEqual(api.log[-1], ('wait', (backend._wake_handle,), 0))
        self.assertEqual(backend.wait(0), (KeyEvent('x', 'x'), WakeEvent()))
        self.assertEqual(backend.wait(0), (WakeEvent(),))

    def backend(self, api=None, **kwargs):
        api = api or FakeAPI()
        backend = WindowsBackend(io.StringIO(), io.StringIO(), _api=api,
                                 input_handle=10, output_handle=11,
                                 environ=kwargs.pop("environ", {}), **kwargs)
        self.addCleanup(backend.close)
        return backend, api

    def acquired(self, api=None, **kwargs):
        backend, api = self.backend(api, **kwargs)
        snapshot = backend.capture()
        backend.acquire("output_mode", snapshot)
        backend.acquire("input_mode", snapshot)
        self.addCleanup(backend.restore, "output_mode", snapshot)
        self.addCleanup(backend.restore, "input_mode", snapshot)
        return backend, api, snapshot

    def test_abi_uses_windows_widths_and_natural_alignment(self):
        self.assertEqual(ctypes.sizeof(_win32.COORD), 4)
        self.assertEqual(ctypes.sizeof(_win32.KEY_EVENT_RECORD), 16)
        self.assertEqual(ctypes.sizeof(_win32.INPUT_RECORD), 20)
        self.assertEqual(_win32.INPUT_RECORD.Event.offset, 4)
        self.assertEqual(_win32.KEY_EVENT_RECORD.dwControlKeyState.offset, 12)

    def test_constructor_is_read_only_and_vt_is_confirmed_at_entry(self):
        backend, api = self.backend()
        self.assertTrue(backend.capabilities.plain)
        self.assertTrue(backend.needs_output_probe)
        self.assertFalse(any(op[0].startswith("set_") or op[0] == "create_event"
                             for op in api.log))
        snapshot = backend.capture()
        backend.acquire("output_mode", snapshot)
        self.assertFalse(backend.capabilities.plain)
        self.assertTrue(api.modes[11] & 4)
        backend.restore("output_mode", snapshot)
        self.assertEqual(api.modes[11], 3)

    def test_pipe_or_explicit_cursor_false_never_probe_or_allocate(self):
        for missing in (10, 11):
            api = FakeAPI()
            del api.modes[missing]
            backend, api = self.backend(api, options=CapabilityOptions(color=24, cursor=True))
            self.assertTrue(backend.capabilities.plain)
            self.assertFalse(backend.needs_output_probe)
            snapshot = backend.capture()
            self.assertEqual(backend.wait(1), ())
            self.assertFalse(backend.wake())
            self.assertFalse(any(op[0] == "create_event" for op in api.log))
            backend.restore("output_mode", snapshot)
        backend, _ = self.backend(options=CapabilityOptions(cursor=False))
        self.assertFalse(backend.needs_output_probe)

    def test_vt_expected_failure_is_plain_other_failure_preserves_error(self):
        for code in (50, 87):
            backend, api = self.backend()
            snapshot = backend.capture()
            api.failures["set_mode:11"] = native_error(code)
            backend.acquire("output_mode", snapshot)
            self.assertTrue(backend.capabilities.plain)
            self.assertEqual(api.written, b"")
            backend.restore("output_mode", snapshot)
            self.assertEqual(api.modes[11], 3)
        backend, api = self.backend()
        snapshot = backend.capture()
        failure = native_error(6)
        api.failures["set_mode:11"] = failure
        with self.assertRaises(OSError) as raised:
            backend.acquire("output_mode", snapshot)
        self.assertIs(raised.exception, failure)

    def test_input_modes_cursor_and_partial_startup_restore(self):
        backend, api, snapshot = self.acquired()
        self.assertFalse(api.modes[10] & (0x01 | 0x02 | 0x04 | 0x40 | 0x200))
        self.assertTrue(api.modes[10] & 0x08)
        self.assertTrue(api.modes[10] & 0x80)
        backend.acquire("cursor", snapshot)
        self.assertFalse(api.cursor[1])
        backend.restore("cursor", snapshot)
        self.assertEqual(api.cursor, (25, True))
        backend.restore("input_mode", snapshot)
        backend.restore("input_mode", snapshot)
        self.assertEqual(api.modes[10], 0x47)
        self.assertEqual(sum(op[0] == "close_handle" for op in api.log), 1)
        backend, api = self.backend()
        snapshot = backend.capture()
        backend.acquire("output_mode", snapshot)
        api.failures["set_mode:10"] = native_error(5)
        with self.assertRaises(OSError):
            backend.acquire("input_mode", snapshot)
        backend.restore("input_mode", snapshot)
        self.assertEqual(sum(op[0] == "close_handle" for op in api.log), 1)

    def test_native_capabilities_respect_options_and_no_color(self):
        backend, _, _ = self.acquired(options=CapabilityOptions(color=16, unicode=False,
                                                                 reduced_motion=True))
        self.assertEqual(backend.capabilities.color_depth, 16)
        self.assertFalse(backend.capabilities.unicode)
        self.assertTrue(backend.capabilities.reduced_motion)
        self.assertFalse(backend.capabilities.paste)
        no_color, _, _ = self.acquired(environ={"NO_COLOR": "1"})
        self.assertEqual(no_color.capabilities.color_depth, 0)
        self.assertTrue(no_color.capabilities.cursor)
        explicit, _, _ = self.acquired(environ={"NO_COLOR": "1"},
                                      options=CapabilityOptions(color=16))
        self.assertEqual(explicit.capabilities.color_depth, 16)
        with self.assertRaises(ValueError):
            self.backend(options=CapabilityOptions(paste=True))

    def test_key_names_modifiers_repeats_and_key_up(self):
        backend, api, _ = self.acquired()
        api.wait_results.append(1)
        api.records.append((key(ord("A"), 65, modifiers=0x13, repeat=3),
                            key(3, 67, modifiers=0x08), key(vk=38), key(vk=135),
                            key(ord("a"), 65, down=False), resize(120, 40)))
        self.assertEqual(backend.wait(0.025), (
            KeyEvent("a", "A", frozenset({"shift", "alt"}), 3),
            KeyEvent("c", modifiers=frozenset({"ctrl"})), KeyEvent("up"),
            KeyEvent("f24"), ResizeEvent(80, 25)))
        waits = [op for op in api.log if op[0] == "wait"]
        self.assertEqual(waits[-1][2], 25)
        self.assertEqual(waits[-1][1][1], 10)

    def test_surrogates_across_reads_and_malformed_replacement(self):
        backend, api, _ = self.acquired()
        api.wait_results.extend((1, 1, 1))
        api.records.extend(((key(0xD83D, repeat=2),), (key(0xDE00, repeat=2),),
                            (key(0xD800), key(ord("x")), key(0xDC00))))
        self.assertEqual(backend.wait(0), ())
        self.assertEqual(backend.wait(0), (KeyEvent("😀", "😀", repeat=2),))
        self.assertEqual(backend.wait(0), (KeyEvent("�", "�"), KeyEvent("x", "x"),
                                          KeyEvent("�", "�")))

    def test_resize_and_key_order_and_filtered_batch_is_not_eof(self):
        backend, api, _ = self.acquired()
        api.wait_results.extend((1, 1))
        api.records.extend(((key(ord("a"), down=False),),
                            (resize(0, 0), key(vk=27), resize(90, 30))))
        self.assertEqual(backend.wait(0), ())
        self.assertEqual(backend.wait(0), (ResizeEvent(80, 25), KeyEvent("escape"),
                                          ResizeEvent(80, 25)))
        self.assertEqual(backend.dimensions(), (80, 25))
        api.screen = (0, 0, 0, 0)
        self.assertEqual(backend.dimensions(), (0, 0))

    def test_eof_and_invalid_handle_events_flush_surrogate(self):
        backend, api, _ = self.acquired()
        api.wait_results.extend((1, 1))
        api.records.extend(((key(0xD800),), ()))
        self.assertEqual(backend.wait(0), ())
        self.assertEqual(backend.wait(0), (KeyEvent("�", "�"), EOFEvent()))
        self.assertEqual(backend.wait(0), ())
        backend, api, _ = self.acquired()
        api.failures["wait"] = native_error(6)
        events = backend.wait(0)
        self.assertIsInstance(events[0], InputErrorEvent)
        self.assertEqual(events[-1], EOFEvent())

    def test_wake_and_close_do_not_close_a_handle_under_native_wait(self):
        backend, api, _ = self.acquired()
        api.block_wait = True
        result = []
        worker = threading.Thread(target=lambda: result.extend(backend.wait(None)))
        worker.start()
        self.assertTrue(api.wait_started.wait(1))
        backend.close()
        worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result, [EOFEvent()])
        operations = [op[0] for op in api.log]
        self.assertLess(operations.index("set_event"), operations.index("close_handle"))
        self.assertFalse(backend.wake())
        backend.close()

    def test_wake_signal_is_normalized(self):
        backend, api, _ = self.acquired()
        self.assertTrue(backend.wake())
        api.wait_results.append(0)
        self.assertEqual(backend.wait(0), (WakeEvent(),))

    def test_main_cursor_position_restored_after_alternate_screen_exit(self):
        backend, api, snapshot = self.acquired()
        snapshot["cursor_position"] = (3, 40)
        backend.acquire("alternate_screen", snapshot)
        backend.acquire("cursor", snapshot)
        backend.restore("cursor", snapshot)
        self.assertFalse(any(op[0] == "set_position" for op in api.log))
        backend.restore("alternate_screen", snapshot)
        backend.restore("output_mode", snapshot)
        self.assertEqual([op for op in api.log if op[0] == "set_position"][-1],
                         ("set_position", 11, 3, 40))

    def test_input_restore_retains_mode_and_event_close_failures(self):
        backend, api, snapshot = self.acquired()
        mode_error, event_error = native_error(5), native_error(6)
        api.failures["set_mode:10"] = mode_error
        api.failures["close_handle"] = event_error
        with self.assertRaises(TerminalCleanupError) as raised:
            backend.restore("input_mode", snapshot)
        self.assertEqual(tuple(error for _, error in raised.exception.failures),
                         (mode_error, event_error))

    def test_closed_input_reports_eof_once(self):
        backend, _, _ = self.acquired()
        backend.close()
        self.assertEqual(backend.wait(0), (EOFEvent(),))
        self.assertEqual(backend.wait(0), ())

    def test_concurrent_close_releases_the_owned_event_once(self):
        backend, api, _ = self.acquired()
        api.block_wait = True
        api.wait_release = threading.Event()
        waiter = threading.Thread(target=lambda: backend.wait(None))
        waiter.start()
        self.assertTrue(api.wait_started.wait(1))
        errors = []

        def close():
            try:
                backend.close()
            except BaseException as error:
                errors.append(error)

        closers = [threading.Thread(target=close) for _ in range(2)]
        for closer in closers:
            closer.start()
        try:
            self.assertTrue(api.two_wakes.wait(1))
        finally:
            api.wait_release.set()
            waiter.join(1)
            for closer in closers:
                closer.join(1)
        self.assertFalse(waiter.is_alive())
        self.assertTrue(all(not closer.is_alive() for closer in closers))
        self.assertEqual(errors, [])
        self.assertEqual(sum(op[0] == "close_handle" for op in api.log), 1)

    def test_altgr_printable_text_and_ctrl_space_are_preserved(self):
        backend, api, _ = self.acquired()
        api.wait_results.append(1)
        api.records.append((key(ord("€"), 69, modifiers=0x09), key(0, 32, modifiers=0x08)))
        self.assertEqual(backend.wait(0), (
            KeyEvent("€", "€", frozenset({"ctrl", "alt"})),
            KeyEvent("space", modifiers=frozenset({"ctrl"}))))

    def test_large_finite_timeout_is_clamped_before_multiplication(self):
        backend, api, _ = self.acquired()
        self.assertEqual(backend.wait(1e308), ())
        self.assertEqual([op for op in api.log if op[0] == "wait"][-1][2], 0xFFFFFFFE)

    def test_cursor_visibility_position_and_output_mode_cleanup_are_all_attempted(self):
        backend, api, snapshot = self.acquired()
        backend.acquire("alternate_screen", snapshot)
        backend.restore("cursor", snapshot)
        backend.restore("alternate_screen", snapshot)
        first, second = native_error(5), native_error(6)
        api.failures["set_cursor"], api.failures["set_position"] = first, second
        with self.assertRaises(TerminalCleanupError) as raised:
            backend.restore("output_mode", snapshot)
        self.assertEqual(tuple(error for _, error in raised.exception.failures), (first, second))
        self.assertEqual(api.modes[11], snapshot["output_mode"])

    def test_character_acknowledgements_cover_partial_surrogate(self):
        backend, api, _ = self.acquired()
        api.write_counts.extend((2, 1))
        self.assertEqual(backend.write("A😀B"), 2)
        self.assertEqual(api.written.decode("utf-16-le"), "A😀")
        self.assertEqual(backend.write("B"), 1)
        self.assertEqual(api.written.decode("utf-16-le"), "A😀B")
        for invalid in (0, -1, 99, True, None):
            api.write_counts.append(invalid)
            with self.subTest(invalid=invalid), self.assertRaises(OSError):
                backend.write("x")

    def test_plain_stream_writes_have_no_escape_sequences(self):
        api = FakeAPI()
        api.modes.clear()
        output = io.StringIO()
        backend = WindowsBackend(io.StringIO(), output, _api=api,
                                 input_handle=10, output_handle=11, environ={})
        self.addCleanup(backend.close)
        self.assertEqual(backend.write("\x1b[31mhello"), 10)
        backend.flush()
        self.assertNotIn("\x1b", output.getvalue())
        self.assertIn("hello", output.getvalue())
        self.assertFalse(any(op[0] == "write_console" for op in api.log))

    @unittest.skipUnless(os.name == "nt", "requires Windows isolated console")
    def test_hidden_real_console_modes_records_wake_and_restoration(self):
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0  # SW_HIDE
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [sys.executable, "-S", str(root / "tests" / "ui_windows_console_probe.py")],
            cwd=root, startupinfo=startup, creationflags=subprocess.CREATE_NEW_CONSOLE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        report = json.loads(completed.stdout)
        self.assertTrue(report["vt"])
        self.assertTrue(report["raw"])
        self.assertEqual(report["records"], 4)
        scheduling = report['scheduling']
        self.assertEqual(scheduling['workload'], 10000)
        self.assertLessEqual(scheduling['key_inspection_turn'], scheduling['key_injection_turn'] + 1)
        self.assertTrue(scheduling['worker_joined'])
        for name in ("unicode_write", "wake", "suspend", "modes_restored",
                     "cursor_restored", "cursor_position_restored", "wake_handle_closed"):
            self.assertTrue(report[name], name)


if __name__ == "__main__":
    unittest.main()
