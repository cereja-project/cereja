"""Directory completion through the real UI bridge and temporary directories."""
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from cereja.tui.paths import PathForm, directory_completions, MAX_COMPLETIONS
from cereja.ui.buffer import CellBuffer, Rect
from cereja.ui.events import KeyEvent
from cereja.ui.overlays import FormField
from cereja.ui.scheduling import EventLoop
from cereja.ui.terminal import TerminalSession
from cereja.ui.testing import VirtualBackend


class PathCompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.session = TerminalSession(VirtualBackend())
        self.session.__enter__()
        self.addCleanup(self.session.close)
        self.form = PathForm('paths-test', 'Paths', (FormField('root', 'Root'),))
        self.loop = EventLoop(self.session, self.form.consume)
        self.addCleanup(self.loop.close)
        self.form.bind(self.loop)
        self.addCleanup(self.form.close)

    def value(self, text):
        editor = self.form.input('root')
        editor.set_selection(0, len(editor.text))
        editor.insert(str(text))

    def key(self, key, **kwargs):
        return self.form.handle_completion(KeyEvent(key, **kwargs), 'root')

    def finish(self):
        deadline = time.monotonic() + 5
        while self.form._completion_bridge.active and time.monotonic() < deadline:
            self.loop.turn()
            self.form.consume(None)
            time.sleep(.001)
        self.assertFalse(self.form._completion_bridge.active)
        self.form.consume(None)

    def test_open_bind_empty_path_and_backward_tab_do_not_enumerate(self):
        with patch('os.scandir', side_effect=AssertionError('unexpected I/O')):
            self.assertIsNone(self.key('tab'))
            self.value(self.root)
            self.assertIsNone(self.key('tab', modifiers={'shift'}))
            self.assertIsNone(self.key('f1'))

    def test_single_completion_is_inserted_then_tab_visits_next_field(self):
        (self.root / 'Documents').mkdir()
        (self.root / 'Data.txt').write_text('not a directory')
        self.value(self.root / 'Doc')
        self.assertEqual(self.key('tab').kind, 'changed')
        self.finish()
        self.assertEqual(self.form.input('root').text, str(self.root / 'Documents') + os.sep)
        self.assertFalse(self.form.completing)
        self.assertIsNone(self.key('tab'))

    def test_multiple_candidates_can_be_navigated_and_selected(self):
        for name in ('alpha', 'beta', 'gamma'):
            (self.root / name).mkdir()
        self.value(str(self.root) + os.sep)
        self.key('tab')
        self.finish()
        self.assertEqual(len(self.form.completions), 3)
        self.key('down')
        self.assertEqual(self.form.completion_index, 1)
        frame = CellBuffer(60, 8)
        self.assertTrue(self.form.paint_completions(frame, Rect(0, 0, 60, 8)))
        text = '\n'.join(''.join(cell.text for cell in row) for row in frame.rows)
        self.assertIn('Directories', text)
        self.key('enter')
        self.assertEqual(self.form.input('root').text, str(self.root / 'beta') + os.sep)
        self.assertFalse(self.form.completing)

    def test_escape_discards_completion_without_closing_form_or_changing_value(self):
        (self.root / 'alpha').mkdir()
        (self.root / 'beta').mkdir()
        original = str(self.root) + os.sep
        self.value(original)
        self.key('tab')
        self.finish()
        self.assertEqual(self.key('escape').kind, 'changed')
        self.assertFalse(self.form.completing)
        self.assertEqual(self.form.input('root').text, original)

    def test_unavailable_directory_reports_error_and_does_not_trap_tab(self):
        self.value(self.root / 'missing' / 'prefix')
        self.key('tab')
        self.finish()
        self.assertIn('unavailable', self.form.completion_message)
        self.assertIsNone(self.key('tab'))
        self.assertFalse(self.form.completing)

    def test_slow_io_leaves_ui_responsive_and_stale_completion_cannot_overwrite_edit(self):
        entered, release = threading.Event(), threading.Event()
        owner = threading.get_ident()
        original_scandir = os.scandir
        def held(path):
            self.assertNotEqual(threading.get_ident(), owner)
            entered.set()
            self.assertTrue(release.wait(5))
            return original_scandir(path)
        (self.root / 'alpha').mkdir()
        self.value(self.root / 'al')
        with patch('cereja.tui.paths.os.scandir', side_effect=held):
            self.key('tab')
            self.assertTrue(entered.wait(5))
            try:
                self.assertEqual(self.key('escape').kind, 'changed')
                self.value(self.root / 'new-draft')
                self.assertTrue(self.form._completion_bridge.active)
            finally:
                release.set()
            self.finish()
        self.assertEqual(self.form.input('root').text, str(self.root / 'new-draft'))

    def test_candidate_count_is_bounded_and_partial_listing_never_auto_selects(self):
        for index in range(MAX_COMPLETIONS + 1):
            (self.root / f'directory-{index:03}').mkdir()
        self.value(str(self.root) + os.sep)
        self.key('tab')
        self.finish()
        self.assertLessEqual(len(self.form.completions), MAX_COMPLETIONS)
        self.assertIn('Partial', self.form.completion_message)
        self.assertTrue(self.form.completing)

    def test_close_detaches_delivery_while_owned_worker_finishes(self):
        entered, release = threading.Event(), threading.Event()
        def held(value):
            entered.set()
            self.assertTrue(release.wait(5))
            return (str(self.root / 'complete') + os.sep,), ''
        self.value(self.root / 'co')
        with patch('cereja.tui.paths.directory_completions', side_effect=held):
            self.key('tab')
            self.assertTrue(entered.wait(5))
            try:
                self.form.close()
                self.assertFalse(self.form.completing)
                self.assertTrue(self.form._completion_bridge.active)
            finally:
                release.set()
            self.finish()
        self.assertEqual(self.form.input('root').text, str(self.root / 'co'))
        self.assertNotEqual(self.form._completion_bridge.snapshot.delivery, 'delivered')

    def test_symlink_directories_are_not_suggested(self):
        (self.root / 'ordinary').mkdir()
        try:
            (self.root / 'linked').symlink_to(self.root / 'ordinary', target_is_directory=True)
        except OSError:
            self.skipTest('directory symlink creation unavailable')
        values, _ = directory_completions(str(self.root) + os.sep)
        self.assertEqual(values, (str(self.root / 'ordinary') + os.sep,))


if __name__ == '__main__':
    unittest.main()
