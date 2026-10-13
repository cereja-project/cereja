"""Native Windows Ledger entry, paste/copy/exit and acquisition restoration."""
import json
import os
from pathlib import Path
import unittest


@unittest.skipUnless(os.name == 'nt', 'Windows ConPTY required')
class LedgerWindowsNativeTest(unittest.TestCase):
    def test_conpty_official_entry_paste_copy_exit_and_restore(self):
        if __package__:
            from .ui_windows_conpty_probe import probe
        else:
            # Discovery with -s tests imports this file as a top-level module;
            # tests/tests.py can then shadow the tests package.
            from ui_windows_conpty_probe import probe
        report = probe()
        self.assertTrue(report['modes_restored'])
        self.assertFalse(report['human_clipboard_checked'])
        directory = os.environ.get('CEREJA_UI_EVIDENCE_DIR')
        if directory:
            destination = Path(directory)
            destination.mkdir(parents=True, exist_ok=True)
            (destination / 'windows-ledger-conpty.json').write_text(
                json.dumps(report, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
