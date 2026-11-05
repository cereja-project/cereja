"""Keyboard-to-worker file actions against disposable files only."""
import json
import unittest
from unittest.mock import patch

from cereja.tui.large_files import human_size
from cereja.ui.events import KeyEvent
if __package__:
    from . import test_ui_ledger_large_files as fixtures
else:
    import test_ui_ledger_large_files as fixtures


class FileBrowserTests(unittest.TestCase):
    def setUp(self):
        self.ui = fixtures.LargeFilesLedgerTests()
        self.ui.setUp()
        self.addCleanup(self.ui.doCleanups)
        self.app = self.ui.app
        self.source = self.ui.root / 'large.bin'
        self.source.write_bytes(b'123456')

    def start(self):
        self.ui.start()
        return self.ui.finish()

    def key(self, key):
        self.app.handle(KeyEvent(key))

    def menu(self, action):
        self.app.focus.focus('content')
        self.key('enter')
        menu = self.app.overlays.top
        menu.index = next(i for i, (name, _) in enumerate(menu.actions) if name == action)
        self.key('enter')

    def destination(self, path):
        form = self.app.overlays.top
        form.input('destination').insert(str(path))
        self.key('enter')
        self.assertIs(self.app.overlays.top, self.app._file_review)

    def confirm(self):
        self.app.focus.focus('@primary')
        self.key('enter')
        return self.ui.finish()

    def test_binary_sizes_and_exact_bytes_in_details(self):
        self.assertEqual(human_size(1024), '1.00 KiB')
        self.assertEqual(human_size(1853575860), '1.73 GiB')
        self.assertEqual(human_size(0), '0 B')
        self.start()
        self.menu('details')
        self.assertIn('Exact logical size: 6 bytes', self.app.overlays.top.content.text)

    def test_arrow_navigation_menu_escape_and_scan_details(self):
        (self.ui.root / 'small.txt').write_text('a')
        self.start()
        self.assertEqual(self.app.focus.focused, 'content')
        browser = self.app._file_browser()
        self.assertEqual(browser.selected['relative'], 'large.bin')
        self.key('down')
        self.assertEqual(browser.selected['relative'], 'small.txt')
        self.key('home')
        self.key('enter')
        self.assertEqual(self.app.focus.focused, '@choose')
        self.assertIn('Enter: choose | Esc: Back', self.ui.text(self.app.render()))
        self.key('down')
        self.assertIn('> Copy file...', self.app.overlays.top.content.text)
        self.key('escape')
        self.assertEqual(self.app.focus.focused, 'content')
        self.key('s')
        self.assertIn('Scan: Complete', self.app.overlays.top.content.text)

    def test_copy_requires_confirmation_and_never_replaces_destination(self):
        self.start()
        target = self.ui.root / 'copy.bin'
        self.menu('copy')
        self.destination(target)
        self.assertFalse(target.exists())
        self.assertEqual(self.app.focus.focused, '@back')
        result = self.confirm()
        self.assertEqual(result.state, 'Succeeded')
        self.assertEqual(target.read_bytes(), b'123456')
        self.assertTrue(self.source.exists())
        self.start()
        self.menu('copy')
        self.destination(target)
        self.assertEqual(self.confirm().state, 'Failed')
        self.assertEqual(target.read_bytes(), b'123456')

    def test_delete_back_preserves_file_then_explicit_run_deletes(self):
        origin = self.start()
        self.menu('delete')
        self.assertTrue(self.source.exists())
        self.assertEqual(self.app.focus.focused, '@back')
        self.key('enter')
        self.assertTrue(self.source.exists())
        self.assertIsNone(self.app.overlays.top)
        self.menu('delete')
        self.assertEqual(self.confirm().state, 'Succeeded')
        self.assertFalse(self.source.exists())
        self.assertEqual(json.loads(origin.attachment)['files'], [])
        self.assertIs(self.app.results.current, origin)
        self.assertEqual(self.app.focus.focused, 'content')

    def test_move_publishes_new_file_before_removing_source(self):
        self.start()
        target = self.ui.root / 'moved.bin'
        self.menu('move')
        self.destination(target)
        self.assertTrue(self.source.exists())
        self.assertFalse(target.exists())
        result = self.confirm()
        self.assertEqual(result.state, 'Succeeded')
        self.assertFalse(self.source.exists())
        self.assertEqual(target.read_bytes(), b'123456')
        self.assertIn('snapshot', result.content.text)

    def test_changed_source_refuses_delete_and_does_not_leak_error(self):
        self.start()
        self.source.write_bytes(b'changed since scan')
        self.menu('delete')
        result = self.confirm()
        self.assertEqual(result.state, 'Failed')
        self.assertIn('Selected file changed', result.content.text)
        self.assertTrue(self.source.exists())

    def test_directory_open_runs_only_after_explicit_menu_choice(self):
        self.start()
        def requested(action, selection, destination, context):
            context.running()
            return 'Directory requested'
        with patch('cereja.tui.file_actions.execute', side_effect=requested) as execute:
            self.menu('open-directory')
            self.assertEqual(self.ui.finish().state, 'Succeeded')
        self.assertEqual(execute.call_args.args[0], 'open-directory')

    def test_compact_menu_keeps_selected_action_visible(self):
        self.start()
        self.ui.size = (40, 12)
        self.key('enter')
        self.key('end')
        self.assertIn('> File details', self.ui.text(self.app.render()))

    def test_selected_file_remains_visible_across_supported_sizes(self):
        (self.ui.root / 'small.txt').write_text('a')
        self.start()
        for size in ((40, 12), (40, 13), (40, 14), (80, 24), (120, 40), (40, 12)):
            with self.subTest(size=size):
                self.ui.size = size
                for key, name in (('home', 'large.bin'), ('down', 'small.txt')):
                    self.key(key)
                    screen = self.ui.text(self.app.render())
                    self.assertIn(name, screen)
                    self.assertIn('Scan: Complete', screen)
                    self.key('enter')
                    self.assertIn(name, self.ui.text(self.app.render()))
                    self.key('escape')
                    self.assertEqual(self.app.focus.focused, 'content')

    def test_compact_incomplete_scan_keeps_status_and_selected_file(self):
        for i in range(5):
            (self.ui.root / ('entry' + str(i))).write_text('x')
        self.ui.start(max_entries=3)
        self.ui.finish()
        self.ui.size = (40, 12)
        screen = self.ui.text(self.app.render())
        self.assertIn('Scan: Incomplete', screen)
        self.assertIn(self.app._file_browser().selected['relative'], screen)

    def test_attachment_counts_toward_retention_and_is_evicted_with_block(self):
        from cereja.tui.model import Results
        results = Results(max_bytes=1000, block_bytes=100)
        block = results.append('/large-files', 'pending', active=True)
        results.finish(block, 'Succeeded', 'done', attachment='a' * 800)
        self.assertGreater(results.retained_bytes, 800)
        results.append('/home', 'x' * 100)
        results.append('/home', 'x' * 100)
        self.assertNotIn(block, results.blocks)
        self.assertLessEqual(results.retained_bytes, 1000)

    def test_long_path_display_does_not_exceed_collection_field_limit(self):
        from cereja.tui.file_browser import FileBrowser
        path = 'x' * 17000
        browser = FileBrowser(json.dumps(dict(files=[dict(relative=path, size=1, selection=None)], omitted=0)))
        self.assertEqual(browser.selected['relative'], path)
        self.assertIn('[display shortened]', browser.view.item('0').cells[1])

    def test_unicode_file_name_is_readable_in_list_menu_and_details(self):
        name = 'relatório 日本語.txt'
        (self.ui.root / name).write_bytes(b'x' * 10)
        self.start()
        self.assertIn(name, self.ui.text(self.app.render()))
        self.key('enter')
        self.assertIn(name, self.ui.text(self.app.render()))
        self.key('end')
        self.key('enter')
        self.assertIn(name, self.app.overlays.top.content.text)
        self.assertIn('Exact logical size: 10 bytes', self.app.overlays.top.content.text)

    def test_display_names_neutralize_controls_and_remain_byte_bounded(self):
        from cereja.tui.file_browser import FileBrowser
        for name in ('café\n\t\x1b[2J\x85\u202eevil.txt', '界' * 17000, '\ud800name'):
            with self.subTest(name=name[:30]):
                browser = FileBrowser(json.dumps(dict(files=[dict(relative=name, size=1, selection=None)], omitted=0)))
                label = browser.view.item('0').cells[1]
                self.assertLessEqual(len(label.encode('utf-8')), 8300)
                self.assertFalse(any(ord(char) < 32 or 127 <= ord(char) <= 159 or char == '\u202e' for char in label))
                self.assertEqual(browser.selected['relative'], name)
        self.assertIn('café', FileBrowser(json.dumps(dict(files=[dict(relative='café', size=1, selection=None)], omitted=0))).view.item('0').cells[1])
