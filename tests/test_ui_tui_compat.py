"""Canonical TUI imports and identity-preserving legacy module paths."""
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULES = ('app', 'catalogue', 'examples', 'large_files', 'model', 'system', 'tree', 'workflows')


class TUICompatibilityTests(unittest.TestCase):
    def process(self, code):
        result = subprocess.run([sys.executable, '-B', '-S', '-c', code], cwd=ROOT,
                                capture_output=True, text=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((result.stdout, result.stderr), ('', ''))

    def test_both_package_imports_are_silent_and_do_not_load_application_or_toolkit(self):
        self.process('''
import sys, threading
from unittest.mock import patch
before = set(threading.enumerate())
with patch.object(threading.Thread, 'start', side_effect=AssertionError('worker at import')):
    import cereja
    assert 'cereja.tui' not in sys.modules and 'cereja.ledger' not in sys.modules
    import cereja.tui
    import cereja.ledger
    assert 'TUI' in dir(cereja.tui)
    assert 'TUI' not in vars(cereja.tui)
assert set(threading.enumerate()) == before
assert not any(n.startswith(('cereja.tui.', 'cereja.ledger.', 'cereja.ui', 'cereja.system')) for n in sys.modules)
''')

    def test_modules_alias_in_both_import_orders_and_share_mutation(self):
        for legacy_first in (False, True):
            with self.subTest(legacy_first=legacy_first):
                self.process('''
import importlib
from unittest.mock import patch
names = ''' + repr(MODULES) + '''
for name in names:
    order = ('cereja.ledger.', 'cereja.tui.') if ''' + repr(legacy_first) + ''' else ('cereja.tui.', 'cereja.ledger.')
    first, second = (importlib.import_module(prefix + name) for prefix in order)
    assert first is second, name
    assert first.__name__ == 'cereja.tui.' + name, name
    with patch.object(first, '_compat_probe', object(), create=True):
        assert second._compat_probe is first._compat_probe
import cereja.ledger, cereja.tui
assert cereja.ledger.app is cereja.tui.app
from cereja.tui import TUI
from cereja.tui.app import TUI as DirectTUI
from cereja.ledger.app import Ledger
assert Ledger is TUI is DirectTUI
assert TUI.__name__ == 'TUI' and TUI.__module__ == 'cereja.tui.app'
''')

    def test_legacy_patch_reaches_canonical_workflow(self):
        self.process('''
from unittest.mock import patch
from cereja.tui.workflows import execute
import cereja.ledger.large_files
with patch('cereja.ledger.large_files.scan', return_value='legacy patch') as mocked:
    assert execute('large-files', {}, object()) == 'legacy patch'
    mocked.assert_called_once()
''')

    def test_legacy_pickle_globals_and_new_class_roundtrip(self):
        self.process('''
import pickle
from cereja.tui import TUI
from cereja.tui.model import ResultBlock
assert pickle.loads(b'ccereja.ledger.app\\nLedger\\n.') is TUI
assert pickle.loads(b'ccereja.ledger.model\\nResultBlock\\n.') is ResultBlock
assert pickle.loads(pickle.dumps(TUI)) is TUI
''')

    def test_legacy_import_constructs_the_canonical_ui_and_runs_large_files(self):
        self.process('''
from pathlib import Path
import tempfile, time
from cereja.ledger.app import Ledger
from cereja.tui import TUI
from cereja.ui.events import KeyEvent
from cereja.ui.terminal import TerminalSession
from cereja.ui.testing import VirtualBackend
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory).resolve()
    (root / '.binary').write_bytes(b'\\x00\\xff')
    with TerminalSession(VirtualBackend()) as session:
        application = Ledger(session)
        try:
            assert type(application) is TUI
            application.composer.insert('/large-files')
            application.submit()
            application.overlays.top.input('root').insert(str(root))
            application.focus.focus('@primary')
            application.handle(KeyEvent('enter'))
            deadline = time.monotonic() + 5
            while application.bridge.active and time.monotonic() < deadline:
                application.loop.turn()
                application.refresh()
                time.sleep(.001)
            assert not application.bridge.active
            block = application.results.blocks[-1]
            assert block.state == 'Succeeded' and '2 B | ".binary"' in block.content.text
        finally:
            application.close()
''')


if __name__ == '__main__':
    unittest.main()
