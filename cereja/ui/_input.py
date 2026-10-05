"""Incremental UTF-8/xterm input with bounded sequence and paste storage."""

import codecs
import math

from .events import EOFEvent, InputErrorEvent, KeyEvent, PasteEvent


_ARROWS = {'A': 'up', 'B': 'down', 'C': 'right', 'D': 'left',
           'H': 'home', 'F': 'end'}
_TILDE = {1: 'home', 2: 'insert', 3: 'delete', 4: 'end', 5: 'page_up',
          6: 'page_down', 7: 'home', 8: 'end', 11: 'f1', 12: 'f2', 13: 'f3',
          14: 'f4', 15: 'f5', 17: 'f6', 18: 'f7', 19: 'f8', 20: 'f9',
          21: 'f10', 23: 'f11', 24: 'f12'}
_PASTE_END = b'\x1b[201~'


def _modifiers(value):
    if not 1 <= value <= 8:
        raise ValueError('unsupported modifier')
    bits = value - 1
    return frozenset(name for bit, name in ((1, 'shift'), (2, 'alt'), (4, 'ctrl'))
                     if bits & bit)


def _key(char, modifiers=frozenset()):
    if char in '\r\n':
        return KeyEvent('enter', modifiers=modifiers)
    if char == '\t':
        return KeyEvent('tab', modifiers=modifiers)
    if char in ('\x08', '\x7f'):
        return KeyEvent('backspace', modifiers=modifiers)
    if char == '\x00':
        return KeyEvent('space', modifiers=modifiers | {'ctrl'})
    if 1 <= ord(char) <= 26:
        return KeyEvent(chr(ord(char) + 96), modifiers=modifiers | {'ctrl'})
    if 28 <= ord(char) <= 31:
        return KeyEvent(chr(ord(char) + 64), modifiers=modifiers | {'ctrl'})
    return KeyEvent(char.lower(), char, modifiers)


