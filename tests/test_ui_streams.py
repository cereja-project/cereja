"""Actual redirected files and OS pipes, separate from emulator walkthroughs."""

import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cereja.ui.buffer import CellBuffer
from cereja.ui.rendering import Renderer
from cereja.ui.terminal import StreamBackend, TerminalSession


ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
REDIRECTED = r'''
import os, sys
from cereja.ui.buffer import CellBuffer, Style
from cereja.ui.rendering import Renderer
from cereja.ui.terminal import CapabilityOptions, TerminalSession
from cereja.ui.text import TextPolicy
if os.name == 'nt':
    from cereja.ui.windows import WindowsBackend as Backend
else:
    from cereja.ui.posix import PosixBackend as Backend
backend = Backend(options=CapabilityOptions(color=24, cursor=True,
                  unicode=False, reduced_motion=True), environ={'CI': '1'})
try:
    with TerminalSession(backend) as session:
        assert session.capabilities.plain
        assert not session.animations_enabled
        assert session.capabilities.color_depth == 0
        # Plain backends deliberately leave stream input to their consumer.
        source = sys.stdin.read()
        assert sys.stdin.read() == ''  # Real EOF after the parent's close.
        frame = CellBuffer(24, 1, policy=TextPolicy(ascii_only=True))
        frame.draw_text(0, 0, source, style=Style(foreground=1, bold=True))
        renderer = Renderer(session)
        assert renderer.render(frame)
        counts = session.write_count, session.flush_count
        assert renderer.render(frame.copy(), damage=[])
        assert (session.write_count, session.flush_count) == counts
finally:
    backend.close()
'''


class RealStreamTests(unittest.TestCase):
    def assert_plain(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, '')
        self.assertEqual(result.stdout.strip(), 'A?\\x1b[31m')
        self.assertNotIn('\x1b', result.stdout)
        self.assertTrue(result.stdout.isascii())

    def test_native_redirected_stdin_stdout_pipes_and_real_eof(self):
        result = subprocess.run([sys.executable, '-B', '-S', '-c', REDIRECTED],
                                input='A😀\x1b[31m', capture_output=True,
                                text=True, encoding='utf-8', cwd=ROOT, env=ENV, timeout=15)
        self.assert_plain(result)

    def test_native_redirected_files_and_real_eof(self):
        with tempfile.TemporaryDirectory(prefix='cereja-ui-streams-') as directory:
            source = Path(directory) / 'input.txt'
            target = Path(directory) / 'output.txt'
            source.write_text('A😀\x1b[31m', encoding='utf-8')
            with source.open('r', encoding='utf-8') as stdin, target.open('w', encoding='utf-8') as stdout:
                result = subprocess.run([sys.executable, '-B', '-S', '-c', REDIRECTED],
                                        stdin=stdin, stdout=stdout, stderr=subprocess.PIPE,
                                        text=True, encoding='utf-8', cwd=ROOT, env=ENV, timeout=15)
            result.stdout = target.read_text(encoding='utf-8')
            self.assert_plain(result)

    def test_devnull_streams_remain_plain_with_explicit_capability_assertions(self):
        result = subprocess.run([sys.executable, '-B', '-S', '-c', REDIRECTED],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE, text=True, encoding='utf-8',
                                cwd=ROOT, env=ENV, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')

    def test_real_closed_reader_failure_closes_invalidates_and_is_observable(self):
        read_fd, write_fd = os.pipe()
        # Unbuffered binary -> text gives an actual OS failure on write/flush,
        # without retaining unwritten buffered bytes at interpreter shutdown.
        raw = os.fdopen(write_fd, 'wb', buffering=0)
        with os.fdopen(read_fd, 'rb', buffering=0) as reader, \
                io.TextIOWrapper(raw, encoding='utf-8', write_through=True) as output:
            backend = StreamBackend(output_stream=output)
            with TerminalSession(backend) as session:
                renderer = Renderer(session)
                frame = CellBuffer(12, 1)
                frame.draw_text(0, 0, 'open')
                self.assertTrue(renderer.render(frame))
                previous = renderer.front
                reader.close()
                frame.draw_text(0, 0, 'closed')
                try:
                    completed = renderer.render(frame)
                except OSError:
                    # Windows CRT anonymous pipes can surface EINVAL rather
                    # than BrokenPipeError. It must remain observable.
                    self.assertEqual(os.name, 'nt')
                    self.assertFalse(session.broken_pipe)
                else:
                    self.assertFalse(completed)
                    self.assertTrue(session.broken_pipe)
                self.assertTrue(session.closed)
                self.assertTrue(session.needs_redraw)
                self.assertFalse(renderer.screen_known)
                self.assertEqual(renderer.front, previous)


if __name__ == '__main__':
    unittest.main()
