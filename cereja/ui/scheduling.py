"""Single-owner event scheduling; explicit imports, no worker initialization."""

from collections import deque
from dataclasses import dataclass
import heapq
import threading
import time

from ._posting import (
    Cancellation, MAX_BYTES, MAX_EVENTS, _Inbox, _integer, _number, _text,
    payload_bytes,
)
from .events import EOFEvent, ProgressEvent, QuitEvent, ResultEvent, TimerEvent, WakeEvent


@dataclass(frozen=True)
class Request:
    source: str
    generation: int
    cancellation: Cancellation


@dataclass(frozen=True)
class Metrics:
    turns: int
    waits: int
    blocking_waits: int
    native_checks: int
    admission_pauses: int
    posted_events: int
    native_events: int
    timer_events: int
    suppressed_results: int
    renders: int
    writes: int
    flushes: int
    capacity_waits: int
    rejected_posts: int
    coalesced_posts: int


@dataclass
class _Timer:
    owner: str
    deadline: float
    interval: float | None
    decorative: bool
    size: int


class EventLoop:
    """Own presentation callbacks and timers on the active session's UI thread.

    Only post, wait_post and request_shutdown are producer-thread operations.
    Callbacks are synchronous and must return promptly. The 4 ms policy cannot
    preempt one callback or an OS write. run() owns shutdown/cleanup; turn() is
    also available for embedding and deterministic tests. close() never joins
    or declares workers stopped.
    """

    def __init__(self, session, handler, *, clock=time.monotonic,
                 max_events=MAX_EVENTS, max_bytes=MAX_BYTES, low_bandwidth=False):
        session._check_active()
        if not callable(handler) or not callable(clock):
            raise TypeError('handler and clock must be callable')
        if type(low_bandwidth) is not bool:
            raise TypeError('low_bandwidth must be bool')
        self.session, self.handler, self.clock = session, handler, clock
        self._thread = threading.get_ident()
        self._inbox = _Inbox(max_events, max_bytes, self._wake)
        self._native = deque()
        self._timers = {}
        self._heap = []
        self._timer_bytes = 0
        self._sequence = 0
        self._requests = {}
        self._request_bytes = 0
        self._generation = 0
        self._reduced_motion = session.capabilities.reduced_motion
        self._frame_interval = 1 / (4 if low_bandwidth else 30)
        self._renderer = None
        self._pending_frame = None
        self._render_deadline = None
        self._last_render = None
        self._processing = False
        self._stopped = False
        self.wake_error = None
        self._counts = dict.fromkeys(('turns', 'waits', 'blocking_waits', 'native_checks',
            'admission_pauses', 'posted_events', 'native_events', 'timer_events',
            'suppressed_results', 'renders'), 0)
        self._write_start = session.write_count
        self._flush_start = session.flush_count

    def _check_thread(self):
        if threading.get_ident() != self._thread:
            raise RuntimeError('presentation belongs to the UI thread')

    def _check_active(self):
        self._check_thread()
        if self._stopped:
            raise RuntimeError('event loop is closed')
        self.session._check_active()

    def _wake(self):
        with self._inbox.condition:
            self._inbox.condition.notify_all()
        wake = getattr(self.session.backend, 'wake', None)
        if wake is not None:
            try:
                wake()
            except OSError as error:
                # Admission has already committed. Keep the exception observable
                # without lying about producer ownership or retrying the event.
                self.wake_error = error

    @property
    def stopped(self):
        return self._stopped

    @property
    def queued_count(self):
        with self._inbox.condition:
            return len(self._inbox.events)

    @property
    def queued_bytes(self):
        with self._inbox.condition:
            return self._inbox.bytes

    @property
    def native_pending(self):
        return len(self._native)

    @property
    def timer_count(self):
        return len(self._timers)

    @property
    def metrics(self):
        with self._inbox.condition:
            return Metrics(**self._counts,
                writes=self.session.write_count - self._write_start,
                flushes=self.session.flush_count - self._flush_start,
                capacity_waits=self._inbox.capacity_waits,
                rejected_posts=self._inbox.rejected,
                coalesced_posts=self._inbox.replacements)

    def post(self, event, *, source=None):
        """Nonblocking typed admission. False retains producer ownership.

        Quit uses independent shutdown signaling, even when the inbox is full.
        Only progress/resize coalesce; resize can specify a bounded source name.
        """
        if type(event) is QuitEvent:
            return self.request_shutdown(event.reason)
        return self._inbox.post(self._inbox.prepare(event, source))

    def wait_post(self, event, *, source=None, cancellation=None):
        """Worker-only retry, sleeping until capacity, cancellation or shutdown."""
        if threading.get_ident() == self._thread:
            raise RuntimeError('UI thread cannot wait for its own posted inbox')
        if type(event) is QuitEvent:
            return self.request_shutdown(event.reason)
        return self._inbox.post(self._inbox.prepare(event, source), cancellation, wait=True)

    def request_shutdown(self, reason=''):
        """Thread-safe reserved signal. First reason wins; terminal cleanup is UI-owned."""
        return self._inbox.shutdown(reason)

    def begin_request(self, source):
        self._check_active()
        size = _text(source, limit=4096)
        old = self._requests.get(source)
        if old is None and (len(self._requests) >= MAX_EVENTS
                            or self._request_bytes + size > MAX_BYTES):
            raise OverflowError('request registry is full; forget completed sources')
        self._generation += 1
        _integer(self._generation, minimum=1)
        request = Request(source, self._generation, Cancellation())
        self._requests[source] = (request, True)
        if old is None:
            self._request_bytes += size
        return request

    def cancel_request(self, source, *, cooperative=False):
        """Suppress presentation. Signal a proven cooperative path only when requested."""
        self._check_active()
        if type(cooperative) is not bool:
            raise TypeError('cooperative must be bool')
        current = self._requests.get(source)
        if current is None:
            return False
        request, _ = current
        self._requests[source] = (request, False)
        if cooperative:
            request.cancellation.cancel()
        return True

    def forget_request(self, source):
        self._check_active()
        if self._requests.pop(source, None) is None:
            return False
        self._request_bytes -= _text(source, limit=4096)
        return True

    def call_later(self, delay, *, owner, interval=None, decorative=False, spinner=False):
        """Bounded monotonic heap timer; owner removal uses cancel_owner().

        Decorative repeating timers respect the frame ceiling; spinner adds the
        8 Hz ceiling. Late intervals start anew from current time, with no replay.
        Plain/reduced motion rejects decorative timers without allocating them.
        """
        self._check_active()
        _number(delay)
        if delay < 0:
            raise ValueError('timer delay must be nonnegative')
        if type(decorative) is not bool or type(spinner) is not bool:
            raise TypeError('timer motion flags must be bool')
        if spinner and not decorative:
            raise ValueError('spinner is a decorative timer')
        size = _text(owner, limit=4096)
        if interval is not None:
            _number(interval)
            if interval <= 0:
                raise ValueError('timer interval must be positive')
            if decorative:
                interval = max(interval, self._frame_interval, .125 if spinner else 0)
        if decorative and (self._reduced_motion or self.session.capabilities.plain):
            return None
        if len(self._timers) >= MAX_EVENTS or self._timer_bytes + size > MAX_BYTES:
            raise OverflowError('timer storage is full')
        deadline = self.clock() + delay
        _number(deadline)
        self._sequence += 1
        _integer(self._sequence, minimum=1)
        identity = self._sequence
        self._timers[identity] = _Timer(owner, deadline, interval, decorative, size)
        self._timer_bytes += size
        heapq.heappush(self._heap, (deadline, identity))
        return identity

    def cancel_timer(self, timer_id):
        self._check_active()
        timer = self._timers.pop(timer_id, None)
        if timer is None:
            return False
        self._timer_bytes -= timer.size
        # Eagerly remove tombstones: cancelled long deadlines retain no owners.
        self._heap = [entry for entry in self._heap if entry[1] != timer_id]
        heapq.heapify(self._heap)
        return True

    def cancel_owner(self, owner):
        """Call on removal/hiding; this core introduces no widget lifecycle."""
        self._check_active()
        identities = [key for key, timer in self._timers.items() if timer.owner == owner]
        for identity in identities:
            self.cancel_timer(identity)
        return len(identities)

    def set_reduced_motion(self, enabled):
        self._check_active()
        if type(enabled) is not bool:
            raise TypeError('reduced motion must be bool')
        self._reduced_motion = enabled
        if enabled:
            for identity, timer in tuple(self._timers.items()):
                if timer.decorative:
                    self.cancel_timer(identity)
            if self._pending_frame is not None and self._pending_frame[2]:
                self._pending_frame = self._render_deadline = None

    def request_render(self, frame, *, cursor=None, decorative=False):
        """Keep one UI-owned latest frame; no idle redraw or producer callbacks."""
        self._check_active()
        from .buffer import CellBuffer
        from .rendering import Cursor, Renderer
        if not isinstance(frame, CellBuffer):
            raise TypeError('render requires CellBuffer')
        if type(decorative) is not bool:
            raise TypeError('decorative must be bool')
        cursor = Cursor() if cursor is None else cursor
        if not isinstance(cursor, Cursor):
            raise TypeError('cursor must be Cursor')
        if decorative and (self._reduced_motion or self.session.capabilities.plain):
            return False
        if self._renderer is None:
            self._renderer = Renderer(self.session)
        self._pending_frame = (frame.copy(), cursor, decorative)
        now = self.clock()
        self._render_deadline = now if self._last_render is None else max(
            now, self._last_render + self._frame_interval)
        return True

    @property
    def next_deadline(self):
        deadlines = []
        if self._heap:
            deadlines.append(self._heap[0][0])
        if self._render_deadline is not None:
            deadlines.append(self._render_deadline)
        deadline = getattr(self.session.backend, 'input_deadline', None)
        if deadline is not None and not self._native:
            deadlines.append(deadline)
        return min(deadlines) if deadlines else None

    def _control(self):
        with self._inbox.condition:
            reason = self._inbox.shutdown_reason
        if reason is None:
            return False
        try:
            self.handler(QuitEvent(reason))
        except BaseException as error:
            self.close(error)
            raise
        else:
            self.close()
        return True

    def _dispatch(self, event):
        if type(event) is WakeEvent:
            return
        if type(event) in (ResultEvent, ProgressEvent):
            current = self._requests.get(event.source)
            if (type(event) is ResultEvent or event.generation != 0 or current is not None):
                if current is None or not current[1] or current[0].generation != event.generation:
                    self._counts['suppressed_results'] += 1
                    return
        self.handler(event)
        if type(event) in (QuitEvent, EOFEvent):
            self.close()

    def _wait(self, timeout):
        backend = self.session.backend
        admit = not self._native
        self._counts['waits'] += 1
        self._counts['blocking_waits' if timeout != 0 else 'native_checks'] += 1
        if not admit:
            self._counts['admission_pauses'] += 1
        wait = getattr(backend, 'wait_events', None)
        if wait is None and not self.session.capabilities.plain:
            wait = backend.wait
        if wait is not None:
            events = wait(timeout, read_input=admit)
            # Native adapters return one finite read (POSIX 4 KiB, Windows 128
            # records); retain it until delivered before admitting another.
            self._native.extend(events)
        elif timeout != 0:
            # Plain streams have no native wake resources. The inbox condition
            # supplies an indefinite, race-free wait without acquiring modes.
            with self._inbox.condition:
                if not self._inbox.events and not self._inbox.closed:
                    self._inbox.condition.wait(timeout)

    def _work(self):
        worked = False
        for _ in range(64):
            if not self._native or self._stopped or self._control():
                break
            event = self._native.popleft()
            self._counts['native_events'] += 1
            self._dispatch(event)
            worked = True
        started = self.clock()
        for _ in range(64):
            if self._stopped or self._control() or self.clock() - started >= .004:
                break
            event = self._inbox.pop()
            if event is None:
                break
            self._counts['posted_events'] += 1
            self._dispatch(event)
            worked = True
        if self._stopped or self._control():
            return worked
        # Timer work is bounded too, so an adversarial timer collection cannot
        # form another unbounded drain between native readiness checks.
        started = self.clock()
        for _ in range(64):
            now = self.clock()
            if (not self._heap or self._heap[0][0] > now or now - started >= .004
                    or self._stopped or self._control()):
                break
            deadline, identity = heapq.heappop(self._heap)
            timer = self._timers[identity]
            if timer.interval is None:
                del self._timers[identity]
                self._timer_bytes -= timer.size
            self._counts['timer_events'] += 1
            self._dispatch(TimerEvent(timer.owner, identity, deadline, now))
            worked = True
            if not self._stopped and timer.interval is not None and identity in self._timers:
                timer.deadline = self.clock() + timer.interval
                heapq.heappush(self._heap, (timer.deadline, identity))
        if self._stopped or self._control():
            return worked
        if self._render_deadline is not None and self._render_deadline <= self.clock():
            frame, cursor, _ = self._pending_frame
            self._pending_frame = self._render_deadline = None
            self._last_render = self.clock()
            self._counts['renders'] += 1
            if not self._renderer.render(frame, cursor=cursor):
                self.close()
            worked = True
        return worked

    def turn(self, *, block=False):
        """One bounded turn. block=True waits only when there is no ready work."""
        self._check_thread()
        if self._stopped:
            return False
        self._check_active()
        if self._processing:
            raise RuntimeError('event loop turns cannot reenter')
        self._processing = True
        self._counts['turns'] += 1
        try:
            if self._control():
                return False
            self._wait(0)
            worked = self._work()
            if (not worked and not self._stopped and block
                    and not self._native and not self.queued_count):
                deadline = self.next_deadline
                timeout = None if deadline is None else max(0, deadline - self.clock())
                self._wait(timeout)
                if not self._control():
                    self._work()
            return not self._stopped
        except BaseException as error:
            self.close(error)
            raise
        finally:
            self._processing = False

    def run(self):
        self._check_active()
        try:
            while self.turn(block=True):
                pass
        finally:
            self.close()

    def close(self, initiating_error=None):
        self._check_thread()
        if self._stopped:
            return
        self._stopped = True
        self._inbox.clear()
        self._native.clear()
        self._heap.clear()
        self._timers.clear()
        self._timer_bytes = 0
        self._pending_frame = self._render_deadline = None
        for request, _ in self._requests.values():
            request.cancellation.cancel()
        self._requests.clear()
        self._request_bytes = 0
        self.session.close(initiating_error)
