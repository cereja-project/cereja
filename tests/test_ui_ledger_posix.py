"""Automatic real-PTY Ledger smoke, distinct from human terminal acceptance."""
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest


@unittest.skipUnless(os.name == 'posix', 'POSIX PTY required')
class LedgerPtyTest(unittest.TestCase):
    def test_official_entry_paste_copy_exit_and_native_restore(self):
        import fcntl
        import pty
        import select
        import struct
        import termios
        master, slave = pty.openpty()
        process = None
        try:
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 80, 0, 0))
            before = termios.tcgetattr(slave)
            process = subprocess.Popen(
                [sys.executable, '-B', '-S', '-m', 'cereja', 'ui',
                 '--ascii', '--no-color', '--reduced-motion'],
                cwd=Path(__file__).resolve().parents[1], stdin=slave, stdout=slave, stderr=slave,
                env={**os.environ, 'TERM': 'xterm-256color', 'PYTHONIOENCODING': 'utf-8'})
            received = bytearray()
            def read_until(marker):
                deadline = time.monotonic() + 5
                while marker not in received and time.monotonic() < deadline:
                    if select.select([master], [], [], .1)[0]:
                        received.extend(os.read(master, 65536))
                    if len(received) > 1024 * 1024:
                        self.fail('bounded terminal output exceeded')
                self.assertIn(marker, received)
            read_until(b'Cereja TUI')
            self.assertIn(b'\x1b[?2004h', received)
            # One bracketed paste contains a runnable command and a newline.
            # Ctrl+A selects it; Ctrl+C must request copy instead of exiting.
            os.write(master, b'\x1b[200~/examples progress\n/home\x1b[201~\x01\x03')
            read_until(b'Copy unavailable')
            self.assertIsNone(process.poll())
            self.assertNotIn(b'Synthetic batches', received)
            # Delete the selected literal paste, then use job-aware idle exit.
            os.write(master, b'\x7f\x03')
            process.wait(timeout=5)
            self.assertEqual(process.returncode, 0)
            restored = termios.tcgetattr(slave)
            if sys.platform == 'darwin' and before[3] & termios.ICANON:
                # Darwin adds exactly PENDIN when canonical input is restored.
                # The independent OS reference lives in test_ui_posix.py.
                self.assertIn(restored[3], (before[3], before[3] | termios.PENDIN))
                restored[3] = before[3]
            self.assertEqual(restored, before)
        finally:
            if process is not None and process.poll() is None:
                process.kill()  # Test-owned failed child only, never application cancellation.
                process.wait(timeout=5)
            os.close(master)
            os.close(slave)
