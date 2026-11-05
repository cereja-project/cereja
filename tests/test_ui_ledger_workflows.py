"""Owned end-to-end fixtures for Ledger context/archive/download adapters."""
import contextlib
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from cereja.tui.app import TUI
from cereja.tui.workflows import prepare
from cereja.transfers import download
from cereja.ui.events import KeyEvent
from cereja.ui.terminal import TerminalSession
from cereja.ui.testing import VirtualBackend


@contextlib.contextmanager
def server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            if self.path == '/known':
                self.send_header('Content-Length', '7')
            self.end_headers()
            self.wfile.write(b'fixture')
        def log_message(self, *args):
            pass
    instance = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=instance.serve_forever)
    worker.start()
    try:
        yield 'http://127.0.0.1:' + str(instance.server_port)
    finally:
        instance.shutdown()
        instance.server_close()
        worker.join()


class WorkflowTests(unittest.TestCase):
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

    def finish(self):
        end = time.monotonic() + 5
        while self.app.bridge.active and time.monotonic() < end:
            self.app.loop.turn()
            self.app.refresh()
            time.sleep(.001)
        self.assertFalse(self.app.bridge.active)

    def review(self, name, values):
        form = self.app.workflow_forms[name]
        for key, value in values.items():
            field = form.input(key)
            field.set_selection(0, len(field.text))
            field.insert(value)
        self.assertTrue(form.validate())
        self.app._workflow_review(name, dict(form.values))
        self.app.render()

    def confirm(self):
        self.app.focus.focus('@primary')
        self.app.handle(KeyEvent('enter'))
        self.finish()

    def test_discovery_never_invokes_services(self):
        with patch('cereja.tui.workflows.execute', side_effect=AssertionError('automatic execution')):
            for command in ('context', 'compress', 'download'):
                self.app.composer.set_selection(0, len(self.app.composer.text))
                self.app.composer.insert('/' + command)
                self.app.submit()
                self.assertIs(self.app.overlays.top, self.app.workflow_forms[command])
                self.app.overlays.close()
        self.assertFalse(self.app.bridge.active)

    def test_context_real_search_no_match_binary_and_no_cache(self):
        (self.root / 'a.txt').write_text('needle fixture\n', encoding='utf-8')
        (self.root / 'binary').write_bytes(b'\0\xff')
        self.review('context', dict(root=str(self.root), query='needle'))
        self.finish()
        block = self.app.results.current
        self.assertEqual(block.state, 'Succeeded')
        self.assertIn('needle fixture', block.content.text)
        self.assertIn('Skipped:', block.content.text)
        self.review('context', dict(root=str(self.root), query='missing'))
        self.finish()
        self.assertIn('No matches', self.app.results.current.content.text)

    def test_context_wide_root_refused_before_search(self):
        for index in range(70):
            (self.root / str(index)).touch()
        with patch('cereja.system.search_text_context', side_effect=AssertionError('unbounded search')):
            self.review('context', dict(root=str(self.root), query='needle'))
            self.finish()
        self.assertEqual(self.app.results.current.state, 'Failed')

    def test_archive_requires_exact_target_confirmation_and_roundtrips(self):
        source = self.root / 'source'
        source.write_bytes(b'fixture')
        archive = self.root / 'archive'
        self.review('compress', dict(action='compress', mode='file', source=str(source), destination=str(archive)))
        self.assertFalse(archive.exists())
        self.assertFalse(self.app.bridge.active)
        self.assertEqual(self.app.focus.focused, '@back')
        self.confirm()
        self.assertEqual(self.app.results.current.state, 'Succeeded')
        output = self.root / 'output'
        self.review('compress', dict(action='decompress', mode='file', source=str(archive), destination=str(output)))
        self.confirm()
        self.assertEqual(output.read_bytes(), b'fixture')

    @unittest.skipUnless(os.name == 'nt', 'Exclusive directory publication requires Windows')
    def test_directory_archive_actual_form_roundtrip(self):
        source = self.root / 'tree'
        source.mkdir()
        (source / 'empty').mkdir()
        (source / 'café.txt').write_text('fixture')
        archive = self.root / 'tree.cjz'
        self.review('compress', dict(action='compress', mode='directory', source=str(source), destination=str(archive)))
        self.confirm()
        self.assertEqual(self.app.results.current.state, 'Succeeded')
        output = self.root / 'expanded'
        self.review('compress', dict(action='decompress', mode='directory', source=str(archive), destination=str(output)))
        self.confirm()
        self.assertEqual(self.app.results.current.state, 'Succeeded')
        self.assertTrue((output / 'empty').is_dir())
        self.assertEqual((output / 'café.txt').read_text(), 'fixture')

    def test_changed_fields_invalidate_review(self):
        source = self.root / 'source'
        source.touch()
        self.review('compress', dict(action='compress', mode='file', source=str(source), destination=str(self.root / 'output')))
        form = self.app.workflow_forms['compress']
        form.input('destination').insert('changed')
        self.app.focus.focus('@primary')
        self.app.handle(KeyEvent('enter'))
        self.assertFalse(self.app.bridge.active)
        self.assertFalse((self.root / 'output').exists())

    def test_download_known_unknown_limit_and_existing_destination(self):
        with server() as base:
            for suffix in ('known', 'unknown'):
                output = self.root / suffix
                self.review('download', dict(url=base + '/' + suffix, destination=str(output)))
                self.assertFalse(output.exists())
                self.confirm()
                self.assertEqual(self.app.results.current.state, 'Succeeded')
                self.assertEqual(output.read_bytes(), b'fixture')
            with self.assertRaises(ValueError):
                download(base + '/unknown', self.root / 'limited', max_bytes=3, overwrite=False)
            self.assertFalse((self.root / 'limited').exists())
            with self.assertRaises(FileExistsError):
                download(base + '/known', self.root / 'known', overwrite=False)
            self.assertEqual((self.root / 'known').read_bytes(), b'fixture')
            self.assertFalse(list(self.root.glob('*.part')))

    def test_safe_casefold_highlight_spans(self):
        from cereja.tui.workflows import highlight_spans
        self.assertEqual(highlight_spans('Straße <tag>', ('STRASSE', '<tag>')), ((0, 6), (7, 12)))
        self.assertEqual(highlight_spans('abc', ('[.*]',)), ())

    def test_download_url_restrictions(self):
        for url in ('file:///tmp/a', 'https://user:pass@example.com/a', 'https://example.com/a#secret'):
            with self.assertRaises(ValueError):
                prepare('download', dict(url=url, destination=str(self.root / 'output')))

    def test_invalid_workflow_field_keeps_form_values_and_focus_without_work(self):
        cases = (
            ('context', 'query', dict(root=str(self.root), query='a' * 257), '256'),
            ('context', 'root', dict(root='bad\npath', query='needle'), 'control'),
            ('download', 'url', dict(url='file:///not-http', destination=str(self.root / 'new')), 'HTTP'),
            ('download', 'url', dict(url='https://[bad', destination=str(self.root / 'new')), 'HTTP'),
            ('download', 'destination', dict(url='https://example.test/a', destination='bad\npath'), 'control'),
            ('compress', 'source', dict(source='bad\npath', destination=str(self.root / 'new')), 'control'),
        )
        for size in ((40, 12), (80, 24)):
            self.size = size
            for name, invalid, values, explanation in cases:
                with self.subTest(size=size, workflow=name, field=invalid):
                    form = self.app.workflow_forms[name]
                    for key, value in values.items():
                        editor = form.input(key)
                        editor.set_selection(0, len(editor.text))
                        editor.insert(value)
                    before = form.values
                    self.app.overlays.open(form)
                    self.app.handle(KeyEvent('enter'))
                    try:
                        self.assertIs(self.app.overlays.top, form)
                        self.assertEqual(self.app.focus.focused, invalid)
                        self.assertIn(explanation, form.errors[invalid])
                        self.assertEqual(form.values, before)
                        self.assertFalse(self.app.bridge.active)
                    finally:
                        if self.app.overlays.top is form:
                            self.app.overlays.close()

    def test_preparation_failure_does_not_dismiss_valid_form_or_echo_exception(self):
        form = self.app.workflow_forms['context']
        form.input('root').insert(str(self.root))
        form.input('query').insert('needle')
        self.app.overlays.open(form)
        self.app.focus.focus('query')
        before = form.values
        with patch('cereja.tui.workflows.prepare', side_effect=OSError('private-target')):
            self.app.handle(KeyEvent('enter'))
        self.assertIs(self.app.overlays.top, form)
        self.assertEqual(self.app.focus.focused, 'query')
        self.assertEqual(form.values, before)
        self.assertNotIn('private-target', self.app.notice)
        self.assertFalse(self.app.bridge.active)

    def test_corrected_context_submission_retires_validation_notice(self):
        (self.root / 'a.txt').write_text('needle fixture', encoding='utf-8')
        form = self.app.workflow_forms['context']
        form.input('root').insert(str(self.root))
        query = form.input('query')
        for size in ((40, 12), (80, 24)):
            with self.subTest(size=size):
                self.size = size
                query.set_selection(0, len(query.text))
                query.insert('a' * 257)
                self.app.overlays.open(form)
                self.app.handle(KeyEvent('enter'))
                self.assertEqual(self.app.notice, 'Review the visible field errors')
                self.assertIs(self.app.overlays.top, form)
                query.set_selection(0, len(query.text))
                query.insert('needle')
                self.app.handle(KeyEvent('enter'))
                self.finish()
                self.assertEqual(self.app.results.current.state, 'Succeeded')
                self.assertEqual(self.app.notice, '')
                frame = self.app.render()
                lines = [''.join(cell.text for cell in row) for row in frame.rows]
                self.assertNotIn('Review the visible field errors', '\n'.join(lines))
                self.assertIn('Succeeded', lines[-1])

    def test_valid_form_submission_keeps_new_preparation_error(self):
        form = self.app.workflow_forms['context']
        form.input('root').insert(str(self.root))
        form.input('query').insert('needle')
        self.app.overlays.open(form)
        self.app.notice = 'Previous validation notice'
        with patch('cereja.tui.workflows.prepare', side_effect=ValueError('private detail')):
            self.app.handle(KeyEvent('enter'))
        self.assertEqual(self.app.notice, 'Invalid parameters. Review the workflow help and explicit paths.')
        self.assertIs(self.app.overlays.top, form)
        self.assertFalse(self.app.bridge.active)

    def test_valid_form_submission_keeps_new_busy_notice_without_queuing(self):
        entered, release = threading.Event(), threading.Event()
        def held(context):
            context.running()
            entered.set()
            release.wait(3)
            return 'completed'
        self.app.bridge.start('held', held)
        try:
            self.assertTrue(entered.wait(1))
            form = self.app.workflow_forms['context']
            form.input('root').insert(str(self.root))
            form.input('query').insert('needle')
            self.app.overlays.open(form)
            self.app.notice = 'Previous validation notice'
            count = len(self.app.results.blocks)
            with patch('cereja.tui.workflows.execute', side_effect=AssertionError('must not queue')) as execute:
                self.app.handle(KeyEvent('enter'))
                execute.assert_not_called()
            self.assertEqual(self.app.notice, 'Busy: one operation is active. Nothing was queued.')
            self.assertEqual(len(self.app.results.blocks), count)
        finally:
            release.set()
            self.finish()
        self.assertEqual(self.app.notice, 'Busy: one operation is active. Nothing was queued.')

    def test_valid_form_submission_exposes_worker_failure_after_old_notice(self):
        form = self.app.workflow_forms['context']
        form.input('root').insert(str(self.root))
        form.input('query').insert('needle')
        self.app.overlays.open(form)
        self.app.notice = 'Previous validation notice'
        with patch('cereja.tui.workflows.execute', side_effect=ValueError('private detail')):
            self.app.handle(KeyEvent('enter'))
            self.finish()
        self.assertEqual(self.app.notice, '')
        self.assertEqual(self.app.results.current.state, 'Failed')
        lines = [''.join(cell.text for cell in row) for row in self.app.render().rows]
        self.assertIn('Failed', lines[-1])
        self.assertNotIn('private detail', '\n'.join(lines))

    def test_tilde_path_is_identical_with_and_without_completion(self):
        from cereja.tui.paths import directory_completions
        (self.root / 'Documents').mkdir()
        with patch.dict(os.environ, {'HOME': str(self.root), 'USERPROFILE': str(self.root)}):
            values, target = prepare('context', dict(root='~/Documents', query='needle'))
            matches, _ = directory_completions('~/Doc')
        self.assertIsNone(target)
        self.assertEqual(values['root'], str(self.root / 'Documents'))
        self.assertEqual(values['root'], os.path.normpath(matches[0]))


if __name__ == '__main__':
    unittest.main()
