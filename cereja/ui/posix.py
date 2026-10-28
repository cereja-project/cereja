"""POSIX terminal transport and readiness, with reversible native resources.

Protocol inverses return to the normal screen, visible cursor and paste-off
baseline. They do not query or reconstruct arbitrary prior ANSI private state.
"""

from copy import deepcopy
import math
import os
import selectors
import signal
import threading
import time

try:
    import termios
    import tty
except ImportError:
    termios = tty = None

from ._capabilities import StreamBackend, detect_capabilities
from ._session import TerminalCleanupError
from .events import InputErrorEvent, ResizeEvent, WakeEvent


_NATIVE_AVAILABLE = os.name == 'posix' and termios is not None and tty is not None
_ENABLE = {'alternate_screen': '\x1b[?1049h', 'cursor': '\x1b[?25l',
           'paste': '\x1b[?2004h'}
_DISABLE = {'alternate_screen': '\x1b[?1049l', 'cursor': '\x1b[?25h',
            'paste': '\x1b[?2004l'}


class PosixBackend(StreamBackend):
    """Main-thread POSIX backend; ``wake`` alone is safe from other threads.

    Constructor/import performs no native acquisition. Noninteractive streams
    retain plain transport, including on hosts without termios. ``wait`` returns
    typed events, with one EOF and no subsequent blocking. Caller streams remain
    caller-owned. A session restores its resources; ``close`` also disposes any
    partially acquired backend resources and is idempotent.
    """

    def __init__(self, input_stream=None, output_stream=None, *, options=None,
                 environ=None, escape_timeout=0.03, parser=None,
                 clock=time.monotonic):
        super().__init__(input_stream, output_stream, options=options,
                         environ=environ, platform='posix')
        self.supports_acquisition = _NATIVE_AVAILABLE
        self.capabilities = detect_capabilities(
            self.input_stream, self.output_stream, options, environ,
            supports_acquisition=self.supports_acquisition, platform='posix')
        if parser is None:
            from ._input import EscapeParser
            parser = EscapeParser(escape_timeout=escape_timeout)
        elif (isinstance(escape_timeout, bool)
              or not isinstance(escape_timeout, (int, float))
              or not math.isfinite(escape_timeout)
              or not 0.01 <= escape_timeout <= 0.1):
            raise ValueError('escape_timeout must be finite and between 0.01 and 0.1')
        if not callable(clock):
            raise TypeError('clock must be callable')
        self._parser = parser
        self._clock = clock
        self._selector = None
        self._wake_read = self._wake_write = None
        self._wake_lock = threading.RLock()
        self._input_fd = self._output_fd = None
        self._snapshot = None
        self._acquired = []
        self._closed = False
        self._eof = False
        self._resize_pending = False

    @staticmethod
    def _check_thread():
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError('POSIX terminal operations require the main thread')

    def _check_open(self):
        self._check_thread()
        if self._closed:
            raise RuntimeError('POSIX backend is closed')

    def capture(self):
        self._check_open()
        if self._acquired:
            raise RuntimeError('POSIX resources already acquired')
        if self.capabilities.plain:
            self._snapshot = {}
            return {}
        self._input_fd = self.input_stream.fileno()
        self._output_fd = self.output_stream.fileno()
        snapshot = {
            'input_attrs': deepcopy(termios.tcgetattr(self._input_fd)),
            'output_attrs': deepcopy(termios.tcgetattr(self._output_fd)),
            'input_blocking': os.get_blocking(self._input_fd),
            'output_blocking': os.get_blocking(self._output_fd),
            'handlers': {sig: signal.getsignal(sig)
                         for sig in (signal.SIGINT, signal.SIGWINCH)},
        }
        self._snapshot = snapshot
        return snapshot

    def acquire(self, resource, snapshot):
        self._check_open()
        if self.capabilities.plain:
            raise RuntimeError('plain POSIX transport acquires no terminal modes')
        if resource not in ('output_mode', 'input_mode', 'signal_handlers', *_ENABLE):
            raise ValueError('unknown terminal resource')
        self._acquired.append(resource)
        if resource == 'output_mode':
            attrs = deepcopy(snapshot['output_attrs'])
            attrs[1] &= ~termios.OPOST
            termios.tcsetattr(self._output_fd, termios.TCSANOW, attrs)
        elif resource == 'input_mode':
            # TCSANOW avoids flushing already queued user input.
            tty.setraw(self._input_fd, when=termios.TCSANOW)
            os.set_blocking(self._input_fd, False)
            self._selector = selectors.DefaultSelector()
            self._wake_read, self._wake_write = os.pipe()
            os.set_blocking(self._wake_read, False)
            os.set_blocking(self._wake_write, False)
            self._selector.register(self._input_fd, selectors.EVENT_READ, 'input')
            self._selector.register(self._wake_read, selectors.EVENT_READ, 'wake')
        elif resource == 'signal_handlers':
            signal.signal(signal.SIGINT, signal.default_int_handler)
            signal.signal(signal.SIGWINCH, self._on_resize)
        else:
            self._control(_ENABLE[resource])

    @staticmethod
    def _attempt(actions):
        failures = []
        for name, action in actions:
            try:
                action()
            except BaseException as error:
                failures.append((name, error))
        if failures:
            raise TerminalCleanupError(failures)

    def _close_polling(self):
        with self._wake_lock:
            selector, self._selector = self._selector, None
            read_fd, self._wake_read = self._wake_read, None
            write_fd, self._wake_write = self._wake_write, None
            actions = []
            if selector is not None:
                actions.append(('selector', selector.close))
            for fd in (read_fd, write_fd):
                if fd is not None:
                    actions.append(('self-pipe', lambda fd=fd: os.close(fd)))
            self._attempt(actions)

    def restore(self, resource, snapshot):
        self._check_thread()
        try:
            if resource == 'input_mode':
                self._attempt([
                    ('polling', self._close_polling),
                    ('input attrs', lambda: termios.tcsetattr(
                        self._input_fd, termios.TCSANOW, snapshot['input_attrs'])),
                    ('input blocking', lambda: os.set_blocking(
                        self._input_fd, snapshot['input_blocking'])),
                ])
            elif resource == 'output_mode':
                self._attempt([
                    ('output attrs', lambda: termios.tcsetattr(
                        self._output_fd, termios.TCSANOW, snapshot['output_attrs'])),
                    ('output blocking', lambda: os.set_blocking(
                        self._output_fd, snapshot['output_blocking'])),
                ])
            elif resource == 'signal_handlers':
                self._attempt([(f'handler {sig}', lambda sig=sig: signal.signal(
                    sig, snapshot['handlers'][sig]))
                    for sig in (signal.SIGWINCH, signal.SIGINT)])
            elif resource in _DISABLE:
                self._control(_DISABLE[resource])
            else:
                raise ValueError('unknown terminal resource')
        finally:
            if resource in self._acquired:
                self._acquired.remove(resource)

    def _output_call(self, operation):
        self._check_open()
        if self.capabilities.plain or self._output_fd is None:
            return operation()
        # stdin/stdout can share an open-file description. Raw nonblocking input
        # must not turn a buffered text write into an unacknowledged byte suffix.
        was_blocking = os.get_blocking(self._output_fd)
        changed = not was_blocking
        initiating = None
        try:
            if changed:
                os.set_blocking(self._output_fd, True)
            return operation()
        except BaseException as error:
            initiating = error
            raise
        finally:
            if changed:
                try:
                    os.set_blocking(self._output_fd, False)
                except BaseException:
                    if initiating is None:
                        raise
                    try:
                        BaseException.add_note(initiating,
                            'POSIX output blocking restoration failed')
                    except BaseException:
                        pass

    def write(self, text):
        return self._output_call(lambda: self.output_stream.write(text))

    def flush(self):
        self._output_call(self.output_stream.flush)

    def _control(self, text):
        offset = 0
        while offset < len(text):
            count = self.write(text[offset:])
            if type(count) is not int or not 0 < count <= len(text) - offset:
                raise OSError('terminal control write did not acknowledge progress')
            offset += count
        self.flush()

    def dimensions(self):
        self._check_thread()
        return super().dimensions()

    def invalidate(self):
        self._check_open()
        self.invalidated = True

    def _signal_wake(self):
        fd = self._wake_write
        if fd is None:
            return False
        try:
            os.write(fd, b'\0')
        except BlockingIOError:
            pass  # A full pipe is already a pending readiness notification.
        except OSError:
            return False
        return True

    def wake(self):
        with self._wake_lock:
            return self._signal_wake()

    def _on_resize(self, signum, frame):
        self._resize_pending = True
        # A signal can interrupt code already holding the pipe lock. Do not
        # acquire a lock or draw here; the nonblocking byte only wakes select.
        self._signal_wake()

    def _finish_input(self):
        self._eof = True
        self._selector.unregister(self._input_fd)
        return self._parser.eof()

    @property
    def input_deadline(self):
        return self._parser.deadline

    def wait(self, timeout=None, *, read_input=True):
        self._check_open()
        if timeout is not None:
            if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                    or not math.isfinite(timeout) or timeout < 0):
                raise ValueError('timeout must be finite and nonnegative or None')
        if self.capabilities.plain or self._eof:
            return ()
        if self._selector is None:
            raise RuntimeError('POSIX input is not acquired')
        now = self._clock()
        pending = self._parser.expire(now) if read_input else ()
        if pending:
            return pending
        deadline = self._parser.deadline if read_input else None
        if deadline is not None:
            remaining = max(0.0, deadline - now)
            timeout = remaining if timeout is None else min(timeout, remaining)
        # Temporarily unregister readiness as well as skipping read(), so a
        # full retained batch cannot create an input-ready busy loop.
        paused = not read_input
        if paused:
            self._selector.unregister(self._input_fd)
        try:
            ready = self._selector.select(timeout)
        finally:
            if paused:
                self._selector.register(self._input_fd, selectors.EVENT_READ, 'input')
        now = self._clock()
        events = list(self._parser.expire(now)) if read_input else []
        woke = False
        for key, mask in ready:
            if key.data == 'wake':
                with self._wake_lock:
                    if self._wake_read is not None:
                        try:
                            os.read(self._wake_read, 4096)
                        except BlockingIOError:
                            pass
                woke = True
            elif key.data == 'input':
                try:
                    data = os.read(self._input_fd, 4096)
                except (BlockingIOError, InterruptedError):
                    continue
                except OSError as error:
                    events.append(InputErrorEvent(f'POSIX input failed: {error.strerror or "I/O error"}'))
                    events.extend(self._finish_input())
                else:
                    events.extend(self._parser.feed(data, now) if data else self._finish_input())
        if self._resize_pending:
            self._resize_pending = False
            events.append(ResizeEvent(*self.dimensions()))
        if woke:
            events.append(WakeEvent())
        return tuple(events)

    def close(self):
        self._check_thread()
        if self._closed:
            return
        failures = []
        for resource in reversed(tuple(self._acquired)):
            try:
                self.restore(resource, self._snapshot)
            except BaseException as error:
                failures.append((resource, error))
        try:
            self._close_polling()
        except BaseException as error:
            failures.append(('polling', error))
        self._closed = True
        if failures:
            raise TerminalCleanupError(failures)


__all__ = ['PosixBackend']
