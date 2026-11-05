"""Task-first large-file journey, including keyboard and compact layout contracts."""
import unittest
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from cereja.tui.app import TUI
from cereja.ui.events import KeyEvent, PasteEvent
from cereja.ui.terminal import TerminalSession
from cereja.ui.testing import VirtualBackend


class JourneyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.size = (80, 24)
        session = TerminalSession(VirtualBackend(size=lambda: self.size))
        session.__enter__()
        self.addCleanup(session.close)
        self.app = TUI(session)
        self.addCleanup(self.app.close)

    def text(self):
        return '\n'.join(''.join(c.text for c in row) for row in self.app.render().rows)

    def test_home_has_a_focused_task_and_enter_opens_it_without_scanning(self):
        for size in ((40, 12), (80, 24)):
            self.size = size
            self.assertIn('Find large files', self.text())
        self.assertEqual(self.app.focus.focused, 'find-large-files')
        with patch('os.scandir', side_effect=AssertionError('opening a task must not scan')):
            self.app.handle(KeyEvent('enter'))
            self.assertIs(self.app.overlays.top, self.app.workflow_forms['large-files'])
            self.assertEqual(self.app.focus.focused, 'root')
            self.assertFalse(self.app.bridge.active)
            self.app.handle(KeyEvent('escape'))
        self.assertEqual(self.app.focus.focused, 'find-large-files')

    def test_typing_and_paste_from_home_use_the_existing_composer(self):
        self.assertEqual(self.app.focus.focused, 'find-large-files')
        self.app.handle(PasteEvent('/large-files\n/home'))
        self.assertEqual(self.app.focus.focused, 'composer')
        self.assertEqual(self.app.composer.text, '/large-files\n/home')
        self.assertFalse(self.app.bridge.active)
        self.assertIsNone(self.app.overlays.top)

    def open_form(self):
        self.app.handle(KeyEvent('enter'))
        return self.app.workflow_forms['large-files']

    def test_basic_form_only_shows_folder_and_size_with_advanced_accessible(self):
        form = self.open_form()
        self.assertEqual([f.identity for f in getattr(form, 'visible_fields', form.fields)],
                         ['root', 'min_size_bytes'])
        self.assertEqual(dict(form.values), dict(root='', min_size_bytes='0', max_results='20',
                                                max_entries='1000000', max_depth='64', max_errors='32'))
        self.assertIn('@advanced', [t.identity for t in form.targets])
        for size in ((40, 12), (80, 24)):
            self.size = size
            self.assertIn('Advanced', self.text())
            self.assertNotIn('Examined entries', self.text())

    def test_folder_enter_advances_without_starting_search(self):
        form = self.open_form()
        form.input('root').insert(str(self.root))
        self.app.handle(KeyEvent('enter'))
        self.assertEqual(self.app.focus.focused, 'min_size_bytes')
        self.assertIs(self.app.overlays.top, form)
        self.assertFalse(self.app.bridge.active)

    def test_minimum_size_accepts_exact_units_without_changing_domain_defaults(self):
        from cereja.tui.workflows import prepare
        form = self.open_form()
        form.input('root').insert(str(self.root))
        editor = form.input('min_size_bytes')
        for text, expected in [('1.5 MiB', 1572864), ('2 KB', 2000), ('0', 0), ('1KiB', 1024),
                               ('0.001 KB', 1), ('123456789012345678901234567890 B', 123456789012345678901234567890)]:
            with self.subTest(text=text):
                editor.set_selection(0, len(editor.text)); editor.insert(text)
                self.assertEqual(form.validate().kind, 'submit')
                values, _ = prepare('large-files', dict(form.values))
                self.assertEqual(values['min_size_bytes'], expected)
                self.assertEqual(values['max_entries'], 1000000)
        for text in ['-1', '1e9', '1.5 B', 'NaN', '١ MiB', '1 MB extra', '1\nKiB']:
            with self.subTest(invalid=text):
                editor.set_selection(0, len(editor.text)); editor.insert(text)
                self.assertEqual(form.validate().kind, 'rejected')

    def test_advanced_collapse_preserves_values_and_editor_state(self):
        form = self.open_form()
        self.assertIn('@advanced', [t.identity for t in form.targets])
        form.input('root').insert(str(self.root))
        self.app.focus.focus('@advanced'); self.app.handle(KeyEvent('enter'))
        self.assertTrue(form.advanced)
        self.assertEqual(self.app.focus.focused, 'max_results')
        editor = form.input('max_results')
        editor.set_selection(0, len(editor.text)); editor.insert('7')
        editor.set_selection(0, 1)
        before = editor.content, editor.selection, editor.caret
        self.app.focus.focus('@advanced'); self.app.handle(KeyEvent('enter'))
        self.assertFalse(form.advanced)
        self.assertEqual(dict(form.values)['max_results'], '7')
        self.app.focus.focus('@advanced'); self.app.handle(KeyEvent('enter'))
        self.assertEqual((editor.content, editor.selection, editor.caret), before)
        self.assertFalse(self.app.bridge.active)

    def test_invalid_hidden_limit_is_revealed_and_never_starts_work(self):
        form = self.open_form()
        form.input('root').insert(str(self.root))
        editor = form.input('max_results')
        editor.set_selection(0, len(editor.text)); editor.insert('0')
        self.app.focus.focus('@primary'); self.app.handle(KeyEvent('enter'))
        self.assertTrue(getattr(form, 'advanced', False))
        self.assertEqual(self.app.focus.focused, 'max_results')
        self.assertIn('max_results', form.errors)
        self.assertFalse(self.app.bridge.active)

    def finish(self):
        deadline = time.monotonic() + 5
        while self.app.bridge.active and time.monotonic() < deadline:
            self.app.loop.turn()
            self.app.refresh()
            time.sleep(.001)
        self.assertFalse(self.app.bridge.active)

    def search_from_home(self, minimum='1 KiB'):
        form = self.open_form()
        form.input('root').insert(str(self.root))
        self.app.handle(KeyEvent('enter'))
        field = form.input('min_size_bytes')
        field.set_selection(0, len(field.text)); field.insert(minimum)
        self.app.handle(KeyEvent('enter'))
        self.finish()
        return form

    def test_full_journey_results_details_and_back_preserve_selection(self):
        (self.root / 'relatório.txt').write_bytes(b'x' * 2048)
        (self.root / 'second.txt').write_bytes(b'x' * 1024)
        form = self.search_from_home()
        self.assertEqual(self.app.focus.focused, 'content')
        self.assertIn('Large files', self.text())
        self.assertNotIn('result-2', self.text())
        self.app.handle(KeyEvent('down'))
        before = self.app._file_browser().selected
        self.app.handle(KeyEvent('enter'))
        self.assertEqual(self.app.overlays.top.actions[0][0], 'details')
        self.app.handle(KeyEvent('enter'))
        self.assertIn('second.txt', self.app.overlays.top.content.text)
        self.app.handle(KeyEvent('escape'))
        self.assertEqual(self.app._file_browser().selected, before)
        self.app.handle(KeyEvent('escape'))
        self.assertIs(self.app.overlays.top, form)
        self.assertEqual(form.input('root').text, str(self.root))
        self.app.handle(KeyEvent('escape'))
        self.assertEqual(self.app.focus.focused, 'content')
        self.assertEqual(self.app._file_browser().selected, before)

    def test_empty_search_explains_next_step_without_file_actions(self):
        self.search_from_home('1 GiB')
        self.assertIn('No matching files observed.', self.text())
        self.assertIn('Esc', self.text())
        self.app.handle(KeyEvent('enter'))
        self.assertIsNone(self.app.overlays.top)

    def test_form_progress_uses_task_language_in_compact_layout(self):
        self.size = (40, 12)
        form = self.open_form()
        self.assertIn('Step 1/2', self.text())
        self.assertNotIn('Overlay', self.text())
        form.input('root').insert(str(self.root))
        self.app.handle(KeyEvent('enter'))
        self.assertIn('Step 2/2', self.text())


if __name__ == '__main__':
    unittest.main()
