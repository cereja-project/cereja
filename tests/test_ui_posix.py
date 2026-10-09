"""POSIX lifecycle fixtures run everywhere; PTY checks require a Unix host."""

from collections import deque
from contextlib import ExitStack
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import platform
import signal
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cereja.ui.events import EOFEvent, KeyEvent, PasteEvent, ResizeEvent, WakeEvent
from cereja.ui.posix import PosixBackend
from cereja.ui.terminal import TerminalSession


class Stream(io.StringIO):
    def __init__(self, fd):
        super().__init__()
        self.fd = fd

    def fileno(self):
        return self.fd

    def isatty(self):
        return True


class Parser:
    deadline = None

    def __init__(self):
        self.calls = []

    def feed(self, data, now):
        self.calls.append((data, now))
        return (KeyEvent('a', 'a'),)

    def expire(self, now):
        return ()

    def eof(self):
        return (EOFEvent(),)


class Selector:
    def __init__(self):
        self.registered = {}
        self.ready = []
        self.timeouts = []
        self.closed = False
        self.failure = None

    def register(self, fd, events, data):
        self.registered[fd] = data
        if self.failure == data:
            raise OSError('register ' + data)

    def unregister(self, fd):
        del self.registered[fd]

    def select(self, timeout):
        self.timeouts.append(timeout)
        return [(SimpleNamespace(data=self.registered[fd]), 1) for fd in self.ready
                if fd in self.registered]

    def close(self):
        self.closed = True


