"""Behavioral isolation requirements for the lazy public import facade."""

import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
MINIMAL = {"cereja", "cereja._exports", "cereja._lazy", "cereja._version"}


class LazyImportsTest(unittest.TestCase):
    def run_python(self, code):
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=ROOT,
            env=dict(os.environ, PYTHONPATH=str(ROOT)),
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_root_loads_only_bootstrap_modules(self):
        result = self.run_python(f'''
import sys
import cereja
loaded = {{n for n in sys.modules if n == "cereja" or n.startswith("cereja.")}}
assert loaded <= {MINIMAL!r}, sorted(loaded - {MINIMAL!r})
''')
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_dir_does_not_resolve_exports(self):
        self.run_python('''
import sys
import cereja
before = set(sys.modules)
assert {"Path", "FileIO", "TaskList", "console", "utils"} <= set(dir(cereja))
assert set(sys.modules) == before
assert "Path" not in vars(cereja)
''')

    def test_package_imports_do_not_load_implementations(self):
        packages = (
            "utils", "system", "concurrently", "array", "file", "mltools",
            "hashtools", "geolinear", "display", "date", "mathtools",
        )
        for package in packages:
            with self.subTest(package=package):
                allowed = MINIMAL | {"cereja." + package}
                self.run_python(f'''
import sys
from importlib import import_module
import_module({"cereja." + package!r})
loaded = {{n for n in sys.modules if n == "cereja" or n.startswith("cereja.")}}
assert loaded <= {allowed!r}, sorted(loaded - {allowed!r})
''')

    def test_path_does_not_load_unrelated_domains(self):
        self.run_python('''
import sys
from cereja.system import Path
assert Path(".").name
for prefix in ("cereja.mltools", "cereja._requests", "cereja.scraping",
               "cereja.display", "cereja.file", "cereja.system._context"):
    assert not any(n == prefix or n.startswith(prefix + ".") for n in sys.modules), prefix
''')

    def test_tasklist_does_not_load_process_workers(self):
        self.run_python('''
import sys
from cereja.concurrently import TaskList
assert TaskList.__name__ == "TaskList"
for prefix in ("cereja.concurrently.process", "cereja.mltools", "cereja.file",
               "cereja.display", "cereja._requests", "cereja.system"):
    assert not any(n == prefix or n.startswith(prefix + ".") for n in sys.modules), prefix
''')

    def test_version_metadata_does_not_load_utils(self):
        self.run_python('''
import sys
from cereja import VERSION, __version__
assert VERSION == "2.1.6.final.0"
assert __version__ == "2.1.6"
assert "cereja.utils" not in sys.modules
''')

    def test_banner_remains_an_explicit_operation(self):
        result = self.run_python('''
import cereja
assert cereja.print_cereja_version() is True
''')
        self.assertEqual(result.stdout.count("Using Cereja"), 1)

    def test_terminal_capability_probe_does_not_print(self):
        result = self.run_python('''
import cereja
assert isinstance(cereja.NON_BMP_SUPPORTED, bool)
''')
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
