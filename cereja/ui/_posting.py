"""Bounded, typed producer inbox. No arbitrary references or result store."""

from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
import math
import threading

from .events import (
    EOFEvent, FocusEvent, InputErrorEvent, KeyEvent, PasteEvent, ProgressEvent,
    QuitEvent, ResizeEvent, ResultEvent, TimerEvent, WakeEvent,
)


MAX_BYTES = 1048576
MAX_EVENTS = 1024
MAX_ID_BYTES = 4096


class _Oversized(ValueError):
    pass


def _text(value, *, limit=MAX_BYTES):
    if type(value) is not str:
        raise TypeError('event text and identities must be exact str values')
    if len(value) > limit:
        raise _Oversized('event text exceeds its UTF-8 budget')
    size = len(value.encode('utf-8'))
    if size > limit:
        raise _Oversized('event text exceeds its UTF-8 budget')
    return size


def _integer(value, *, minimum=0):
    if type(value) is not int or not minimum <= value <= (1 << 63) - 1:
        raise ValueError('event integer outside the bounded 64-bit range')


def _number(value):
    if type(value) is int:
        _integer(value, minimum=-(1 << 63))
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('time must be a finite number')


def payload_bytes(event):
    """Logical UTF-8/raw-byte cost; fixed bounded scalars cost zero.

    Reject subclasses and object graphs, even on frozen dataclass instances.
    This bounds logical content, not Python allocator overhead. No external
    result references are accepted, so there is no hidden result store to free.
    """
    kind = type(event)
    if kind is KeyEvent:
        _integer(event.repeat, minimum=1)
        if type(event.modifiers) is not frozenset or any(
                type(m) is not str or m not in ('shift', 'ctrl', 'alt') for m in event.modifiers):
            raise TypeError('key modifiers must be bounded immutable names')
        return _text(event.key, limit=MAX_ID_BYTES) + _text(event.text) + sum(
            len(m) for m in event.modifiers)
    if kind is PasteEvent:
        return _text(event.text)
    if kind is ResizeEvent:
        _integer(event.width)
        _integer(event.height)
        return 0
    if kind is InputErrorEvent:
        return _text(event.message)
    if kind is QuitEvent:
        return _text(event.reason, limit=MAX_ID_BYTES)
    if kind is FocusEvent:
        if type(event.focused) is not bool:
            raise TypeError('focus must be bool')
        return 0
    if kind is ProgressEvent:
        _integer(event.completed)
        _integer(event.generation)
        if event.total is not None:
            _integer(event.total)
            if event.completed > event.total:
                raise ValueError('progress exceeds its real total')
        return _text(event.source, limit=MAX_ID_BYTES) + _text(event.message)
    if kind is ResultEvent:
        _integer(event.generation, minimum=1)
        size = _text(event.source, limit=MAX_ID_BYTES)
        value = event.value
        if type(value) is str:
            size += _text(value)
        elif type(value) is bytes:
            size += len(value)
        elif type(value) is int:
            _integer(value, minimum=-(1 << 63))
        elif type(value) is float:
            _number(value)
        elif value is not None and type(value) is not bool:
            raise TypeError('results accept only bounded scalar/text/bytes values')
        return size
    if kind is TimerEvent:
        _integer(event.timer_id, minimum=1)
        _number(event.deadline)
        _number(event.now)
        return _text(event.owner, limit=MAX_ID_BYTES)
    if kind in (EOFEvent, WakeEvent):
        return 0
    raise TypeError('unsupported event type or event subclass')


class Cancellation:
    """Cooperative signal, with event-driven capacity waits and no worker claim."""

    def __init__(self):
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._conditions = {}

    @property
    def cancelled(self):
        return self._event.is_set()

    def wait(self, timeout=None):
        return self._event.wait(timeout)

    def cancel(self):
        with self._lock:
            self._event.set()
            conditions = tuple(self._conditions)
        for condition in conditions:
            with condition:
                condition.notify_all()

    @contextmanager
    def _watch(self, condition):
        with self._lock:
            self._conditions[condition] = self._conditions.get(condition, 0) + 1
        try:
            yield
        finally:
            with self._lock:
                count = self._conditions[condition] - 1
                if count:
                    self._conditions[condition] = count
                else:
                    del self._conditions[condition]


@dataclass(frozen=True)
class _Envelope:
    event: object
    size: int
    coalesce: object


class _Inbox:
    def __init__(self, max_events, max_bytes, wake):
        if type(max_events) is not int or not 1 <= max_events <= MAX_EVENTS:
            raise ValueError('posted envelope limit must be in 1..1024')
        if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_BYTES:
            raise ValueError('posted byte limit must be in 1..1048576')
        self.condition = threading.Condition()
        self.max_events, self.max_bytes = max_events, max_bytes
        self.wake = wake
        self.events = OrderedDict()
        self.coalesced = {}
        self.bytes = 0
        self.sequence = 0
        self.closed = False
        self.shutdown_reason = None
        self.capacity_waits = 0
        self.rejected = 0
        self.replacements = 0

    def prepare(self, event, source):
        if source is not None and type(event) is not ResizeEvent:
            raise ValueError('source override is supported only for resize')
        try:
            size = payload_bytes(event)
            if source is not None:
                size += _text(source, limit=MAX_ID_BYTES)
        except _Oversized:
            return None
        if size > self.max_bytes:
            return None
        key = None
        if type(event) is ResizeEvent:
            key = (ResizeEvent, source)
        elif type(event) is ProgressEvent:
            # A stale generation cannot replace current progress in its slot.
            key = (ProgressEvent, event.source, event.generation)
        return _Envelope(event, size, key)

    def _admit(self, envelope):
        key = self.coalesced.get(envelope.coalesce) if envelope.coalesce is not None else None
        old = self.events.get(key)
        size = self.bytes + envelope.size - (old.size if old else 0)
        if size > self.max_bytes or (old is None and len(self.events) >= self.max_events):
            return False
        if old is None:
            self.sequence += 1
            key = self.sequence
        else:
            self.replacements += 1
        self.events[key] = envelope
        if envelope.coalesce is not None:
            self.coalesced[envelope.coalesce] = key
        self.bytes = size
        # Replacing a larger slot can release capacity for another producer.
        self.condition.notify_all()
        return True

    def post(self, envelope, cancellation=None, *, wait=False):
        if envelope is None:
            with self.condition:
                self.rejected += 1
            return False
        token = cancellation or Cancellation()
        if not isinstance(token, Cancellation):
            raise TypeError('cancellation must be Cancellation or None')
        with token._watch(self.condition):
            with self.condition:
                while not self.closed and not token.cancelled:
                    if self._admit(envelope):
                        break
                    if not wait:
                        self.rejected += 1
                        return False
                    self.capacity_waits += 1
                    self.condition.wait()
                else:
                    self.rejected += 1
                    return False
        self.wake()
        return True

    def pop(self):
        with self.condition:
            if not self.events:
                return None
            _, envelope = self.events.popitem(last=False)
            self.bytes -= envelope.size
            if envelope.coalesce is not None:
                del self.coalesced[envelope.coalesce]
            self.condition.notify_all()
            return envelope.event

    def shutdown(self, reason):
        _text(reason, limit=MAX_ID_BYTES)
        with self.condition:
            if self.closed:
                return False
            if self.shutdown_reason is None:
                self.shutdown_reason = reason
            self.closed = True
            self.condition.notify_all()
        self.wake()
        return True

    def clear(self):
        with self.condition:
            self.closed = True
            self.events.clear()
            self.coalesced.clear()
            self.bytes = 0
            self.condition.notify_all()
