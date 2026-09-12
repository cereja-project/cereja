"""Check built archives and the installed wheel outside the source checkout."""

import os
from pathlib import Path
import runpy
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def run(command, cwd):
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    env.pop('PYTHONPATH', None)
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                            text=True, encoding='utf-8', timeout=120)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout


def main():
    wheels = list((ROOT / 'dist').glob('*.whl'))
    sdists = list((ROOT / 'dist').glob('*.tar.gz'))
    if len(wheels) != 1 or len(sdists) != 1:
        raise RuntimeError('Expected exactly one wheel and one sdist in dist/')
    registry = runpy.run_path(str(ROOT / 'cereja' / '_exports.py'))
    required = {name.replace('.', '/') + '/__init__.pyi' for name in registry['EXPORTS']}
    required.add('cereja/py.typed')
    with zipfile.ZipFile(wheels[0]) as archive:
        missing = required - set(archive.namelist())
        if missing:
            raise AssertionError(f'Missing wheel typing files: {sorted(missing)}')
    with tarfile.open(sdists[0], 'r:gz') as archive:
        names = {name.partition('/')[2] for name in archive.getnames()}
        missing = required - names
        if missing:
            raise AssertionError(f'Missing sdist typing files: {sorted(missing)}')
    with tempfile.TemporaryDirectory(prefix='cereja-wheel-check-') as directory:
        target = Path(directory)
        environment = target / 'venv'
        venv.EnvBuilder(with_pip=True).create(environment)
        executable = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        console = environment / ('Scripts/cereja.exe' if os.name == 'nt' else 'bin/cereja')
        run([str(executable), '-m', 'pip', 'install', '--no-index', '--no-deps', str(wheels[0])], target)
        output = run([str(executable), '-I', '-c', '''
import sys
import cereja
loaded = {n for n in sys.modules if n == 'cereja' or n.startswith('cereja.')}
assert loaded == {'cereja', 'cereja._lazy', 'cereja._exports', 'cereja._version'}, loaded
from importlib.metadata import version
from pathlib import Path as NativePath
assert NativePath(cereja.__file__).is_relative_to(sys.prefix)
assert cereja.__version__ == version('cereja')
assert NativePath(cereja.__file__).with_name('__init__.pyi').is_file()
from cereja.system import Path
from cereja.concurrently import TaskList
from cereja.file import FileIO
assert cereja.Path is Path
assert cereja.TaskList is TaskList
assert cereja.FileIO is FileIO
assert Path('.').name
'''], target)
        if output:
            raise AssertionError(f'Installed imports wrote to stdout: {output!r}')
        for command in ([str(executable), '-I', '-m', 'cereja', '--help'],
                        [str(console), '--help'], [str(console), 'security', '--help']):
            output = run(command, target)
            if 'usage:' not in output.lower() or 'Using Cereja' in output:
                raise AssertionError(f'Unexpected CLI help: {output!r}')
    print(f'Validated wheel, sdist, {len(required) - 1} export stubs, isolated imports, and CLI entrypoints.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
