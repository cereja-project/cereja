"""Run only in a separately created, hidden console; stdout is the JSON pipe."""

import ctypes as C
import json
from pathlib import Path
import platform
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cereja.ui._win32 import BOOL, COORD, CONSOLE_SCREEN_BUFFER_INFO, DWORD, HANDLE, INPUT_RECORD
from cereja.ui.events import KeyEvent, ResizeEvent, WakeEvent
from cereja.ui.terminal import TerminalSession
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
                  "platform": platform.platform(), "python": sys.version}
        try:
            with TerminalSession(backend) as session:
                result["vt"] = not backend.capabilities.plain
                if backend.capabilities.plain:
                    raise RuntimeError("this console did not accept VT output")
                event_handle = backend._wake_handle
                result["raw"] = not api.get_mode(backend._input) & 7
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
        finally:
            backend.close()
        return result


if __name__ == "__main__":
    try:
        print(json.dumps(probe(), ensure_ascii=True))
    except BaseException as error:
        print(json.dumps({"error": repr(error)}, ensure_ascii=True))
        raise
