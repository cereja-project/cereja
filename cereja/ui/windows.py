"""Windows console records and VT output with explicit session acquisition."""

import math
import os
import sys
import threading

from ._capabilities import Capabilities, CapabilityOptions, _stream_identity, _unicode_output
from ._session import TerminalCleanupError, _safe_text
from ._win32 import INFINITE, WAIT_TIMEOUT, Win32API
from .events import EOFEvent, InputErrorEvent, KeyEvent, ResizeEvent, WakeEvent


_KEYS = {8: "backspace", 9: "tab", 13: "enter", 27: "escape", 33: "page_up",
         34: "page_down", 35: "end", 36: "home", 37: "left", 38: "up",
         39: "right", 40: "down", 45: "insert", 46: "delete"}
_KEYS.update({112 + index: f"f{index + 1}" for index in range(24)})


class WindowsBackend:
    """Borrow console handles and own only the session's application wake event.

    Constructing the backend queries handles without changing modes. VT remains
    unconfirmed until the session's journaled output probe succeeds. Legacy key
    records cannot identify paste, so an asserted paste protocol is rejected.
    One caller consumes input; worker threads may call wake() or close().
    """

    supports_acquisition = True

    def __init__(self, input_stream=None, output_stream=None, *, options=None,
                 environ=None, input_handle=None, output_handle=None, _api=None):
        options = CapabilityOptions() if options is None else options
        if not isinstance(options, CapabilityOptions):
            raise TypeError("options must be CapabilityOptions or None")
        if options.paste:
            raise ValueError("legacy Windows console records cannot assert paste support")
        self.input_stream = sys.stdin if input_stream is None else input_stream
        self.output_stream = sys.stdout if output_stream is None else output_stream
        self._options = options
        self._environ = dict(os.environ if environ is None else environ)
        self._api = Win32API() if _api is None else _api
        self._input = self._api.stream_handle(self.input_stream) if input_handle is None else input_handle
        self._output = self._api.stream_handle(self.output_stream) if output_handle is None else output_handle
        self._input_console = self._api.get_mode(self._input) is not None
        self._output_console = self._api.get_mode(self._output) is not None
        self.needs_output_probe = (self._input_console and self._output_console
                                   and options.cursor is not False)
        self.identity = (("process-console", os.getpid()) if self._output_console
                         else _stream_identity(self.output_stream))
        self._condition = threading.Condition()
        self._wake_handle = None
        self._waiters = 0
        self._closing = False
        self._closed = False
        self._input_ended = False
        self._pending_surrogate = None
        self._alternate_screen = False
        self._deferred_cursor = None
        self.invalidated = False
        self.capabilities = self._resolve(False)

    def _resolve(self, vt, reason="win32:vt-unconfirmed"):
        options = self._options
        cursor = vt and (options.cursor if options.cursor is not None
                         else self._environ.get("TERM") != "dumb")
        plain = not (self._input_console and self._output_console and cursor)
        color = 24 if vt else 0
        color_source = "win32:vt" if vt else reason
        if self._environ.get("NO_COLOR", ""):
            color, color_source = 0, "NO_COLOR"
        if options.color is not None:
            color, color_source = options.color, "option"
        unicode, unicode_source = ((True, "win32:wide-console") if self._output_console
                                    else _unicode_output(self.output_stream))
        if options.unicode is not None:
            unicode, unicode_source = options.unicode, "option"
        alternate = vt and (options.alternate_screen if options.alternate_screen is not None else True)
        sources = {
            "input_interactive": "win32:GetConsoleMode",
            "output_interactive": "win32:GetConsoleMode", "color_depth": color_source,
            "unicode": unicode_source, "cursor": "option" if options.cursor is not None else reason,
            "alternate_screen": "option" if options.alternate_screen is not None else "win32:vt",
            "paste": "win32:legacy-records", "reduced_motion": "option" if
            options.reduced_motion is not None else "safe-default",
            "plain": reason if plain else "win32:vt-confirmed",
        }
        if plain:
            color = 0
            cursor = alternate = False
            for name in ("color_depth", "cursor", "alternate_screen"):
                sources[name] = f"plain:{reason}"
        return Capabilities(self._input_console, self._output_console, color, unicode,
                            cursor, alternate, False, options.reduced_motion or False,
                            plain, sources)

    def dimensions(self):
        if self._output_console:
            try:
                return self._api.get_screen(self._output)[:2]
            except OSError:
                pass
        return 80, 24

    def capture(self):
        if self._closed:
            raise RuntimeError("Windows backend is closed")
        input_mode = self._api.get_mode(self._input) if self._input_console else None
        output_mode = self._api.get_mode(self._output) if self._output_console else None
        if ((self._input_console and input_mode is None)
                or (self._output_console and output_mode is None)):
            raise OSError("console handle became unavailable during capture")
        cursor = self._api.get_cursor(self._output) if self._output_console else None
        position = self._api.get_screen(self._output)[2:] if self._output_console else None
        return {"input_mode": input_mode, "output_mode": output_mode, "cursor": cursor,
                "cursor_position": position, "alternate_screen": self._alternate_screen}

    def acquire(self, resource, snapshot):
        if self._closed:
            raise RuntimeError("Windows backend is closed")
        if resource == "output_mode":
            if not self.needs_output_probe:
                return
            try:
                self._api.set_mode(self._output, snapshot["output_mode"] | 0x01 | 0x04)
            except OSError as error:
                if getattr(error, "winerror", None) not in (50, 87):
                    raise
                self.capabilities = self._resolve(False, "win32:vt-unavailable")
            else:
                self.capabilities = self._resolve(True, "win32:vt")
        elif resource == "input_mode":
            if self.capabilities.plain:
                return
            with self._condition:
                if self._closed or self._closing:
                    raise RuntimeError("Windows backend is closing")
                if self._wake_handle is None:
                    self._wake_handle = self._api.create_event()
            mode = (snapshot["input_mode"] | 0x08 | 0x80) & ~(0x01 | 0x02 | 0x04 | 0x10 | 0x40 | 0x200)
            self._api.set_mode(self._input, mode)
            self._input_ended = False
        elif resource == "alternate_screen":
            self._alternate_screen = True
            self._write_control("\x1b[?1049h")
        elif resource == "cursor":
            self._api.set_cursor(self._output, snapshot["cursor"][0], False)
        elif resource == "paste":
            raise ValueError("Windows record input has no paste protocol")
        elif resource != "signal_handlers":
            raise ValueError(f"unknown terminal resource {resource!r}")

    def restore(self, resource, snapshot):
        if resource == "output_mode":
            operations = []
            if self._deferred_cursor is not None:
                operations.append(("cursor", self._restore_deferred_cursor))
            if snapshot.get("output_mode") is not None:
                operations.append(("output_mode", lambda: self._api.set_mode(
                    self._output, snapshot["output_mode"])))
            try:
                self._restore_all(operations)
            finally:
                self.capabilities = self._resolve(False)
        elif resource == "input_mode":
            operations = []
            if snapshot.get("input_mode") is not None:
                operations.append(("input_mode", lambda: self._api.set_mode(
                    self._input, snapshot["input_mode"])))
            operations.append(("wake_event", self._release_event))
            self._restore_all(operations)
        elif resource == "cursor":
            if snapshot.get("cursor") is not None:
                if self._alternate_screen:
                    # Main-buffer scrollback coordinates can exceed the alternate
                    # buffer. Restore them after screen exit, at output cleanup.
                    self._deferred_cursor = dict(snapshot)
                else:
                    self._restore_cursor(snapshot)
        elif resource == "alternate_screen":
            target = snapshot.get("alternate_screen", False)
            if self._alternate_screen != target:
                self._write_control("\x1b[?1049h" if target else "\x1b[?1049l")
                self._alternate_screen = target
        elif resource not in ("paste", "signal_handlers"):
            raise ValueError(f"unknown terminal resource {resource!r}")

    @staticmethod
    def _restore_all(operations):
        failures = []
        for name, operation in operations:
            try:
                operation()
            except TerminalCleanupError as error:
                failures.extend(error.failures)
            except BaseException as error:
                failures.append((name, error))
        if len(failures) == 1:
            raise failures[0][1]
        if failures:
            raise TerminalCleanupError(failures)

    def _restore_cursor(self, snapshot):
        self._restore_all([
            ("cursor_visibility", lambda: self._api.set_cursor(self._output, *snapshot["cursor"])),
            ("cursor_position", lambda: self._api.set_position(self._output, *snapshot["cursor_position"])),
        ])

    def _restore_deferred_cursor(self):
        self._restore_cursor(self._deferred_cursor)
        self._deferred_cursor = None

    def _release_event(self):
        with self._condition:
            handle = self._wake_handle
            if handle is None:
                return
            self._closing = True
            if self._waiters:
                # Closing a handle during WaitForMultipleObjects is undefined.
                self._api.set_event(handle)
                while self._waiters:
                    self._condition.wait()
            if self._wake_handle != handle:
                return  # Another close caller completed this same release.
            self._api.close_handle(handle)
            self._wake_handle = None
            self._closing = False

    def wake(self):
        with self._condition:
            if self._closed or self._closing or self._wake_handle is None:
                return False
            self._api.set_event(self._wake_handle)
            return True

    def close(self):
        with self._condition:
            self._closed = True
        self._release_event()

    @staticmethod
    def _timeout(timeout):
        if timeout is None:
            return INFINITE
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise TypeError("timeout must be a number or None")
        if timeout < 0 or (isinstance(timeout, float) and not math.isfinite(timeout)):
            raise ValueError("timeout must be finite and nonnegative")
        if timeout >= (INFINITE - 1) / 1000:
            return INFINITE - 1
        return math.ceil(timeout * 1000)

    def _finish_input(self, error=None):
        self._input_ended = True
        events = self._flush_surrogate()
        if error is not None:
            events.append(InputErrorEvent(str(error)))
        events.append(EOFEvent())
        return tuple(events)

    def wait(self, timeout):
        milliseconds = self._timeout(timeout)
        with self._condition:
            if self._closed or self._closing:
                return () if self._input_ended else self._finish_input()
            if self.capabilities.plain or self._wake_handle is None or self._input_ended:
                return ()
            if self._waiters:
                raise RuntimeError("Windows input has one wait consumer")
            self._waiters += 1
            handles = self._wake_handle, self._input
        try:
            try:
                result = self._api.wait(handles, milliseconds)
                with self._condition:
                    if self._closed or self._closing:
                        return self._finish_input()
                if result == WAIT_TIMEOUT:
                    return ()
                if result == 0:
                    return (WakeEvent(),)
                if result != 1:
                    return self._finish_input(OSError("unexpected native wait result"))
                records = self._api.read_input(self._input, 128)
                if not records:
                    return self._finish_input()
                return self._decode(records)
            except OSError as error:
                return self._finish_input(None if getattr(error, "winerror", None) == 109 else error)
        finally:
            with self._condition:
                self._waiters -= 1
                self._condition.notify_all()

    def _flush_surrogate(self):
        pending, self._pending_surrogate = self._pending_surrogate, None
        if pending is None:
            return []
        return [KeyEvent("\ufffd", "\ufffd", pending[1], pending[2])]

    def _decode(self, records):
        events = []
        for record in records:
            if record.EventType == 4:
                events.extend(self._flush_surrogate())
                # Native resize records carry buffer size, not the viewport.
                events.append(ResizeEvent(*self.dimensions()))
            elif record.EventType == 1:
                event = record.Event.KeyEvent
                if not event.bKeyDown:
                    continue
                state, vk, unit = event.dwControlKeyState, event.wVirtualKeyCode, event.uChar.UnicodeChar
                modifiers = frozenset(name for name, flag in (("alt", 0x03), ("ctrl", 0x0C),
                                                              ("shift", 0x10)) if state & flag)
                repeat = max(1, event.wRepeatCount)
                pending = self._pending_surrogate
                if pending and 0xDC00 <= unit <= 0xDFFF and (modifiers, repeat) == pending[1:]:
                    self._pending_surrogate = None
                    char = chr(0x10000 + ((pending[0] - 0xD800) << 10) + unit - 0xDC00)
                    events.append(KeyEvent(char.lower(), char, modifiers, repeat))
                    continue
                events.extend(self._flush_surrogate())
                if 0xD800 <= unit <= 0xDBFF:
                    self._pending_surrogate = unit, modifiers, repeat
                elif 0xDC00 <= unit <= 0xDFFF:
                    events.append(KeyEvent("\ufffd", "\ufffd", modifiers, repeat))
                elif vk in _KEYS:
                    events.append(KeyEvent(_KEYS[vk], modifiers=modifiers, repeat=repeat))
                elif "ctrl" in modifiers and (1 <= unit <= 26 or (unit == 0 and 65 <= vk <= 90)):
                    letter = chr(96 + unit) if 1 <= unit <= 26 else chr(vk).lower()
                    events.append(KeyEvent(letter, modifiers=modifiers, repeat=repeat))
                elif "ctrl" in modifiers and unit == 0 and vk == 32:
                    events.append(KeyEvent("space", modifiers=modifiers, repeat=repeat))
                elif unit:
                    char = chr(unit)
                    events.append(KeyEvent(char.lower(), char, modifiers, repeat))
        return tuple(events)

    def _write_console(self, text):
        cleaned = "".join("\ufffd" if 0xD800 <= ord(char) <= 0xDFFF else char for char in text)
        data = cleaned.encode("utf-16-le")
        count = self._api.write_console(self._output, data)
        units = len(data) // 2
        if type(count) is not int or not 0 < count <= units:
            raise OSError("native console write did not acknowledge valid progress")
        boundary = characters = 0
        for char in cleaned:
            width = 2 if ord(char) > 0xFFFF else 1
            if boundary + width > count:
                # Finish an acknowledged high surrogate before confirming the
                # Python character. Failure ends the transaction without a frame.
                if count > boundary:
                    extra = self._api.write_console(self._output, data[count * 2:(count + 1) * 2])
                    if type(extra) is not int or extra != 1:
                        raise OSError("native console write split a surrogate pair")
                    characters += 1
                break
            boundary += width
            characters += 1
            if boundary == count:
                break
        return characters

    def write(self, text):
        if not isinstance(text, str):
            raise TypeError("terminal text must be str")
        if not text:
            return 0
        if self.capabilities.plain:
            safe = _safe_text(text)
            offset = 0
            while offset < len(safe):
                count = (self._write_console(safe[offset:]) if self._output_console
                         else self.output_stream.write(safe[offset:]))
                if type(count) is not int or not 0 < count <= len(safe) - offset:
                    raise OSError("plain write did not acknowledge valid progress")
                offset += count
            return len(text)
        return self._write_console(text)

    def _write_control(self, text):
        if self.capabilities.plain:
            raise RuntimeError("plain Windows output cannot acquire terminal controls")
        offset = 0
        while offset < len(text):
            offset += self.write(text[offset:])
        self.flush()

    def flush(self):
        if not self._output_console:
            self.output_stream.flush()

    def invalidate(self):
        self.invalidated = True
