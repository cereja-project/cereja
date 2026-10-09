"""Run only in a separately created, hidden console; stdout is the JSON pipe."""

import ctypes as C
import json
from pathlib import Path
import platform
import sys
import threading
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cereja.ui._win32 import BOOL, COORD, CONSOLE_SCREEN_BUFFER_INFO, DWORD, HANDLE, INPUT_RECORD, SMALL_RECT
from cereja.ui.buffer import CellBuffer, Style
from cereja.ui.events import KeyEvent, ResizeEvent, WakeEvent
from cereja.ui.rendering import Renderer
from cereja.ui.scheduling import EventLoop
from cereja.ui.terminal import CapabilityOptions, TerminalSession
from cereja.ui.text import TextPolicy
from cereja.ui.windows import WindowsBackend
from tests.ui_scheduling_probe import exercise_native


def key(unit, vk=0, *, modifiers=0, repeat=1):
    record = INPUT_RECORD()
    record.EventType = 1
    event = record.Event.KeyEvent
    event.bKeyDown = True
    event.wRepeatCount = repeat
    event.wVirtualKeyCode = vk
    event.uChar.UnicodeChar = unit
    event.dwControlKeyState = modifiers
    return record


def render_probe(session, *, resize=False):
    """Acknowledged real-console output and viewport resize, not visual QA."""
    backend = session.backend
    dimensions = backend.dimensions()
    policy = TextPolicy(ascii_only=not session.capabilities.unicode)
    renderer = Renderer(session, verify_damage=True)
    writes = []
    real_write = backend.write
    def observed_write(text):
        writes.append(text)
        return real_write(text)
    def present(size):
        frame = CellBuffer(*size, policy=policy)
        frame.draw_text(0, 0, 'e\u0301界😀\x1b]52;c;x\x07', style=Style(1, bold=True))
        if not renderer.render(frame):
            raise AssertionError('native frame failed')
        counts = session.write_count, session.flush_count
        if not renderer.render(frame.copy(), damage=[]):
            raise AssertionError('unchanged native frame failed')
        if (session.write_count, session.flush_count) != counts:
            raise AssertionError('unchanged native frame wrote/flushed')
    with patch.object(backend, 'write', side_effect=observed_write):
        present(dimensions)
        resized = None
        resize_status = 'not_requested'
        if resize:
            dll = backend._api._dll
            dll.SetConsoleWindowInfo.argtypes = [HANDLE, BOOL, C.POINTER(SMALL_RECT)]
            dll.SetConsoleWindowInfo.restype = BOOL
            info = CONSOLE_SCREEN_BUFFER_INFO()
            if not dll.GetConsoleScreenBufferInfo(backend._output, C.byref(info)):
                raise C.WinError(C.get_last_error())
            original = info.srWindow
            smaller = SMALL_RECT(original.Left, original.Top, original.Right - 1, original.Bottom - 1)
            try:
                if not dll.SetConsoleWindowInfo(backend._output, True, C.byref(smaller)):
                    raise C.WinError(C.get_last_error())
                resized = backend.dimensions()
                if resized == (dimensions[0] - 1, dimensions[1] - 1):
                    resize_status = 'passed'
                    present(resized)
                elif resized == dimensions:
                    # The API acknowledged the request but this hidden host did
                    # not expose a changed viewport. Do not call this a pass.
                    resize_status = 'unavailable: acknowledged API request left viewport unchanged'
                else:
                    raise AssertionError(f'unexpected native viewport: {dimensions} -> {resized}')
            finally:
                if not dll.SetConsoleWindowInfo(backend._output, True, C.byref(original)):
                    raise C.WinError(C.get_last_error())
    output = ''.join(writes)
    if '\x1b]52;' in output or '\x07' in output:
        raise AssertionError('source text injected terminal controls')
    if policy.ascii_only and not output.isascii():
        raise AssertionError('native ASCII fallback emitted non-ASCII')
    if session.capabilities.color_depth == 0:
        if any(cell.style.foreground is not None or cell.style.background is not None
               for row in renderer.front for cell in row):
            raise AssertionError('no-color frame retained color')
    return {'dimensions': dimensions, 'resized_dimensions': resized, 'resize_status': resize_status,
            'encoding': backend.output_stream.encoding, 'unchanged_writes_flushes': 0,
            'ascii_only': policy.ascii_only, 'color_depth': session.capabilities.color_depth,
            'reduced_motion': session.capabilities.reduced_motion,
            'capabilities': {name: getattr(session.capabilities, name) for name in
                             ('plain', 'cursor', 'alternate_screen', 'unicode', 'paste')},
            'presentation_checked': False}


