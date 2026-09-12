"""The optional inventory must resolve lazy exports, not just cached names."""

import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ImportBenchmarkTest(unittest.TestCase):
    def test_inventory_includes_unresolved_exports(self):
        benchmark = runpy.run_path(str(ROOT / 'benchmarks' / 'imports.py'))
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / 'cereja'
            package.mkdir()
            (package / '__init__.py').write_text('''
__all__ = ["Example"]
def __dir__():
    return ["Example"]
def __getattr__(name):
    if name == "Example":
        from .implementation import Example
        return Example
    raise AttributeError(name)
''', encoding='utf-8')
            (package / 'implementation.py').write_text(
                'class Example:\n    pass\n', encoding='utf-8'
            )
            result = subprocess.run(
                [sys.executable, '-c', benchmark['INVENTORY']], cwd=directory,
                env=dict(os.environ, PYTHONPATH=directory, PYTHONIOENCODING='utf-8'),
                capture_output=True, text=True, encoding='utf-8', timeout=30,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        reports = [json.loads(line) for line in result.stdout.splitlines()]
        root = next(report for report in reports if report['package'] == 'cereja')
        self.assertIn('Example', root['exports'])
        self.assertEqual(root['exports']['Example']['target'], ['cereja.implementation', 'Example'])


if __name__ == '__main__':
    unittest.main()
