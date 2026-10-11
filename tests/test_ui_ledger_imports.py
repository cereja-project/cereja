"""Catalogue truth and lazy startup contracts, in isolated stdlib processes."""
from pathlib import Path
import subprocess
import sys
import unittest

from cereja.ledger.catalogue import COMMANDS, REFERENCES

ROOT = Path(__file__).resolve().parents[1]


class LedgerImportTest(unittest.TestCase):
    def process(self, code):
        result = subprocess.run([sys.executable, '-B', '-S', '-c', code], cwd=ROOT,
                                capture_output=True, text=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, '')
        return result.stdout

    def test_import_and_discovery_never_start_services(self):
        output = self.process('''
import ctypes, os, selectors, signal, subprocess, sys, threading
from contextlib import ExitStack
from unittest.mock import patch
targets = [(threading.Thread, 'start'), (signal, 'signal'), (subprocess, 'Popen'),
           (os, 'open'), (selectors, 'DefaultSelector')]
if os.name == 'nt': targets.append((ctypes, 'WinDLL'))
with ExitStack() as stack:
    for owner, name in targets:
        stack.enter_context(patch.object(owner, name, side_effect=AssertionError(name)))
    import cereja
    import cereja.ledger
    assert 'cereja.ledger.app' not in sys.modules
    from cereja.ledger.catalogue import COMMANDS, REFERENCES
    for entry in COMMANDS + REFERENCES: entry.description()
    assert 'cereja.ui' not in sys.modules
    from cereja.ledger.app import Ledger
assert not any(n.startswith(('cereja.system', 'cereja.http', 'cereja.hashtools',
                            'cereja.transfers', 'cereja.display')) for n in sys.modules)
''')
        self.assertEqual(output, '')

    def test_ui_help_and_plain_fallback_do_not_load_ui_or_read_input(self):
        for arguments in (['ui', '--help'], ['ui', '--plain'], ['ui']):
            with self.subTest(arguments=arguments):
                output = self.process('''
import io, sys
from unittest.mock import patch
from cereja.entrypoint import main
class NeverRead(io.StringIO):
    def read(self, *a): raise AssertionError('stdin read')
    def readline(self, *a): raise AssertionError('stdin read')
with patch.object(sys, 'stdin', NeverRead()):
    try: assert main(''' + repr(arguments) + ''') == 0
    except SystemExit as e: assert e.code == 0
assert not any(n.startswith('cereja.ui') for n in sys.modules)
assert 'cereja.ledger.app' not in sys.modules
''')
                self.assertNotIn('\x1b', output)
                self.assertIn('Ledger', output)

    def test_every_claimed_cli_is_registered_and_supports_help(self):
        from cereja.commands.registry import COMMANDS as CLI
        registered = {entry.name for entry in CLI}
        for entry in COMMANDS + REFERENCES:
            for invocation in entry.cli:
                words = invocation.split()
                self.assertEqual(words[0], 'cereja')
                self.assertIn(words[1], registered)
                result = subprocess.run([sys.executable, '-B', '-S', '-m', 'cereja', *words[1:], '--help'],
                                        cwd=ROOT, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, invocation + result.stderr)
                self.assertIn('usage:', result.stdout.lower())

    def test_every_claimed_api_resolves_and_every_guide_exists(self):
        self.assertEqual(self.process('''
import importlib
from cereja.ledger.catalogue import COMMANDS, REFERENCES
for entry in COMMANDS + REFERENCES:
    for name in entry.api:
        module, attribute = name.rsplit('.', 1)
        assert getattr(importlib.import_module(module), attribute) is not None, name
'''), '')
        for entry in COMMANDS + REFERENCES:
            if entry.guide:
                self.assertTrue((ROOT / entry.guide).is_file(), entry.guide)

    def test_unknown_paste_transport_uses_plain_without_terminal_acquisition(self):
        output = self.process('''
import io, sys
from types import SimpleNamespace
from unittest.mock import patch
from cereja.commands.ui import main
class TTY(io.StringIO):
    def isatty(self): return True
    def read(self, *a): raise AssertionError('read')
with patch.object(sys, 'stdin', TTY()), patch.object(sys.stdout, 'isatty', return_value=True):
    # Replace this module's platform view, not the shared stdlib os module.
    with patch('cereja.commands.ui.os', SimpleNamespace(name='nt')):
        assert main([]) == 0
    with patch('cereja.commands.ui.os', SimpleNamespace(name='posix')):
        assert main([]) == 0
assert not any(n.startswith('cereja.ui') for n in sys.modules)
''')
        self.assertIn('cannot distinguish paste', output)
        self.assertIn('--bracketed-paste', output)


if __name__ == '__main__':
    unittest.main()
