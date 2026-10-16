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

from cereja.ledger.app import Ledger
from cereja.ledger.workflows import prepare
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
        session = TerminalSession(VirtualBackend())
        session.__enter__()
        self.addCleanup(session.close)
        self.app = Ledger(session)
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
        with patch('cereja.ledger.workflows.execute', side_effect=AssertionError('automatic execution')):
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
        from cereja.ledger.workflows import highlight_spans
        self.assertEqual(highlight_spans('Straße <tag>', ('STRASSE', '<tag>')), ((0, 6), (7, 12)))
        self.assertEqual(highlight_spans('abc', ('[.*]',)), ())

    def test_download_url_restrictions(self):
        for url in ('file:///tmp/a', 'https://user:pass@example.com/a', 'https://example.com/a#secret'):
            with self.assertRaises(ValueError):
                prepare('download', dict(url=url, destination=str(self.root / 'output')))


if __name__ == '__main__':
    unittest.main()
