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
assert 'cereja.display' not in sys.modules
assert 'cereja.system' not in sys.modules
assert set(threading.enumerate()) == before
assert not any('site-packages' in str(getattr(m, '__file__', ''))
               for m in sys.modules.values())
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
