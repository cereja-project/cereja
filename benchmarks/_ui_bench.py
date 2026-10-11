"""Small stdlib reporting helpers for the existing UI benchmarks."""

import gc
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]


def summary(values):
    """Nearest-rank p95; MAD and range describe dispersion, not confidence."""
    ordered = sorted(values)
    center = statistics.median(ordered)
    return {'n': len(ordered), 'median': center,
            'p95': ordered[math.ceil(.95 * len(ordered)) - 1],
            'mad': statistics.median(abs(value - center) for value in ordered),
            'min': ordered[0], 'max': ordered[-1]}


def summaries(samples):
    return {key: summary([sample[key] for sample in samples]) for key in samples[0]
            if type(samples[0][key]) in (int, float)}


def environment():
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()
    sources = sorted((ROOT / 'cereja/ui').glob('*.py'))
    sources += sorted((ROOT / 'benchmarks').glob('*ui*.py'))
    sources += [ROOT / 'benchmarks/imports.py', ROOT / 'tests/ui_scheduling_probe.py',
                ROOT / 'tests/ui_windows_console_probe.py']
    return {'python': sys.version, 'implementation': platform.python_implementation(),
            'platform': platform.platform(), 'machine': platform.machine(),
            'processor': platform.processor(), 'pointer_bits': 64 if sys.maxsize > 2**32 else 32,
            'gc_enabled': gc.isenabled(), 'head': git('rev-parse', 'HEAD'),
            'head_tree': git('rev-parse', 'HEAD^{tree}'), 'dirty': bool(git('status', '--porcelain')),
            'source_sha256': {str(path.relative_to(ROOT)).replace('\\', '/'):
                              hashlib.sha256(path.read_bytes()).hexdigest() for path in sources},
            'execution': 'One benchmark process at a time; affinity/power/background load uncontrolled; '
                         'filesystem/import caches may be OS-warm; no cross-host comparison.'}


def traced(function):
    """Separate untimed window. Live blocks are not cumulative allocations/RSS."""
    gc.collect()
    tracemalloc.start()
    try:
        value = function()
        retained, peak = tracemalloc.get_traced_memory()
        blocks = sum(item.count for item in tracemalloc.take_snapshot().statistics('filename'))
        del value
        return {'retained_bytes': retained, 'peak_bytes': peak, 'live_traced_blocks': blocks}
    finally:
        tracemalloc.stop()


def emit(report, output=None):
    data = json.dumps(report, indent=2, ensure_ascii=True) + '\n'
    if output:
        Path(output).write_text(data, encoding='utf-8')
    else:
        print(data, end='')
