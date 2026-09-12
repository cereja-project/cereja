"""The checked-in static API must match the lazy runtime registry."""

from pathlib import Path
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ExportStubsTest(unittest.TestCase):
    def test_stubs_are_current(self):
        generator = runpy.run_path(str(ROOT / 'tools' / 'generate_export_stubs.py'))
        self.assertEqual(generator['main'](['--check']), 0)


if __name__ == '__main__':
    unittest.main()