class EscapeParser:
    """One input stream, one monotonic clock, no I/O or scheduled timers.

    Feed a bounded native read at its arrival time. Deadlines are inclusive:
    bytes arriving at/after a deadline follow the expired escape event. Unknown
    control strings and rejected pastes are consumed without shortcut replay.
    """

    def __init__(self, *, escape_timeout=.03, max_paste_bytes=1048576,
                 max_sequence_bytes=4096):
        if (isinstance(escape_timeout, bool) or
                not isinstance(escape_timeout, (int, float))):
            raise TypeError('escape timeout must be numeric')
        if not math.isfinite(escape_timeout) or not .01 <= escape_timeout <= .1:
            raise ValueError('escape timeout must be between 10 and 100 ms')
        for value, minimum in ((max_paste_bytes, 1), (max_sequence_bytes, 2)):
            if type(value) is not int or value < minimum:
                raise ValueError('input limits must be positive integers')
        self.escape_timeout = escape_timeout
        self.max_paste_bytes = max_paste_bytes
        self.max_sequence_bytes = max_sequence_bytes
        self.deadline = None
        self._state = 'ground'
        self._decoder = codecs.getincrementaldecoder('utf-8')('replace')
        self._sequence = bytearray()
        self._paste = bytearray()
        self._tail = bytearray()
        self._paste_size = 0
        self._rejected = False
        self._string_escape = False
        self._string_kind = None
        self._closed = False

    @property
    def retained_bytes(self):
        return (len(self._sequence) + len(self._paste) + len(self._tail) +
                len(self._decoder.getstate()[0]))

    def _reset(self):
        self._state = 'ground'
        self.deadline = None
        self._sequence.clear()
        self._decoder.reset()

    def _flush_text(self, modifiers=frozenset()):
        return tuple(_key(c, modifiers) for c in self._decoder.decode(b'', final=True))

    def expire(self, now):
        if self.deadline is None or now < self.deadline:
            return ()
        if self._state == 'escape':
            events = (KeyEvent('escape'),)
        elif self._state == 'alt':
            events = self._flush_text(frozenset({'alt'}))
        else:
            events = (InputErrorEvent('incomplete terminal escape sequence'),)
        self._reset()
        return events

    def feed(self, data, now):
        if self._closed:
            raise RuntimeError('input parser is closed')
        if not isinstance(data, bytes):
            raise TypeError('input must be bytes')
        if (isinstance(now, bool) or not isinstance(now, (int, float)) or
                not math.isfinite(now)):
            raise ValueError('arrival time must be finite')
        events = list(self.expire(now))
        for byte in data:
            state = self._state
            if state == 'paste':
                events.extend(self._paste_byte(byte))
            elif state == 'string':
                if ((byte == 7 and self._string_kind == 93) or
                        (self._string_escape and byte == 92)):
                    self._reset()
                    self._string_escape = False
                else:
                    self._string_escape = byte == 27
            elif state == 'discard':
                if 64 <= byte <= 126:
                    self._reset()
            elif state in ('csi', 'ss3'):
                if len(self._sequence) >= self.max_sequence_bytes:
                    events.append(InputErrorEvent('terminal escape sequence exceeds byte limit'))
                    self._sequence.clear()
                    self.deadline = None
                    self._state = 'discard'
                    if 64 <= byte <= 126:
                        self._reset()
                elif 64 <= byte <= 126:
                    self._sequence.append(byte)
                    events.extend(self._finish_sequence(state))
                elif 32 <= byte <= 63:
                    self._sequence.append(byte)
                else:
                    events.append(InputErrorEvent('malformed terminal escape sequence'))
                    self._sequence.clear()
                    self.deadline = None
                    self._state = 'discard'
            elif state == 'escape':
                if byte in (91, 79):
                    self._state = 'csi' if byte == 91 else 'ss3'
                    # A recognized protocol prefix is no longer ambiguous with
                    # the standalone Escape key. Timing it out would replay a
                    # delayed paste/sequence suffix as ordinary shortcuts.
                    self.deadline = None
                    self._sequence.extend((27, byte))
                elif byte in (93, 80, 88, 94, 95):
                    events.append(InputErrorEvent('unsupported terminal control string'))
                    self._state = 'string'
                    self._string_kind = byte
                    self.deadline = None
                elif byte == 27:
                    events.append(KeyEvent('escape'))
                    self.deadline = now + self.escape_timeout
                else:
                    self._state = 'alt'
                    decoded = self._decoder.decode(bytes((byte,)))
                    if decoded:
                        events.extend(_key(c, frozenset({'alt'})) for c in decoded)
                        self._reset()
            elif state == 'alt':
                decoded = self._decoder.decode(bytes((byte,)))
                if decoded:
                    events.extend(_key(c, frozenset({'alt'})) for c in decoded)
                    self._reset()
            elif byte == 27:
                events.extend(self._flush_text())
                self._decoder.reset()
                self._state = 'escape'
                self.deadline = now + self.escape_timeout
            else:
                events.extend(_key(c) for c in self._decoder.decode(bytes((byte,))))
        return tuple(events)

    def _finish_sequence(self, state):
        sequence = bytes(self._sequence[2:])
        self._reset()
        if state == 'csi' and sequence == b'200~':
            self._state = 'paste'
            self._paste.clear()
            self._tail.clear()
            self._paste_size = 0
            self._rejected = False
            return ()
        try:
            final = chr(sequence[-1])
            parameter_text = sequence[:-1].decode('ascii')
            if parameter_text and not all(part.isdigit()
                                          for part in parameter_text.split(';')):
                raise ValueError('non-numeric parameters or unsupported intermediates')
            params = [int(p) for p in parameter_text.split(';')] if parameter_text else []
            if len(params) > 2 or any(p < 0 or p > 99999 for p in params):
                raise ValueError('unsupported parameters')
            modifiers = _modifiers(params[-1]) if len(params) == 2 else frozenset()
            if final in _ARROWS and (not params or params[0] in (0, 1)):
                key = _ARROWS[final]
            elif final in 'PQRS' and (not params or params[0] in (0, 1)):
                key = f'f{ord(final) - ord("P") + 1}'
            elif final == 'Z' and not params:
                key, modifiers = 'tab', frozenset({'shift'})
            elif final == '~' and params and params[0] in _TILDE:
                key = _TILDE[params[0]]
            else:
                raise ValueError('unsupported key sequence')
            return (KeyEvent(key, modifiers=modifiers),)
        except (ValueError, UnicodeError):
            return (InputErrorEvent('unsupported terminal escape sequence'),)

    def _append_paste(self, data, *, final=False):
        decoded = self._decoder.decode(data, final=final).encode('utf-8')
        if not self._rejected:
            self._paste_size += len(decoded)
            if self._paste_size > self.max_paste_bytes:
                self._rejected = True
                self._paste.clear()
            else:
                self._paste.extend(decoded)

    def _paste_byte(self, byte):
        self._tail.append(byte)
        while self._tail and not _PASTE_END.startswith(self._tail):
            self._append_paste(bytes((self._tail.pop(0),)))
        if self._tail != _PASTE_END:
            return ()
        self._append_paste(b'', final=True)
        if self._rejected:
            event = InputErrorEvent('paste exceeds decoded UTF-8 byte limit')
        else:
            event = PasteEvent(self._paste.decode('utf-8'))
        self._paste.clear()
        self._tail.clear()
        self._reset()
        return (event,)

    def eof(self):
        if self._closed:
            return ()
        self._closed = True
        if self._state == 'ground':
            events = self._flush_text()
        elif self._state == 'escape':
            events = (KeyEvent('escape'),)
        elif self._state == 'alt':
            events = self._flush_text(frozenset({'alt'}))
        else:
            events = (InputErrorEvent('input ended inside terminal sequence or paste'),)
        self._paste.clear()
        self._tail.clear()
        self._reset()
        return events + (EOFEvent(),)
