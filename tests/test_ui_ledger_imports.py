"""Catalogue truth and lazy startup contracts, in isolated stdlib processes."""
from pathlib import Path
import subprocess
import sys
import unittest

from cereja.tui.catalogue import COMMANDS, REFERENCES

ROOT = Path(__file__).resolve().parents[1]


class LedgerImportTest(unittest.TestCase):
    def process(self, code):
        result = subprocess.run([sys.executable, '-B', '-S', '-c', code], cwd=ROOT,
                                capture_output=True, text=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, '')
        return result.stdout

    def test_windows_probe_import_in_discovery_and_package_modes(self):
        # Only exercise the import boundary here. The native test still owns
        # real ConPTY coverage on Windows; no platform or native API is faked.
        for pattern in ('test*.py', 'test_ui_*.py', None):
            with self.subTest(pattern=pattern):
                self.process('''
import importlib, unittest
from pathlib import Path
from unittest.mock import patch
pattern = ''' + repr(pattern) + '''
if pattern is None:
    module = importlib.import_module('tests.test_ui_ledger_windows')
    helper = importlib.import_module('tests.ui_windows_conpty_probe')
else:
    loader = unittest.TestLoader()
    loader.discover('tests', pattern=pattern)
    assert not loader.errors, loader.errors
    module = importlib.import_module('test_ui_ledger_windows')
    helper = importlib.import_module('ui_windows_conpty_probe')
assert Path(helper.__file__).resolve() == Path('tests/ui_windows_conpty_probe.py').resolve()
class ProbeReached(Exception):
    pass
case = module.LedgerWindowsNativeTest('test_conpty_official_entry_paste_copy_exit_and_restore')
# Call only up to the native boundary, even on non-Windows hosts. Raising here
# also prevents evidence files or a simulated success report from being written.
with patch.object(helper, 'probe', side_effect=ProbeReached):
    with case.assertRaises(ProbeReached):
        case.test_conpty_official_entry_paste_copy_exit_and_restore()
''')

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
    import cereja.tui
    assert 'cereja.tui.app' not in sys.modules
    from cereja.tui.catalogue import COMMANDS, REFERENCES
    for entry in COMMANDS + REFERENCES: entry.description()
    assert 'cereja.ui' not in sys.modules
    from cereja.tui import TUI
    from cereja.tui.workflows import forms
    assert 'large-files' in forms()
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
assert 'cereja.tui.app' not in sys.modules
assert 'cereja.system.file_sizes' not in sys.modules
''')
                self.assertNotIn('\x1b', output)
                self.assertIn('Cereja TUI', output)

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
from cereja.tui.catalogue import COMMANDS, REFERENCES
for entry in COMMANDS + REFERENCES:
    for name in entry.api:
        module, attribute = name.rsplit('.', 1)
        assert getattr(importlib.import_module(module), attribute) is not None, name
'''), '')
        for entry in COMMANDS + REFERENCES:
            if entry.guide:
                self.assertTrue((ROOT / entry.guide).is_file(), entry.guide)

    def test_unsupported_platform_uses_plain_without_terminal_acquisition(self):
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
    with patch('cereja.commands.ui.os', SimpleNamespace(name='unsupported')):
        assert main([]) == 0
assert not any(n.startswith('cereja.ui') for n in sys.modules)
''')
        self.assertIn('requires a Windows or POSIX terminal', output)

    def test_interactive_entry_requests_paste_automatically_and_keeps_old_flag(self):
        self.process('''
import io, sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from cereja.commands.ui import main
from cereja.ui.terminal import CapabilityOptions
class TTY(io.StringIO):
    def isatty(self): return True
    def read(self, *a): raise AssertionError('read')
for platform, backend in (('nt', 'cereja.ui.windows.WindowsBackend'),
                          ('posix', 'cereja.ui.posix.PosixBackend')):
    for arguments in ([], ['--bracketed-paste']):
        session = MagicMock()
        session.capabilities.plain = False
        with patch.object(sys, 'stdin', TTY()), patch.object(sys.stdout, 'isatty', return_value=True), \
                patch('cereja.commands.ui.os', SimpleNamespace(name=platform)), \
                patch(backend) as native, \
                patch('cereja.ui.terminal.TerminalSession') as terminal, \
                patch('cereja.tui.TUI') as app:
            terminal.return_value.__enter__.return_value = session
            assert main(arguments) == 0
            options = native.call_args.kwargs['options']
            assert isinstance(options, CapabilityOptions)
            assert options.paste is True
            app.assert_called_once_with(session, low_bandwidth=False)
            app.return_value.run.assert_called_once_with()
            terminal.return_value.__exit__.assert_called_once()
''')

    def test_native_plain_fallback_never_constructs_application(self):
        output = self.process('''
import io, sys
from unittest.mock import MagicMock, patch
from cereja.commands.ui import main
class TTY(io.StringIO):
    def isatty(self): return True
    def read(self, *a): raise AssertionError('read')
session = MagicMock()
session.capabilities.plain = True
backend = 'cereja.ui.windows.WindowsBackend' if sys.platform == 'win32' else 'cereja.ui.posix.PosixBackend'
with patch.object(sys, 'stdin', TTY()), patch.object(sys.stdout, 'isatty', return_value=True), \
        patch(backend), patch('cereja.ui.terminal.TerminalSession') as terminal, \
        patch('cereja.tui.TUI') as app:
    terminal.return_value.__enter__.return_value = session
    assert main([]) == 0
    app.assert_not_called()
    terminal.return_value.__exit__.assert_called_once()
''')
        self.assertIn('plain reference', output)


if __name__ == '__main__':
    unittest.main()