class PosixFixtureTests(unittest.TestCase):
    def test_paused_admission_unregisters_input_and_retains_parser_deadline(self):
        with TerminalSession(self.backend):
            self.selector.ready = [3, 30]
            self.reads[3].append(b'a')
            self.reads[30].append(b'w')
            self.parser.deadline = 10.03
            self.assertEqual(self.backend.wait(None, read_input=False), (WakeEvent(),))
            self.assertIsNone(self.selector.timeouts[-1])
            self.assertEqual(self.parser.calls, [])
            self.assertEqual(self.backend.input_deadline, 10.03)
            self.assertEqual(self.selector.registered[3], 'input')
            self.selector.ready = [3]
            self.assertEqual(self.backend.wait(0), (KeyEvent('a', 'a'),))

    def setUp(self):
        from cereja.ui import posix
        self.module = posix
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.attrs = {3: [1, 7, 3, 4, 5, 6, [b'x']],
                      4: [1, 7, 3, 4, 5, 6, [b'y']]}
        self.original = deepcopy(self.attrs)
        self.blocking = {3: True, 4: False, 30: True, 31: True}
        self.selector = Selector()
        self.closed = []
        self.reads = {3: deque(), 30: deque()}
        self.handlers = {signal.SIGINT: object(), getattr(signal, 'SIGWINCH', 28): object()}
        self.old_handlers = dict(self.handlers)
        self.now = [10.0]
        self.parser = Parser()
        termios = SimpleNamespace(TCSANOW=0, OPOST=1,
            tcgetattr=lambda fd: deepcopy(self.attrs[fd]),
            tcsetattr=lambda fd, when, attrs: self.attrs.__setitem__(fd, deepcopy(attrs)))
        def raw(fd, when):
            self.attrs[fd][3] = 0
        replacements = {
            '_NATIVE_AVAILABLE': True, 'termios': termios,
            'tty': SimpleNamespace(setraw=raw),
        }
        for name, value in replacements.items():
            self.stack.enter_context(patch.object(posix, name, value))
        self.stack.enter_context(patch.object(posix.selectors, 'DefaultSelector', return_value=self.selector))
        self.stack.enter_context(patch.object(posix.os, 'pipe', return_value=(30, 31)))
        # Python 3.11 on Windows has neither POSIX helper; fixtures supply them.
        self.stack.enter_context(patch.object(posix.os, 'get_blocking', create=True,
            side_effect=lambda fd: self.blocking[fd]))
        self.stack.enter_context(patch.object(posix.os, 'set_blocking', create=True,
            side_effect=lambda fd, value: self.blocking.__setitem__(fd, value)))
        self.stack.enter_context(patch.object(posix.os, 'close', side_effect=self.closed.append))
        self.stack.enter_context(patch.object(posix.os, 'write', side_effect=lambda fd, data: len(data)))
        self.stack.enter_context(patch.object(posix.os, 'read', side_effect=lambda fd, count: self.reads[fd].popleft()))
        self.stack.enter_context(patch.object(posix.os, 'get_terminal_size', return_value=os.terminal_size((91, 27))))
        self.stack.enter_context(patch.object(posix.signal, 'SIGWINCH', getattr(signal, 'SIGWINCH', 28), create=True))
        self.stack.enter_context(patch.object(posix.signal, 'getsignal', side_effect=lambda sig: self.handlers[sig]))
        self.stack.enter_context(patch.object(posix.signal, 'signal', side_effect=lambda sig, handler: self.handlers.__setitem__(sig, handler)))
        self.backend = PosixBackend(Stream(3), Stream(4), environ={'TERM': 'xterm'},
                                    parser=self.parser, clock=lambda: self.now[0])

    def test_session_restores_actual_snapshots_and_owned_polling_resources(self):
        with TerminalSession(self.backend) as session:
            self.assertFalse(self.blocking[3])
            session.write_text('é')
            self.assertEqual(self.backend.output_stream.getvalue().endswith('é'), True)
        self.assertEqual(self.attrs, self.original)
        self.assertEqual(self.blocking[3], True)
        self.assertEqual(self.blocking[4], False)
        self.assertEqual(self.handlers, self.old_handlers)
        self.assertTrue(self.selector.closed)
        self.assertCountEqual(self.closed, [30, 31])
        self.backend.close()
        self.backend.close()

    def test_registration_failure_restores_modes_and_closes_partial_setup(self):
        self.selector.failure = 'wake'
        with self.assertRaises(OSError):
            with TerminalSession(self.backend):
                pass
        self.assertEqual(self.attrs, self.original)
        self.assertTrue(self.blocking[3])
        self.assertEqual(self.blocking[4], False)
        self.assertTrue(self.selector.closed)
        self.assertCountEqual(self.closed, [30, 31])

    def test_signal_installation_failure_restores_all_captured_handlers(self):
        calls = []
        def install(sig, handler):
            self.handlers[sig] = handler
            calls.append(sig)
            if len(calls) == 1:
                raise OSError('partially installed handler')
        with patch.object(self.module.signal, 'signal', side_effect=install):
            with self.assertRaises(OSError):
                with TerminalSession(self.backend):
                    pass
        self.assertEqual(self.handlers, self.old_handlers)
        self.assertEqual(self.attrs, self.original)

    def test_input_and_resize_wake_are_both_delivered(self):
        with TerminalSession(self.backend):
            self.reads[3].append(b'a')
            self.reads[30].append(b'ww')
            self.selector.ready = [3, 30]
            self.backend._on_resize(signal.SIGWINCH, None)
            events = self.backend.wait(1)
            self.assertIn(KeyEvent('a', 'a'), events)
            self.assertIn(ResizeEvent(91, 27), events)
            self.assertIn(WakeEvent(), events)
            self.assertEqual(self.parser.calls, [(b'a', 10.0)])

    def test_escape_deadline_limits_wait_and_eof_is_not_repeated(self):
        with TerminalSession(self.backend):
            self.parser.deadline = 10.03
            self.backend.wait(1)
            self.assertAlmostEqual(self.selector.timeouts[-1], 0.03)
            self.selector.ready = [3]
            self.reads[3].append(b'')
            self.assertEqual(self.backend.wait(0), (EOFEvent(),))
            before = len(self.selector.timeouts)
            self.assertEqual(self.backend.wait(None), ())
            self.assertEqual(len(self.selector.timeouts), before)

    def test_external_sigint_restores_session_and_cross_thread_only_wakes(self):
        with self.assertRaises(KeyboardInterrupt):
            with TerminalSession(self.backend):
                signal.default_int_handler(signal.SIGINT, None)
        self.assertEqual(self.attrs, self.original)
        self.assertEqual(self.handlers, self.old_handlers)
        failures = []
        def worker():
            try:
                self.backend.capture()
            except RuntimeError as error:
                failures.append(error)
            self.backend.wake()
        worker_thread = threading.Thread(target=worker)
        worker_thread.start()
        worker_thread.join(2)
        self.assertFalse(worker_thread.is_alive())
        self.assertEqual(len(failures), 1)


