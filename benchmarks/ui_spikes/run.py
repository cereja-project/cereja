"""Run from repository root: python benchmarks/ui_spikes/run.py --output FILE."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
import tracemalloc
import unicodedata

from model import Frame, diff, encode

ROOT = Path(__file__).resolve().parents[2]


def measure(call, repetitions=31):
    for _ in range(5):
        call()
    samples = []
    for _ in range(repetitions):
        start = time.perf_counter_ns()
        call()
        samples.append(time.perf_counter_ns() - start)
    tracemalloc.start()
    call()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {'samples_ns': samples, 'median_ns': statistics.median(samples),
            'p95_ns': sorted(samples)[int(len(samples) * .95)], 'peak_traced_bytes': peak}


def run():
    report = {'schema': 1, 'python': platform.python_version(), 'os': platform.system(),
              'os_release': platform.release(), 'machine': platform.machine(),
              'unicode_version': unicodedata.unidata_version,
              'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'warmup': 5, 'repetitions': 31, 'encoding': 'utf-8',
              'transport': 'memory only', 'stdin_tty': sys.stdin.isatty(),
              'stdout_tty': sys.stdout.isatty(),
              'sources_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in Path(__file__).parent.glob('*.py')}, 'render': []}
    for width, height in [(80, 24), (120, 40), (240, 80)]:
        for name, count in [('unchanged', 0), ('one_cell', 1), ('one_row', width),
                            ('ten_percent', width * height // 10), ('all', width * height)]:
            old = Frame(width, height)
            new = old.clone()
            for i in range(count):
                new.put(i % width, i // width, 'x')
            baseline = diff(old, new)
            assert baseline == diff(old, new, True)
            payload = encode(baseline, width)
            report['render'].append({'width': width, 'height': height, 'case': name,
                'changed_cells': len(baseline), 'encoded_bytes': len(payload),
                'planned_stream_write_calls': int(bool(payload)),
                'full_diff': measure(lambda: diff(old, new)),
                'dirty_diff': measure(lambda: diff(old, new, True)),
                'encoding': measure(lambda: encode(baseline, width)),
                'full_diff_encode': measure(lambda: encode(diff(old, new), width)),
                'dirty_diff_encode': measure(lambda: encode(diff(old, new, True), width))})
    probe = """
import contextlib, io, sys, threading, time, json
out, err = io.StringIO(), io.StringIO()
before = len(threading.enumerate())
with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
    start = time.perf_counter_ns()
    import cereja
    elapsed = time.perf_counter_ns() - start
print(json.dumps({'elapsed_ns': elapsed, 'stdout': out.getvalue(), 'stderr': err.getvalue(),
                  'threads_added': len(threading.enumerate()) - before,
                  'ui_modules': [n for n in sys.modules if n.startswith('cereja.ui')]}))
"""
    report['fresh_import_cereja'] = [json.loads(subprocess.check_output(
        [sys.executable, '-c', probe], cwd=ROOT, text=True)) for _ in range(9)]
    report['fresh_import_cereja_ui'] = {'status': 'not available; production module not created'}
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(run(), indent=2) + '\n', encoding='utf-8')
