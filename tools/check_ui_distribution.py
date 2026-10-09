"""Build and install wheel/sdist offline in owned, empty temporary environments.

Requires Git, pip, setuptools and wheel on the build interpreter only. Export
the selected Git tree into a temporary build directory; never build in-place.
The installed interpreter has no pip/setuptools or runtime dependency added.
"""

import argparse
from hashlib import sha256
import io
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import tempfile
import venv


ROOT = Path(__file__).resolve().parents[1]
PROBE = r'''
import ctypes, hashlib, importlib.metadata as metadata, json, os
from pathlib import Path
import selectors, signal, subprocess, sys, threading
from contextlib import ExitStack
from unittest.mock import patch
expected = json.loads(sys.argv[1])
assert sorted(d.metadata['Name'].lower() for d in metadata.distributions()) == ['cereja']
dist = metadata.distribution('cereja')
assert not dist.requires, dist.requires
assert dist.metadata['Requires-Python'] == '>=3.11'
before = set(threading.enumerate())
targets = [(threading.Thread, 'start'), (signal, 'signal'),
           (subprocess, 'Popen'), (os, 'open'), (selectors, 'DefaultSelector')]
if os.name == 'posix':
    import termios
    targets.append((termios, 'tcsetattr'))
if os.name == 'nt':
    targets.append((ctypes, 'WinDLL'))
with ExitStack() as stack:
    for owner, name in targets:
        stack.enter_context(patch.object(owner, name,
                            side_effect=AssertionError('import acquired ' + name)))
    import cereja
    assert not any(n.startswith('cereja.ui') for n in sys.modules)
    import cereja.ui
    assert not any(n.startswith('cereja.ui.') for n in sys.modules)
    from cereja.ui import terminal, text, buffer, rendering, scheduling, testing, events
    from cereja.ui import posix, windows
assert set(threading.enumerate()) == before
assert 'cereja.display' not in sys.modules and 'cereja.system' not in sys.modules
assert 'unicodedata' not in sys.modules
package = Path(cereja.__file__).resolve().parent
assert Path(sys.prefix).resolve() in package.parents, package
for name, fingerprint in expected.items():
    assert hashlib.sha256((package / 'ui' / name).read_bytes()).hexdigest() == fingerprint, name
assert text.UNICODE_VERSION == '17.0.0'
assert text.text_metrics('e\u0301\U0001f600').line_widths() == (3,)
backend = testing.VirtualBackend(size=(8, 2))
with terminal.TerminalSession(backend) as session:
    renderer = rendering.Renderer(session, verify_damage=True)
    frame = buffer.CellBuffer(8, 2)
    frame.draw_text(0, 0, '界 done')
    assert renderer.render(frame, cursor=rendering.Cursor(2, 1, True))
    counts = session.write_count, session.flush_count
    assert renderer.render(frame.copy(), damage=[], cursor=rendering.Cursor(2, 1, True))
    assert (session.write_count, session.flush_count) == counts
    seen = []
    loop = scheduling.EventLoop(session, seen.append, clock=backend.clock)
    request = loop.begin_request('example')
    event = events.ResultEvent('example', request.generation, 'complete')
    assert loop.post(event)
    loop.turn()
    assert seen == [event]
    loop.close()
print(json.dumps({'installed_only': ['cereja'], 'requires_dist': [],
    'unicode_version': text.UNICODE_VERSION, 'imports_silent_and_guarded': True,
    'legacy_isolated': True, 'examples_passed': True,
    'unicode_hashes': expected}, sort_keys=True))
'''


def run(args, *, cwd, binary=False):
    completed = subprocess.run(args, cwd=cwd, capture_output=True,
                               text=not binary, timeout=120,
                               env={**os.environ, 'PYTHONIOENCODING': 'utf-8',
                                    'PYTHONDONTWRITEBYTECODE': '1'})
    if completed.returncode:
        raise RuntimeError(f'{args[0]} failed ({completed.returncode}): '
                           f'{completed.stdout!r} {completed.stderr!r}')
    return completed


def export_tree(revision, destination):
    archive = run(['git', 'archive', '--format=tar', revision], cwd=ROOT, binary=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        for member in source:
            target = (destination / member.name).resolve()
            if destination.resolve() not in target.parents:
                raise ValueError('archive member escapes owned temporary source')
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.extractfile(member).read())
            else:
                raise ValueError(f'unsupported archive member: {member.name}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', default='HEAD', help='Git commit/tree exported for builds')
    parser.add_argument('--output', type=Path, help='New report file (never overwritten)')
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        parser.error('output already exists; use a new owned report path')
    tree = run(['git', 'rev-parse', f'{args.revision}^{{tree}}'], cwd=ROOT).stdout.strip()
    report = {'source_tree': tree, 'python': sys.version, 'platform': platform.platform(),
              'build_tools_only': {name: version(name) for name in ('pip', 'setuptools', 'wheel')},
              'installs': {}}
    with tempfile.TemporaryDirectory(prefix='cereja-ui-dist-') as directory:
        owned = Path(directory)
        source = owned / 'source'
        source.mkdir()
        export_tree(tree, source)
        expected = {name: sha256((source / 'cereja' / 'ui' / name).read_bytes()).hexdigest()
                    for name in ('_unicode17.py', 'UNICODE-LICENSE.txt')}
        run([sys.executable, '-B', '-c', 'from setuptools import build_meta as b; '
             'b.build_sdist("dist"); b.build_wheel("dist")'], cwd=source)
        wheel = next((source / 'dist').glob('*.whl'))
        sdist = next((source / 'dist').glob('*.tar.gz'))
        with tarfile.open(sdist) as archive:
            names = archive.getnames()
            for suffix in ('tools/generate_ui_unicode.py', 'tools/unicode/17.0.0/manifest.json',
                           'tools/unicode/17.0.0/LICENSE.txt'):
                if not any(name.endswith('/' + suffix) for name in names):
                    raise AssertionError(f'sdist missing {suffix}')
            manifest = json.loads((source / 'tools/unicode/17.0.0/manifest.json').read_text('utf-8'))
            for name, entry in manifest['sources'].items():
                member = next(n for n in names if n.endswith('/tools/unicode/17.0.0/' + name))
                if sha256(archive.extractfile(member).read()).hexdigest() != entry['sha256']:
                    raise AssertionError(f'sdist Unicode source changed: {name}')
        rebuilt = owned / 'sdist-wheel'
        rebuilt.mkdir()
        run([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-index',
             '--no-build-isolation', '--wheel-dir', str(rebuilt), str(sdist)], cwd=owned)
        for kind, artifact, install_wheel in (
                ('wheel', wheel, wheel), ('sdist', sdist, next(rebuilt.glob('*.whl')))):
            environment = owned / kind
            venv.EnvBuilder(with_pip=False).create(environment)
            executable = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
            run([sys.executable, '-m', 'pip', '--python', str(executable), 'install',
                 '--no-deps', '--no-index', str(install_wheel)], cwd=owned)
            completed = run([str(executable), '-I', '-B', '-c', PROBE,
                             json.dumps(expected)], cwd=owned)
            if completed.stderr:
                raise AssertionError(f'installed probe stderr: {completed.stderr}')
            report['installs'][kind] = {'artifact': artifact.name,
                'artifact_sha256': sha256(artifact.read_bytes()).hexdigest(),
                'probe': json.loads(completed.stdout)}
    encoded = json.dumps(report, indent=2, sort_keys=True) + '\n'
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(encoded)
    print(encoded, end='')


if __name__ == '__main__':
    main()