@unittest.skipUnless(os.name == 'posix', 'actual POSIX PTY host required')
class PosixPTYTests(unittest.TestCase):
    def test_real_pty_rendering_resize_and_static_ascii_no_color(self):
        import selectors
        import termios
        from cereja.ui.buffer import CellBuffer, Style
        from cereja.ui.rendering import Renderer
        from cereja.ui.scheduling import EventLoop
        from cereja.ui.terminal import CapabilityOptions
        from cereja.ui.text import TextPolicy

        def drain():
            output = bytearray()
            with selectors.DefaultSelector() as selector:
                selector.register(self.master, selectors.EVENT_READ)
                self.assertTrue(selector.select(.5), 'flushed PTY output was unavailable')
                while selector.select(0):
                    output.extend(os.read(self.master, 65536))
            return output.decode('utf-8')

        original_size = termios.tcgetwinsize(self.slave)
        self.addCleanup(termios.tcsetwinsize, self.slave, original_size)
        cases = []
        for fallback in (False, True):
            with self.subTest(fallback=fallback):
                options = CapabilityOptions(unicode=False, reduced_motion=True) if fallback else None
                backend = PosixBackend(self.input, self.output, options=options,
                    environ={'TERM': 'xterm-256color', **({'NO_COLOR': '1'} if fallback else {})})
                self.addCleanup(backend.close)
                termios.tcsetwinsize(self.slave, (12, 40))
                with TerminalSession(backend) as session:
                    cases.append({name: getattr(session.capabilities, name) for name in
                                  ('plain', 'color_depth', 'unicode', 'cursor', 'alternate_screen',
                                   'paste', 'reduced_motion')})
                    renderer = Renderer(session, verify_damage=True)
                    for width, height in ((40, 12), (32, 10)):
                        termios.tcsetwinsize(self.slave, (height, width))
                        os.kill(os.getpid(), signal.SIGWINCH)
                        self.assertIn(ResizeEvent(width, height), backend.wait(.5))
                        frame = CellBuffer(width, height, policy=TextPolicy(ascii_only=fallback))
                        frame.draw_text(0, 0, 'e\u0301界😀\x1b]52;c;x\x07', style=Style(1, bold=True))
                        self.assertTrue(renderer.render(frame))
                        output = drain()
                        self.assertNotIn('\x1b]52;', output)
                        self.assertNotIn('\x07', output)
                        self.assertIn('?' if fallback else '界😀', output)
                        if fallback:
                            self.assertTrue(output.isascii())
                            self.assertTrue(all(cell.style.foreground is None
                                                for row in renderer.front for cell in row))
                        else:
                            self.assertEqual(renderer.front[0][0].style, Style(1, bold=True))
                        counts = session.write_count, session.flush_count
                        self.assertTrue(renderer.render(frame.copy(), damage=[]))
                        self.assertEqual((session.write_count, session.flush_count), counts)
                    if fallback:
                        self.assertFalse(session.animations_enabled)
                        loop = EventLoop(session, lambda event: None)
                        self.assertIsNone(loop.call_later(1, owner='spinner', decorative=True))
                        loop.close()
                self.assert_restored()
        report_directory = os.environ.get('CEREJA_UI_EVIDENCE_DIR')
        if report_directory:
            destination = Path(report_directory)
            destination.mkdir(parents=True, exist_ok=True)
            (destination / 'posix-pty.json').write_text(json.dumps({
                'host': 'OS PTY (not emulator)', 'platform': platform.platform(), 'python': sys.version,
                'encoding': self.output.encoding, 'dimensions': [[40, 12], [32, 10]],
                'capabilities': cases,
                'unicode_color': True, 'ascii_no_color_reduced_motion': True,
                'resize': True, 'restored': True, 'unchanged_writes_flushes': 0,
                'presentation_checked': False, 'emulator': None, 'emulator_version': None,
            }, indent=2) + '\n', encoding='utf-8')

    def test_real_pty_scheduler_idle_worker_wake_pressure_key_and_shutdown(self):
        import selectors
        # Discovery puts tests/ first, where legacy tests.py shadows the package.
        if __package__:
            from .ui_scheduling_probe import exercise_native
        else:
            from ui_scheduling_probe import exercise_native
        def inject_ready_key():
            os.write(self.master, b'x')
            # PTY master acknowledgement is not slave readiness under producer
            # pressure. Observe availability without consuming the key, then
            # retain the existing next-turn fairness assertion.
            with selectors.DefaultSelector() as selector:
                selector.register(self.slave, selectors.EVENT_READ)
                self.assertTrue(selector.select(.5), 'injected PTY key did not become readable')
        with TerminalSession(self.backend) as session:
            report = exercise_native(session, inject_ready_key)
        self.assertEqual(report['workload'], 10000)
        self.assertLessEqual(report['key_inspection_turn'], report['key_injection_turn'] + 1)
        self.assertTrue(report['worker_joined'])
        self.assert_restored()

    def setUp(self):
        import pty
        import termios
        self.master, self.slave = pty.openpty()
        self.addCleanup(os.close, self.master)
        self.addCleanup(os.close, self.slave)
        self.input = os.fdopen(os.dup(self.slave), 'r', encoding='utf-8')
        self.output = os.fdopen(os.dup(self.slave), 'w', encoding='utf-8')
        self.addCleanup(self.input.close)
        self.addCleanup(self.output.close)
        self.attrs = termios.tcgetattr(self.slave)
        self.blocking = os.get_blocking(self.slave)
        self.handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGWINCH)}
        self.backend = PosixBackend(self.input, self.output, environ={'TERM': 'xterm-256color'})
        self.addCleanup(self.backend.close)

    def assert_restored(self):
        import termios
        actual = termios.tcgetattr(self.slave)
        if sys.platform == 'darwin' and self.attrs[3] & termios.ICANON:
            # Darwin adds this kernel state when canonical input is restored.
            # Permit that exact addition, with every other flag/field unchanged.
            self.assertIn(actual[3], (self.attrs[3], self.attrs[3] | termios.PENDIN))
            actual[3] = self.attrs[3]
        self.assertEqual(actual, self.attrs)
        self.assertEqual(os.get_blocking(self.slave), self.blocking)
        self.assertEqual({sig: signal.getsignal(sig) for sig in self.handlers}, self.handlers)

    @unittest.skipUnless(sys.platform == 'darwin', 'Darwin kernel PENDIN reference')
    def test_darwin_direct_restore_adds_kernel_pending_state(self):
        import termios
        import tty
        # Independent OS reference: no session or backend acquisition is used.
        tty.setraw(self.slave, when=termios.TCSANOW)
        termios.tcsetattr(self.slave, termios.TCSANOW, self.attrs)
        actual = termios.tcgetattr(self.slave)
        self.assertEqual(actual[3] ^ self.attrs[3], termios.PENDIN)
        actual[3] = self.attrs[3]
        self.assertEqual(actual, self.attrs)

    def test_real_restore_preserves_queued_input_without_flushing(self):
        import selectors
        with TerminalSession(self.backend):
            os.write(self.master, b'typeahead')
        os.write(self.master, b'\n')
        expected = b'typeahead\n'
        received = bytearray()
        deadline = time.monotonic() + .5
        with selectors.DefaultSelector() as selector:
            selector.register(self.slave, selectors.EVENT_READ)
            while len(received) < len(expected):
                self.assertTrue(selector.select(max(0, deadline - time.monotonic())),
                                'restored canonical input must retain the line')
                data = os.read(self.slave, len(expected) - len(received))
                self.assertTrue(data, 'queued input must not end before the line')
                received.extend(data)
        self.assertEqual(received, expected)
        self.assert_restored()

    def test_real_pty_fragmented_input_wake_resize_and_restoration(self):
        import termios
        with TerminalSession(self.backend) as session:
            os.write(self.master, b'\xc3')
            self.assertEqual(self.backend.wait(0.2), ())
            os.write(self.master, b'\xa9\x1b[A\x03')
            events = self.backend.wait(0.2)
            self.assertIn(KeyEvent('é', 'é'), events)
            self.assertIn(KeyEvent('up'), events)
            self.assertIn(KeyEvent('c', modifiers=frozenset({'ctrl'})), events)
            worker = threading.Thread(target=self.backend.wake)
            worker.start()
            worker.join(2)
            self.assertFalse(worker.is_alive())
            self.assertIn(WakeEvent(), self.backend.wait(0.2))
            termios.tcsetwinsize(self.slave, (31, 99))
            os.kill(os.getpid(), signal.SIGWINCH)
            self.assertIn(ResizeEvent(99, 31), self.backend.wait(0.2))
            self.assertTrue(session.write_text('é'))
        self.assert_restored()

    def test_real_pty_exception_ctrl_c_and_suspend_restore_original_state(self):
        with TerminalSession(self.backend) as session:
            with session.suspend():
                self.assert_restored()
            self.assertTrue(session.needs_redraw)
        self.assert_restored()
        for error in (ValueError('body'), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(type(error)) as caught:
                    with TerminalSession(self.backend):
                        raise error
                self.assertIs(caught.exception, error)
                self.assert_restored()

    def test_real_partial_selector_setup_closes_pipe_and_restores_native_state(self):
        from cereja.ui import posix
        real_factory = posix.selectors.DefaultSelector
        allocated = []
        backend = self.backend
        class FailingSelector:
            def __init__(self):
                self.native = real_factory()

            def register(self, fd, events, data):
                self.native.register(fd, events, data)
                if data == 'wake':
                    allocated.extend((backend._wake_read, backend._wake_write))
                    raise OSError('partial native registration')

            def close(self):
                self.native.close()

        with patch.object(posix.selectors, 'DefaultSelector', FailingSelector):
            with self.assertRaises(OSError):
                TerminalSession(backend).__enter__()
        self.assert_restored()
        self.assertEqual(len(allocated), 2)
        for fd in allocated:
            with self.assertRaises(OSError):
                os.fstat(fd)
        with TerminalSession(backend):
            pass
        self.assert_restored()

    def test_real_external_sigint_restores_modes_flags_and_handlers(self):
        with self.assertRaises(KeyboardInterrupt):
            with TerminalSession(self.backend):
                os.kill(os.getpid(), signal.SIGINT)
        self.assert_restored()

    def test_real_fragmented_paste_and_lone_escape_timeout(self):
        with TerminalSession(self.backend):
            for data in (b'\x1b[20', b'0~a\x03\xc3', b'\xa9\x1b[20'):
                os.write(self.master, data)
                self.assertEqual(self.backend.wait(0.2), ())
            os.write(self.master, b'1~')
            self.assertEqual(self.backend.wait(0.2), (PasteEvent('a\x03é'),))
            os.write(self.master, b'\x1b')
            self.assertEqual(self.backend.wait(0.2), ())
            self.assertEqual(self.backend.wait(0.2), (KeyEvent('escape'),))


if __name__ == '__main__':
    unittest.main()
