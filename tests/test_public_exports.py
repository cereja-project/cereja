"""Frozen names observed on the eager baseline; never derive them from the map."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests' / 'fixtures' / 'public_exports.json'


def run_python(code):
    result = subprocess.run(
        [sys.executable, '-c', code], cwd=ROOT,
        env=dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING='utf-8'),
        capture_output=True, text=True, encoding='utf-8', timeout=60,
    )
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return result


class PublicExportsTest(unittest.TestCase):
    def test_frozen_exports_resolve_in_both_orders(self):
        fixture = json.loads(FIXTURE.read_text(encoding='utf-8'))
        for package, names in fixture['packages'].items():
            expected = set(names.split())
            if sys.platform == 'win32' and package in ('cereja', 'cereja.system'):
                expected.update(fixture['windows_names'].split())
            for reverse in (False, True):
                with self.subTest(package=package, reverse=reverse):
                    run_python(f'''
import importlib
import cereja
module = importlib.import_module({package!r})
expected = {expected!r}
actual = {{n for n in dir(module) if not n.startswith('_')}}
assert actual == expected, (sorted(expected - actual), sorted(actual - expected))
for name in sorted(expected, reverse={reverse!r}):
    obj = getattr(module, name)
    assert getattr(module, name) is obj, name
    owner = getattr(obj, '__module__', None)
    original_name = getattr(obj, '__name__', None)
    if owner and original_name and owner.startswith('cereja'):
        original_module = importlib.import_module(owner)
        assert getattr(original_module, original_name) is obj, (name, owner)
''')

    def test_star_imports_keep_the_frozen_surface(self):
        fixture = json.loads(FIXTURE.read_text(encoding='utf-8'))
        for package, names in fixture['packages'].items():
            expected = set(fixture['star_overrides'].get(package, names).split())
            if sys.platform == 'win32' and package in ('cereja', 'cereja.system'):
                expected.update(fixture['windows_names'].split())
            with self.subTest(package=package):
                run_python(f'''
import cereja
namespace = {{}}
exec('from {package} import *', namespace)
actual = {{n for n in namespace if not n.startswith('_')}}
assert actual == {expected!r}, actual ^ {expected!r}
''')

    def test_every_root_reexport_is_the_package_object(self):
        run_python('''
import importlib
import json
from pathlib import Path
import cereja
fixture = json.loads(Path('tests/fixtures/public_exports.json').read_text())
for package in 'utils display file array system concurrently mltools date hashtools mathtools'.split():
    full_name = 'cereja.' + package
    module = importlib.import_module(full_name)
    for name in fixture['packages'][full_name].split():
        assert getattr(cereja, name) is getattr(module, name), (package, name)
''')

    def test_release_metadata_agrees_with_public_formatter(self):
        run_python('''
from cereja import VERSION, __version__
from cereja.utils.version import get_version_pep440_compliant
assert get_version_pep440_compliant(VERSION) == __version__
''')


if __name__ == '__main__':
    unittest.main()
