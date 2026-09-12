"""Public import contracts, checked in fresh interpreters to expose order bugs."""

import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ImportContractTest(unittest.TestCase):
    def run_python(self, code):
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=ROOT, env=env,
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_root_exports_are_the_canonical_objects(self):
        self.run_python('''
import importlib
import cereja
pairs = {
    "Path": "cereja.system",
    "FileIO": "cereja.file",
    "Progress": "cereja.display",
    "TaskList": "cereja.concurrently",
    "async_to_sync": "cereja.concurrently",
    "sync_to_async": "cereja.concurrently",
    "Timer": "cereja.utils",
}
for name, module in pairs.items():
    assert getattr(cereja, name) is getattr(importlib.import_module(module), name), name
''')

    def test_stride_alias_preserves_identity(self):
        self.run_python('''
from cereja import stride_values
from cereja.utils import stride_values as package_alias
from cereja.utils._utils import get_batch_strides
assert stride_values is package_alias is get_batch_strides
''')

    def test_unknown_attribute_raises_attribute_error(self):
        self.run_python('''
import cereja
try:
    cereja.__nonexistent_import_contract_attribute__
except AttributeError:
    pass
else:
    raise AssertionError("Unknown exports must raise AttributeError")
''')

    def test_import_orders_preserve_identity(self):
        for first in ("cereja.system._path", "cereja.file", "cereja.concurrently"):
            with self.subTest(first=first):
                self.run_python(f'''
import importlib
importlib.import_module({first!r})
import cereja
from cereja.system import Path
from cereja.file import FileIO
from cereja.concurrently import TaskList
assert cereja.Path is Path
assert cereja.FileIO is FileIO
assert cereja.TaskList is TaskList
''')

    def test_exported_classes_remain_pickleable(self):
        self.run_python('''
import pickle
import cereja
for cls in (cereja.Path, cereja.TaskList):
    assert pickle.loads(pickle.dumps(cls)) is cls
''')

    def test_concurrent_first_access_preserves_identity(self):
        self.run_python('''
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import cereja
barrier = Barrier(8)
def access(_):
    barrier.wait(timeout=10)
    return cereja.Path
with ThreadPoolExecutor(max_workers=8) as executor:
    results = list(executor.map(access, range(8)))
assert all(item is results[0] for item in results)
from cereja.system import Path
assert results[0] is Path
''')

    def test_dir_discovers_representative_exports(self):
        self.run_python('''
import cereja
names = set(dir(cereja))
assert {"Path", "FileIO", "TaskList", "Timer", "utils", "system"} <= names
''')


if __name__ == "__main__":
    unittest.main()
