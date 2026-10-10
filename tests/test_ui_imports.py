"""The independent UI must remain opt-in and standard-library-only."""

from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class UIImportTest(unittest.TestCase):
    def test_ui_namespace_defers_backend_and_has_no_side_effects(self):
        code = '''
import sys, threading
before = set(threading.enumerate())
import cereja
assert not any(n.startswith('cereja.ui') for n in sys.modules)
import cereja.ui
assert not any(n.startswith('cereja.ui.') for n in sys.modules)
assert set(threading.enumerate()) == before
assert 'cereja.display' not in sys.modules
'''
        self.check_process(code)

    def test_explicit_core_imports_use_no_legacy_or_third_party_runtime(self):
        code = '''
import sys, threading
before = set(threading.enumerate())
from cereja.ui.terminal import StreamBackend, TerminalSession
from cereja.ui.testing import VirtualBackend
from cereja.ui.events import KeyEvent
from cereja.ui.scheduling import EventLoop, Cancellation, payload_bytes
from cereja.ui.text import TextPolicy, text_metrics
from cereja.ui.buffer import CellBuffer, Layer, compose
from cereja.ui.rendering import Cursor, Renderer, full_diff, dirty_diff
from cereja.ui.layout import Constraint, Viewport, split_rows, split_columns, inset, layout_damage
from cereja.ui.editing import TextContent, TextSelection, TextInput, copy_action
from cereja.ui.focus import FocusManager, FocusScope, FocusTarget
from cereja.ui.overlays import Suggestions, ParameterForm, Confirmation, OverlayStack
from cereja.ui.collections import SelectableList, Table, TreeView
from cereja.ui.posix import PosixBackend
from cereja.ui.windows import WindowsBackend
assert 'cereja.display' not in sys.modules
assert 'cereja.system' not in sys.modules
assert set(threading.enumerate()) == before
assert not any('site-packages' in str(getattr(m, '__file__', ''))
               for m in sys.modules.values())
'''
        self.check_process(code)

    def test_terminal_import_defers_unicode_and_metrics_import_is_isolated(self):
        code = '''
import sys
from cereja.ui.terminal import TerminalSession
from cereja.ui.scheduling import EventLoop
assert 'cereja.ui.text' not in sys.modules
assert 'cereja.ui.buffer' not in sys.modules
assert 'cereja.ui._unicode17' not in sys.modules
from cereja.ui.text import text_metrics
assert text_metrics('test').line_widths() == (4,)
assert 'unicodedata' not in sys.modules
assert 'cereja.ui.posix' not in sys.modules
assert 'cereja.ui.windows' not in sys.modules
assert 'cereja.display' not in sys.modules
assert 'cereja.system' not in sys.modules
'''
        self.check_process(code)

    def test_imports_never_attempt_workers_handlers_or_terminal_acquisition(self):
        # A before/after snapshot alone would miss a short-lived worker or a
        # handler/mode installed and then restored during import.
        code = '''
import ctypes, os, selectors, signal, subprocess, threading
from contextlib import ExitStack
from unittest.mock import patch
targets = [(threading.Thread, 'start'), (signal, 'signal'),
           (subprocess, 'Popen'), (os, 'open'), (selectors, 'DefaultSelector')]
if os.name == 'posix':
    import termios
    targets.append((termios, 'tcsetattr'))
if os.name == 'nt':
    targets.append((ctypes, 'WinDLL'))
with ExitStack() as stack:
    for owner, name in targets:
        stack.enter_context(patch.object(owner, name,
                            side_effect=AssertionError('import acquired ' + name)))
    import cereja
    import cereja.ui
    from cereja.ui import terminal, testing, events, scheduling
    from cereja.ui import text, buffer, rendering, layout, editing, focus, overlays, collections, posix, windows
'''
        self.check_process(code)

    def check_process(self, code):
        result = subprocess.run([sys.executable, '-S', '-c', code], cwd=ROOT,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr, '')


if __name__ == '__main__':
    unittest.main()
