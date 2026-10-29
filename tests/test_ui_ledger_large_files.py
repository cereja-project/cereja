"""Large-file form, worker ownership and report semantics through the real UI bridge."""
import errno
import inspect
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from unittest.mock import patch

from cereja.tui.app import TUI
from cereja.tui.large_files import MAX_TEXT_BYTES
from cereja.system.file_sizes import FileSize, FileSizeError, find_large_files
from cereja.ui.events import KeyEvent, ResizeEvent, OperationResultEvent
from cereja.ui.terminal import TerminalSession
from cereja.ui.testing import VirtualBackend


class LargeFilesLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.size = (80, 24)
        self.session = TerminalSession(VirtualBackend(size=lambda: self.size))
        self.session.__enter__()
        self.addCleanup(self.session.close)
        self.app = TUI(self.session)
        self.addCleanup(self.app.close)
        self.form = self.app.workflow_forms['large-files']
        self.defaults = dict(self.form.values)

    def field(self, name, value):
        editor = self.form.input(name)
        editor.set_selection(0, len(editor.text))
        editor.insert(str(value))

    def open(self):
        self.app.focus.focus('composer')
        self.app.composer.set_selection(0, len(self.app.composer.text))
        self.app.composer.insert('/large-files')
        self.app.handle(KeyEvent('enter'))
        self.assertIs(self.app.overlays.top, self.form)

    def start(self, **values):
        self.open()
        options = dict(self.defaults, root=str(self.root))
        options.update(values)
        for name, value in options.items():
            self.field(name, value)
        self.app.focus.focus('@primary')
        self.app.handle(KeyEvent('enter'))

    def finish(self):
        deadline = time.monotonic() + 5
        while self.app.bridge.active and time.monotonic() < deadline:
            self.app.loop.turn()
            self.app.refresh()
            time.sleep(.001)
        self.assertFalse(self.app.bridge.active)
        self.app.refresh()
        return self.app.results.blocks[-1]

    @staticmethod
    def text(frame):
        return '\n'.join(''.join(c.text for c in row) for row in frame.rows)

    def test_discovery_help_back_and_reopen_never_scan(self):
        with patch('os.scandir', side_effect=AssertionError('automatic scan')):
            self.open()
            self.field('root', self.root)
            self.app.focus.focus('root')
            self.app.handle(KeyEvent('f1'))
            self.assertIn('No Cancel', self.text(self.app.render()))
            self.app.handle(KeyEvent('escape'))
            self.assertIs(self.app.overlays.top, self.form)
            self.app.focus.focus('@back')
            self.app.handle(KeyEvent('enter'))
            self.open()
            self.assertEqual(self.form.input('root').text, str(self.root))
            self.assertFalse(self.app.bridge.active)

    def test_defaults_and_validation_match_api_minima_without_io(self):
        signature = inspect.signature(find_large_files)
        for name, value in self.defaults.items():
            if name != 'root':
                self.assertEqual(int(value), signature.parameters[name].default)
        self.open()
        self.field('root', self.root)
        with patch('os.scandir', side_effect=AssertionError('invalid form scanned')):
            for name, invalid in (('min_size_bytes', '-1'), ('max_results', '0'),
                                  ('max_entries', '0'), ('max_depth', '-1'), ('max_errors', '-1'),
                                  ('max_results', '1.5'), ('max_depth', 'True'), ('max_results', '١')):
                with self.subTest(name=name, value=invalid):
                    for key, value in self.defaults.items():
                        if key != 'root':
                            self.field(key, value)
                    self.field(name, invalid)
                    self.app.focus.focus('@primary')
                    self.app.handle(KeyEvent('enter'))
                    self.assertIs(self.app.overlays.top, self.form)
                    self.assertIn(name, self.form.errors)
                    self.assertFalse(self.app.bridge.active)

    def test_real_form_preserves_api_options_includes_hidden_binary_and_ignored_without_reads(self):
        (self.root / '.git').mkdir()
        files = {'.hidden': b'123', 'binary.bin': b'\x00\xff' * 5,
                 '.git/ignored.bin': b'x' * 12, '.gitignore': b'*', 'small': b'x'}
        for path, contents in files.items():
            (self.root / path).write_bytes(contents)
        with patch('builtins.open', side_effect=AssertionError('file content read')), \
                patch('pathlib.Path.open', side_effect=AssertionError('file content read')), \
                patch('cereja.system.file_sizes.find_large_files', wraps=find_large_files) as api:
            self.start(min_size_bytes=3, max_results=2, max_entries=123, max_depth=4, max_errors=0)
            block = self.finish()
        api.assert_called_once_with(str(self.root), min_size_bytes=3, max_results=2,
                                    max_entries=123, max_depth=4, max_errors=0)
        self.assertEqual(block.command, '/large-files')
        self.assertEqual(block.state, 'Succeeded')
        self.assertIn('Scan: Complete', block.content.text)
        self.assertIn('Results truncated: True; retained files: 2', block.content.text)
        self.assertIn('matched files: 3', block.content.text)
        self.assertLess(block.content.text.index('12 B | ".git/ignored.bin"'),
                        block.content.text.index('10 B | "binary.bin"'))
        self.start()
        self.assertIn('3 B | ".hidden"', self.finish().content.text)

    def test_incomplete_scan_is_distinct_from_retention_and_empty_result(self):
        (self.root / 'sub').mkdir()
        (self.root / 'sub' / 'a').write_bytes(b'1234')
        (self.root / 'b').write_bytes(b'12')
        for options, reason in ((dict(max_entries=1), 'max_entries'), (dict(max_depth=0), 'max_depth')):
            with self.subTest(reason=reason):
                self.start(**options)
                text = self.finish().content.text
                self.assertIn('Scan: Incomplete: ' + reason, text)
                self.assertIn('whole-root largest files are unknown', text)
                self.assertIn('Results truncated: False', text)
        self.start(min_size_bytes=100)
        text = self.finish().content.text
        self.assertIn('Scan: Complete', text)
        self.assertIn('No matching files observed.', text)

    def test_filesystem_errors_and_error_retention_are_visible(self):
        (self.root / 'sub').mkdir()
        scandir = os.scandir
        def denied(path):
            if Path(path) == self.root / 'sub':
                raise PermissionError(errno.EACCES, 'SECRET filesystem details')
            return scandir(path)
        with patch('os.scandir', side_effect=denied):
            self.start(max_errors=0)
            text = self.finish().content.text
            self.start(max_errors=1)
            details = self.finish().content.text
        self.assertIn('Scan: Incomplete: filesystem_error', text)
        self.assertIn('Errors: 1; retained details: 0; error details truncated: True', text)
        self.assertNotIn('SECRET', text)
        self.assertIn(f'Error: scandir; errno={errno.EACCES}; path=', details)
        self.assertIn('error details truncated: False', details)
        self.assertNotIn('SECRET', details)

    def test_links_are_skipped_and_linked_roots_refused(self):
        (self.root / 'target').write_bytes(b'abc')
        try:
            (self.root / 'link').symlink_to(self.root / 'target')
            (self.root / 'linked-root').symlink_to(self.root, target_is_directory=True)
        except OSError:
            self.skipTest('symlink creation unavailable')
        self.start()
        text = self.finish().content.text
        self.assertIn('Scan: Complete', text)
        self.assertIn('Skipped links/reparse points: 2', text)
        self.start(root=str(self.root / 'linked-root'))
        block = self.finish()
        self.assertEqual(block.state, 'Failed')
        self.assertIn('root components must not be links', block.content.text)

    def test_publication_is_bounded_and_escapes_paths_without_losing_scan_summary(self):
        report = find_large_files(self.root)
        hostile = '界\n\t\x1b[31m\udcff'
        report = replace(report, files=tuple(FileSize(hostile, hostile + str(i), 999 - i) for i in range(400)),
                         matched_files=400, errors=(FileSizeError(hostile, 'stat', 13),), error_count=1,
                         complete=False, reasons=('filesystem_error',))
        with patch('cereja.system.file_sizes.find_large_files', return_value=report):
            self.start(max_results=400)
            block = self.finish()
        text = block.content.text
        self.assertIn('Scan: Incomplete: filesystem_error', text)
        self.assertIn('Results truncated: False; retained files: 400', text)
        self.assertIn('Errors: 1', text)
        self.assertIn('UI display truncated', text)
        self.assertIn(json.dumps(hostile + '0', ensure_ascii=True), text)
        self.assertNotIn('\x1b', text)
        self.assertLessEqual(len(text.encode('utf-8')), MAX_TEXT_BYTES)
        self.assertLessEqual(self.app.results.retained_bytes, self.app.results.max_bytes)
        self.assertIs(type(self.app.bridge.snapshot.outcome.value), str)

    def test_missing_root_and_worker_failure_are_sanitized_and_next_scan_can_run(self):
        self.start(root=str(self.root / 'missing'))
        self.assertEqual(self.finish().state, 'Failed')
        with patch('cereja.system.file_sizes.find_large_files', side_effect=RuntimeError('SECRET\x1b')):
            self.start()
            block = self.finish()
        self.assertEqual(block.state, 'Failed')
        self.assertNotIn('SECRET', block.content.text)
        self.start()
        self.assertEqual(self.finish().state, 'Succeeded')

    def test_long_expanded_root_keeps_publication_bounded_and_summary_intact(self):
        report = replace(find_large_files(self.root), root='/' + '\u0080' * 2200)
        with patch('cereja.system.file_sizes.find_large_files', return_value=report):
            self.start()
            text = self.finish().content.text
        self.assertIn('Scan: Complete', text)
        self.assertIn('No matching files observed.', text)
        self.assertIn('[UI root display truncated]', text)
        self.assertLessEqual(len(text.encode('utf-8')), MAX_TEXT_BYTES)

    def test_terminal_loss_detaches_without_stopping_or_joining_scanner(self):
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        scandir = os.scandir
        worker_threads = []
        def held(path):
            worker_threads.append(threading.current_thread())
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test worker release timed out')
            return scandir(path)
        from cereja.tui.large_files import scan
        def observed(values, context):
            try:
                return scan(values, context)
            finally:
                finished.set()
        with patch('os.scandir', side_effect=held), patch('cereja.tui.large_files.scan', side_effect=observed):
            self.start()
            try:
                self.assertTrue(entered.wait(3))
                self.app.close()
                self.assertFalse(finished.is_set())
                self.assertTrue(worker_threads[0].is_alive())
                self.assertTrue(self.app.results.blocks[-1].active)
            finally:
                release.set()
                self.assertTrue(finished.wait(3))
                for worker in worker_threads:
                    worker.join(3)  # Test-owned join after consumer close, never on the UI path.
                    self.assertFalse(worker.is_alive())

    def test_worker_start_failure_and_final_delivery_failure_claim_no_success(self):
        with patch.object(self.app.bridge, 'start', side_effect=RuntimeError('SECRET')):
            self.start()
        self.assertEqual(self.app.results.blocks[-1].state, 'Failed')
        original = self.app.loop.wait_post
        def broken(event, **kwargs):
            if isinstance(event, OperationResultEvent):
                raise RuntimeError('SECRET delivery')
            return original(event, **kwargs)
        with patch.object(self.app.loop, 'wait_post', side_effect=broken):
            self.start()
            block = self.finish()
        self.assertEqual(block.state, 'Unavailable')
        self.assertNotIn('SECRET', block.content.text)

    def test_ui_responds_while_real_scandir_is_held_slot_stays_owned_until_worker_exit(self):
        entered, release = threading.Event(), threading.Event()
        scandir = os.scandir
        workers = []
        def held(path):
            workers.append(threading.get_ident())
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test worker release timed out')
            return scandir(path)
        with patch('os.scandir', side_effect=held):
            self.start()
            try:
                self.assertTrue(entered.wait(3))
                block = self.app.results.blocks[-1]
                self.assertNotEqual(workers[0], threading.get_ident())
                self.app.composer.set_selection(0, len(self.app.composer.text))
                self.app.composer.insert('draft kept during scan')
                self.app.handle(KeyEvent('f1'))
                self.assertIn('Cereja TUI keyboard', self.text(self.app.render()))
                self.app.handle(KeyEvent('escape'))
                self.size = (40, 12)
                self.app.handle(ResizeEvent(*self.size))
                self.assertEqual(self.app.composer.text, 'draft kept during scan')
                self.assertTrue(self.app.bridge.active)
                self.assertFalse(self.app.progress.determinate)
                self.assertEqual(self.app.bridge.exit_choices, ('return', 'wait'))
                self.app._workflow_review('large-files', dict(self.form.values))
                self.assertIn('Busy', self.app.notice)
                self.assertIs(self.app.results.blocks[-1], block)
                self.app._exit()
                self.app.focus.focus('wait')
                self.app.handle(KeyEvent('enter'))
                self.assertTrue(self.app.waiting)
                self.app._exit()
                self.app.handle(KeyEvent('escape'))
                self.assertFalse(self.app.waiting)
                self.assertTrue(block.active)
                self.assertFalse(self.app.loop.stopped)
            finally:
                release.set()
                self.finish()
        self.assertEqual(block.state, 'Succeeded')
        self.assertEqual(len(workers), 1)

    def test_all_six_fields_remain_reachable_in_compact_layout(self):
        self.size = (40, 12)
        self.open()
        for spec in self.form.fields:
            self.assertEqual(self.app.focus.focused, spec.identity)
            self.assertIn(spec.label[:20], self.text(self.app.render()))
            self.app.handle(KeyEvent('tab'))
        self.assertEqual(self.app.focus.focused, '@primary')
        self.app.handle(KeyEvent('enter'))
        self.assertIn('root', self.form.errors)
        self.assertFalse(self.app.bridge.active)


if __name__ == '__main__':
    unittest.main()
