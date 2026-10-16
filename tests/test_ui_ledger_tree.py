"""Tree domain-to-Ledger integration through the real operation bridge."""
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from cereja.ledger.app import Ledger
from cereja.ui.events import KeyEvent
from cereja.ui.testing import VirtualBackend
from cereja.ui.terminal import TerminalSession


class TreeLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.session = TerminalSession(VirtualBackend())
        self.session.__enter__()
        self.addCleanup(self.session.close)
        self.app = Ledger(self.session)
        self.addCleanup(self.app.close)

    def finish(self):
        end = time.monotonic() + 3
        while self.app.bridge.active and time.monotonic() < end:
            self.app.loop.turn()
            self.app.refresh()
            time.sleep(.001)
        self.assertFalse(self.app.bridge.active)

    def test_discovery_never_scans(self):
        with patch('os.scandir', side_effect=AssertionError('automatic scan')):
            self.app.composer.insert('/tree')
            self.app.submit()
            self.assertIs(self.app.overlays.top, self.app.tree_form)

    def test_root_load_expand_collapse_and_inspect(self):
        sub = self.root / 'café'
        sub.mkdir()
        (sub / 'a.txt').write_text('fixture')
        self.app._tree(str(self.root), 3)
        self.finish()
        self.assertEqual(self.app.results.current.state, 'Succeeded')
        tree = self.app._tree_result
        node = next(n for n in tree.records.values() if n['name'] == 'café')
        tree.view.select(node['id'])
        self.app.focus.focus('content')
        self.app.handle(KeyEvent('right'))
        self.finish()
        self.assertEqual(self.app.results.current.state, 'Succeeded')
        self.assertTrue(any(n['name'] == 'a.txt' for n in tree.records.values()))
        self.assertIn(node['id'], tree.view.expanded)
        self.app.handle(KeyEvent('left'))
        self.assertNotIn(node['id'], tree.view.expanded)
        self.app.handle(KeyEvent('enter'))
        self.assertIsNotNone(self.app.overlays.top)

    def test_root_failure_and_depth_zero_explicit(self):
        self.app._tree(str(self.root / 'missing'), 3)
        self.finish()
        self.assertEqual(self.app.results.current.state, 'Failed')
        self.app._tree(str(self.root), 0)
        self.finish()
        self.assertIn('Incomplete', self.app.results.current.content.text)

    def test_wide_directory_is_explicitly_incomplete(self):
        for index in range(200):
            (self.root / str(index)).touch()
        self.app._tree(str(self.root), 3)
        self.finish()
        self.assertLessEqual(len(self.app._tree_result.records), 64)
        self.assertIn('Incomplete', self.app.results.current.content.text)


if __name__ == '__main__':
    unittest.main()
