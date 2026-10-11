"""Reproducible Ledger startup, retention and actual command/render measurements.

No performance gates or human/terminal/RSS claims. Child processes are fresh,
but OS caches are not flushed. Guarded import side effects are tested separately.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _ui_bench import environment, summary, emit


CHILD = '''
import contextlib, io, json, sys, threading, time
started = time.perf_counter_ns()
before = set(threading.enumerate())
with contextlib.redirect_stdout(io.StringIO()) as output:
    {statement}
elapsed = time.perf_counter_ns() - started
print(json.dumps({{'elapsed_ns': elapsed, 'new_threads': len(set(threading.enumerate()) - before),
    'services': [n for n in sys.modules if n.startswith(('cereja.system', 'cereja.http',
        'cereja.hashtools', 'cereja.transfers', 'cereja.display'))],
    'module_count': len(sys.modules), 'output_chars': len(output.getvalue())}}))
'''

CASES = {
    'root_import': 'import cereja',
    'catalogue_import_and_discovery': 'from cereja.ledger.catalogue import COMMANDS, REFERENCES; '
                                      '[entry.description() for entry in COMMANDS + REFERENCES]',
    'application_import': 'from cereja.ledger.app import Ledger',
    'plain_entry': 'from cereja.entrypoint import main; main(["ui", "--plain"])',
    'application_first_frame': 'exec("from cereja.ledger.app import Ledger\\n'
                               'from cereja.ui.terminal import TerminalSession\\n'
                               'from cereja.ui.testing import VirtualBackend\\n'
                               'with TerminalSession(VirtualBackend()) as s:\\n'
                               '    app = Ledger(s)\\n    app.render()\\n    app.close()")',
}


def fresh(case):
    start = time.perf_counter_ns()
    result = subprocess.run([sys.executable, '-B', '-S', '-c', CHILD.format(statement=CASES[case])],
                            cwd=ROOT, capture_output=True, text=True, timeout=20)
    if result.returncode or result.stderr:
        raise RuntimeError(result.stderr or result.stdout)
    value = json.loads(result.stdout)
    value['process_wall_ns'] = time.perf_counter_ns() - start
    if value['new_threads'] or value['services']:
        raise AssertionError(value)
    return value


def retention(payload_size=1024, count=21, **limits):
    from cereja.ledger.model import Results
    results = Results(**limits)
    for i in range(count):
        # Unique text prevents the metrics cache from sharing identical snapshots.
        results.append('/examples', str(i).zfill(4) + 'x' * (payload_size - 4))
    return results


def memory_sample(payload, limits):
    # Each trace gets a fresh metrics cache; do not mix cold and cached samples.
    code = '''
import json, sys
sys.path.insert(0, 'benchmarks')
from ui_ledger import retention
from _ui_bench import traced
from cereja.ledger.model import Results
details = {}
def fixture():
    results = retention(PAYLOAD, **LIMITS)
    details.update(completed=len(results.blocks), omitted=results.omitted,
                   logical_bytes=results.retained_bytes)
    return results
print(json.dumps(dict(raw=traced(fixture), **details)))
'''.replace('PAYLOAD', str(payload)).replace('LIMITS', repr(limits))
    result = subprocess.run([sys.executable, '-B', '-S', '-c', code], cwd=ROOT,
                            capture_output=True, text=True, timeout=180)
    if result.returncode or result.stderr:
        raise RuntimeError(result.stderr or result.stdout)
    return json.loads(result.stdout)


def command_frame(size=(80, 24)):
    from cereja.ui.events import KeyEvent
    from cereja.ui.terminal import TerminalSession
    from cereja.ui.testing import VirtualBackend
    from cereja.ledger.app import Ledger
    backend = VirtualBackend(size=size)
    with TerminalSession(backend) as session:
        app = Ledger(session)
        try:
            app.composer.insert('/tools')
            start = time.perf_counter_ns()
            app.handle(KeyEvent('enter'))
            elapsed = time.perf_counter_ns() - start
            assert app.results.current.command == '/tools'
            return {'handler_and_cellbuffer_ns': elapsed,
                    'retained_payload_bytes': app.results.retained_bytes}
        finally:
            app.close()


def demo(size=(80, 24)):
    from cereja.ui.events import KeyEvent, PasteEvent
    from cereja.ui.terminal import TerminalSession, CapabilityOptions
    from cereja.ui.testing import VirtualBackend
    from cereja.ledger.app import Ledger
    with TerminalSession(VirtualBackend(size=size, options=CapabilityOptions(
            color=0, unicode=False, reduced_motion=True))) as session:
        app = Ledger(session)
        try:
            app.handle(PasteEvent('/ex'))
            app.handle(KeyEvent('enter'))  # insertion only
            app.handle(KeyEvent('enter'))  # form
            frame = app.render()
            return [''.join(cell.text for cell in row) for row in frame.rows]
        finally:
            app.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=int, default=31)
    parser.add_argument('--warmup', type=int, default=3)
    parser.add_argument('--memory-samples', type=int, default=3)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--smoke', action='store_true', help='Omit costly retention stress in CI smoke.')
    args = parser.parse_args()
    if args.demo:
        print('\n'.join(demo()))
        return
    if min(args.samples, args.memory_samples) < 1 or args.warmup < 0:
        parser.error('invalid sample counts')
    env = environment()
    sources = list((ROOT / 'cereja/ledger').glob('*.py')) + [ROOT / 'cereja/commands/ui.py',
               ROOT / 'cereja/commands/registry.py', ROOT / 'cereja/entrypoint.py']
    env['source_sha256'].update({p.relative_to(ROOT).as_posix(): hashlib.sha256(
        p.read_bytes().replace(b'\r\n', b'\n')).hexdigest() for p in sources})
    for path in env['source_sha256']:
        env['source_sha256'][path] = hashlib.sha256((ROOT / path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    env['hash_normalization'] = 'CRLF to LF; comparable to Git text blobs'
    report = {'environment': env, 'warmups': args.warmup, 'startup': {}, 'retention': {}, 'frames': {},
              'limits': 'Fresh child processes, OS caches uncontrolled. Harness imports excluded from timed import. '
                        'Frame window: Enter handler through CellBuffer, excluding scheduler pacing, renderer, '
                        'OS transport and human input. Retention: separate untimed tracemalloc, excluding imports; '
                        'includes Unicode metrics/cache effects in a fresh child per trace. '
                        'No RSS or whole-process memory claim.'}
    for case in CASES:
        for _ in range(args.warmup):
            fresh(case)
        raw = [fresh(case) for _ in range(args.samples)]
        report['startup'][case] = {'raw': raw, 'import_ns': summary([x['elapsed_ns'] for x in raw]),
                                 'process_wall_ns': summary([x['process_wall_ns'] for x in raw])}
    retention_cases = (
            ('small_20', 1024, {}),
            ('candidate_20x64KiB', 65536, {'max_bytes': 2097152, 'block_bytes': 65536}),
            ('bounded_20x16KiB_256KiB', 16384, {'max_bytes': 262144, 'block_bytes': 16384}))
    for name, payload, limits in retention_cases[:1] if args.smoke else retention_cases:
        measurements = [memory_sample(payload, limits) for _ in range(args.memory_samples)]
        memory = [item['raw'] for item in measurements]
        report['retention'][name] = {'raw': memory, 'summary': {
            key: summary([x[key] for x in memory]) for key in memory[0]},
            **{key: measurements[0][key] for key in ('completed', 'omitted', 'logical_bytes')}}
    for size in ((120, 40), (80, 24), (40, 12)):
        for _ in range(args.warmup):
            command_frame(size)
        raw = [command_frame(size) for _ in range(args.samples)]
        report['frames']['x'.join(map(str, size))] = {
            'raw': raw, 'handler_ns': summary([x['handler_and_cellbuffer_ns'] for x in raw])}
    report['virtual_keyboard_snapshots'] = {'x'.join(map(str, size)): demo(size)
        for size in ((120, 40), (80, 24), (40, 12))}
    emit(report, args.output)


if __name__ == '__main__':
    main()
