"""Check built archives and the installed wheel outside the source checkout."""

import argparse
import hashlib
import json
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist-dir', type=Path, default=ROOT / 'dist')
    args = parser.parse_args(argv)
    wheels = list(args.dist_dir.glob('*.whl'))
    sdists = list(args.dist_dir.glob('*.tar.gz'))
    if len(wheels) != 1 or len(sdists) != 1:
        raise RuntimeError('Expected exactly one wheel and one sdist in dist/')
    registry = runpy.run_path(str(ROOT / 'cereja' / '_exports.py'))
    required = {name.replace('.', '/') + '/__init__.pyi' for name in registry['EXPORTS']}
    required.add('cereja/py.typed')
    required.update({'cereja/ui/buffer.py', 'cereja/ui/text.py', 'cereja/ui/_unicode17.py',
                     'cereja/ui/UNICODE-LICENSE.txt'})
    with zipfile.ZipFile(wheels[0]) as archive:
        missing = required - set(archive.namelist())
        if missing:
            raise AssertionError(f'Missing wheel typing files: {sorted(missing)}')
        wheel_notice = archive.read('cereja/ui/UNICODE-LICENSE.txt')
    with tarfile.open(sdists[0], 'r:gz') as archive:
        members = {member.name.partition('/')[2]: member for member in archive.getmembers()}
        sources_root = 'tools/unicode/17.0.0/'
        source_files = {'tools/generate_ui_unicode.py', sources_root + 'manifest.json',
                        'docs/guides/ui-text.md', 'docs/guides/ui-buffer.md', 'benchmarks/ui_buffers.py'}
        missing = (required | source_files) - members.keys()
        if missing:
            raise AssertionError(f'Missing sdist artifacts: {sorted(missing)}')
        manifest = json.load(archive.extractfile(members[sources_root + 'manifest.json']))
        for name, source in manifest['sources'].items():
            member = members.get(sources_root + name)
            if member is None or hashlib.sha256(archive.extractfile(member).read()).hexdigest() != source['sha256']:
                raise AssertionError(f'Missing or altered sdist Unicode input: {name}')
        if hashlib.sha256(wheel_notice).hexdigest() != manifest['sources']['LICENSE.txt']['sha256']:
            raise AssertionError('Wheel Unicode license differs from the pinned notice')
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
        output = run([str(executable), '-I', '-c', '''
import sys
from pathlib import Path
from cereja.ui import text
from cereja.ui.buffer import CellBuffer, Layer, compose
assert Path(text.__file__).is_relative_to(sys.prefix)
assert text.text_metrics('e\\u0301\\U0001f6d8').line_widths() == (3,)
assert text.UNICODE_VERSION == '17.0.0'
assert 'UNICODE LICENSE V3' in Path(text.__file__).with_name('UNICODE-LICENSE.txt').read_text(encoding='utf-8')
source = CellBuffer(2, 1)
source.draw_text(0, 0, '\\u754c')
overlay = CellBuffer(1, 1)
overlay.draw_text(0, 0, 'x')
frame = compose(2, 1, [Layer(source), Layer(overlay, x=1, z=1)])
assert [(cell.text, cell.width) for cell in frame.rows[0]] == [(' ', 1), ('x', 1)]
assert 'cereja.display' not in sys.modules
assert 'cereja.system' not in sys.modules
assert 'unicodedata' not in sys.modules
'''], target)
        if output:
            raise AssertionError(f'Installed UI metrics wrote to stdout: {output!r}')
        for command in ([str(executable), '-I', '-m', 'cereja', '--help'],
                        [str(console), '--help'], [str(console), 'security', '--help']):
            output = run(command, target)
            if 'usage:' not in output.lower() or 'Using Cereja' in output:
                raise AssertionError(f'Unexpected CLI help: {output!r}')
    print(f'Validated wheel, sdist, {len(registry["EXPORTS"])} export stubs, Unicode data/license, isolated imports, and CLI entrypoints.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