def probe():
    with open("CONIN$", "r", encoding="utf-8") as console_input, \
            open("CONOUT$", "w", encoding="utf-8") as console_output:
        backend = WindowsBackend(console_input, console_output, environ={})
        api = backend._api
        dll = api._dll
        dll.SetConsoleScreenBufferSize.argtypes, dll.SetConsoleScreenBufferSize.restype = [HANDLE, COORD], BOOL
        info = CONSOLE_SCREEN_BUFFER_INFO()
        if not dll.GetConsoleScreenBufferInfo(backend._output, C.byref(info)):
            raise C.WinError(C.get_last_error())
        main_y = api.get_screen(backend._output)[1] + 10
        if info.dwSize.Y <= main_y:
            if not dll.SetConsoleScreenBufferSize(backend._output, COORD(info.dwSize.X, main_y + 1)):
                raise C.WinError(C.get_last_error())
        api.set_position(backend._output, 3, main_y)
        before_modes = api.get_mode(backend._input), api.get_mode(backend._output)
        before_cursor = api.get_cursor(backend._output)
        before_position = api.get_screen(backend._output)[2:]
        dll.WriteConsoleInputW.argtypes = [HANDLE, C.POINTER(INPUT_RECORD), DWORD, C.POINTER(DWORD)]
        dll.WriteConsoleInputW.restype = BOOL
        dll.FlushConsoleInputBuffer.argtypes, dll.FlushConsoleInputBuffer.restype = [HANDLE], BOOL
        dll.GetHandleInformation.argtypes, dll.GetHandleInformation.restype = [HANDLE, C.POINTER(DWORD)], BOOL
        result = {"native": True, "host": "isolated hidden Windows console",
                  "platform": platform.platform(), "python": sys.version,
                  "emulator": None, "emulator_version": None}
        try:
            with TerminalSession(backend) as session:
                result["vt"] = not backend.capabilities.plain
                if backend.capabilities.plain:
                    raise RuntimeError("this console did not accept VT output")
                event_handle = backend._wake_handle
                result["raw"] = not api.get_mode(backend._input) & 7
                result['rendering'] = render_probe(session, resize=True)
                if not dll.FlushConsoleInputBuffer(backend._input):
                    raise C.WinError(C.get_last_error())
                records = [key(ord("A"), 65, modifiers=0x10, repeat=3),
                           key(3, 67, modifiers=0x08), key(0xD83D), key(0xDE00)]
                resize = INPUT_RECORD()
                resize.EventType = 4
                resize.Event.WindowBufferSizeEvent.dwSize.X = 1
                resize.Event.WindowBufferSizeEvent.dwSize.Y = 1
                records.append(resize)
                array = (INPUT_RECORD * len(records))(*records)
                written = DWORD()
                if not dll.WriteConsoleInputW(backend._input, array, len(records), C.byref(written)):
                    raise C.WinError(C.get_last_error())
                if written.value != len(records):
                    raise AssertionError("input record injection was incomplete")
                events = backend.wait(1)
                expected = (KeyEvent("a", "A", frozenset({"shift"}), 3),
                            KeyEvent("c", modifiers=frozenset({"ctrl"})),
                            KeyEvent("😀", "😀"), ResizeEvent(*backend.dimensions()))
                if events != expected:
                    raise AssertionError(f"native records differed: {events!r}")
                result["records"] = len(events)
                if not session.write_text("A😀B"):
                    raise AssertionError("native output transaction failed")
                result["unicode_write"] = True
                wake_result = []
                def delayed_wake():
                    threading.Event().wait(.03)
                    wake_result.append(backend.wake())
                worker = threading.Thread(target=delayed_wake)
                worker.start()
                started = time.monotonic()
                native_wake = backend.wait(1)
                result["wake_wait_seconds"] = time.monotonic() - started
                worker.join(1)
                if worker.is_alive() or wake_result != [True] or native_wake != (WakeEvent(),):
                    raise AssertionError("native wake event failed")
                result["wake"] = True
                with session.suspend():
                    if api.get_mode(backend._input) != before_modes[0]:
                        raise AssertionError("suspend did not restore input mode")
                result["suspend"] = not backend.capabilities.plain
                if not dll.FlushConsoleInputBuffer(backend._input):
                    raise C.WinError(C.get_last_error())
                # Suspend reacquires a new event; verify the current handle.
                event_handle = backend._wake_handle
                def inject_key():
                    record = key(ord('x'))
                    count = DWORD()
                    if not dll.WriteConsoleInputW(backend._input, C.byref(record), 1, C.byref(count)):
                        raise C.WinError(C.get_last_error())
                    if count.value != 1:
                        raise AssertionError('pressure key injection was incomplete')
                result['scheduling'] = exercise_native(session, inject_key)
            result["modes_restored"] = before_modes == (api.get_mode(backend._input), api.get_mode(backend._output))
            result["cursor_restored"] = before_cursor == api.get_cursor(backend._output)
            result["cursor_position_restored"] = before_position == api.get_screen(backend._output)[2:]
            flags = DWORD()
            result["wake_handle_closed"] = not dll.GetHandleInformation(event_handle, C.byref(flags))
            if not all(result[name] for name in ("modes_restored", "cursor_restored", "cursor_position_restored",
                                                "wake_handle_closed")):
                raise AssertionError(f"native restoration failed: {result!r}")
            policy_backend = WindowsBackend(console_input, console_output,
                options=CapabilityOptions(unicode=False, reduced_motion=True), environ={'NO_COLOR': '1'})
            try:
                with TerminalSession(policy_backend) as session:
                    result['fallbacks'] = render_probe(session)
                    if session.animations_enabled or session.capabilities.color_depth:
                        raise AssertionError('static/no-color policy was not applied')
                    loop = EventLoop(session, lambda event: None)
                    if loop.call_later(1, owner='spinner', decorative=True) is not None:
                        raise AssertionError('reduced-motion retained decorative timer')
                    loop.close()
                if (before_modes != (api.get_mode(backend._input), api.get_mode(backend._output))
                        or before_cursor != api.get_cursor(backend._output)
                        or before_position != api.get_screen(backend._output)[2:]):
                    raise AssertionError('fallback session did not restore console state')
                result['fallback_restored'] = True
            finally:
                policy_backend.close()
        finally:
            backend.close()
        return result


if __name__ == "__main__":
    try:
        print(json.dumps(probe(), ensure_ascii=True))
    except BaseException as error:
        print(json.dumps({"error": repr(error)}, ensure_ascii=True))
        raise
