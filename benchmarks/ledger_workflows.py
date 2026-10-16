"""Owned-fixture domain/UI calibration; no private inventory or network services."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import tempfile
import time
import tracemalloc

from cereja.ledger.app import Ledger
from cereja.ui.events import KeyEvent
from cereja.ui.terminal import TerminalSession
from cereja.ui.testing import VirtualBackend


def summary(rows):
    values = sorted(row['milliseconds'] for row in rows)
    median = statistics.median(values)
    return dict(median_ms=median, p95_ms=values[math.ceil(.95 * len(values)) - 1],
                mad_ms=statistics.median(abs(v - median) for v in values),
                min_ms=min(values), max_ms=max(values), samples=rows)


def measure(samples=11, warmup=3):
    result = {}
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / 'source'
        source.mkdir()
        (source / 'empty').mkdir()
        (source / 'data.txt').write_text('needle fixture\n' * 4000, encoding='utf-8')
        for name in ('tree', 'context', 'compress', 'decompress', 'directory'):
            rows = []
            for sample in range(samples + warmup):
                destination = root / ('result-' + name + '-' + str(sample))
                tracemalloc.start()
                with TerminalSession(VirtualBackend()) as session:
                    app = Ledger(session)
                    try:
                        started = time.perf_counter_ns()
                        if name == 'tree':
                            app._tree(str(source), 3)
                        elif name == 'context':
                            app._workflow('context', dict(root=str(source), query='needle'))
                        else:
                            mode = 'directory' if name == 'directory' else 'file'
                            path = source if mode == 'directory' else source / 'data.txt'
                            action = 'compress'
                            if name == 'decompress':
                                from cereja.hashtools.archive import file_archive
                                path = root / ('input-' + str(sample))
                                file_archive(source / 'data.txt', path)
                                action = 'decompress'
                                started = time.perf_counter_ns()
                            app._workflow('compress', dict(action=action, mode=mode,
                                                         source=str(path), destination=str(destination)))
                        inputs = []
                        deadline = time.monotonic() + 10
                        while app.bridge.active:
                            if time.monotonic() > deadline:
                                raise RuntimeError('Benchmark observation timeout; worker is not claimed stopped')
                            app.loop.turn()
                            start_input = time.perf_counter_ns()
                            app.handle(KeyEvent('left'))
                            inputs.append((time.perf_counter_ns() - start_input) / 1e6)
                            app.refresh()
                            time.sleep(.001)
                        elapsed = (time.perf_counter_ns() - started) / 1e6
                        if app.results.current.state != 'Succeeded':
                            raise RuntimeError('Benchmark operation failed: ' + app.results.current.content.text)
                        _, peak = tracemalloc.get_traced_memory()
                        if sample >= warmup:
                            rows.append(dict(milliseconds=elapsed, traced_peak_bytes=peak,
                                             input_ms=inputs, retained_bytes=app.results.retained_bytes))
                    finally:
                        app.close()
                        tracemalloc.stop()
            result[name] = summary(rows)
    files = ('cereja/system/repository.py', 'cereja/hashtools/archive.py',
             'cereja/ledger/app.py', 'cereja/ledger/tree.py', 'cereja/ledger/workflows.py')
    return dict(schema_version=1, python=platform.python_version(), platform=sys.platform,
                samples=samples, warmup=warmup, scenarios=result,
                fingerprints={p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in files},
                limitations='Owned stable fixtures; scheduler/CellBuffer plus memory sink; 1ms harness waits. '
                'Traced allocation is not RSS. No real terminal presentation/human latency. OS cache/load uncontrolled. '
                'Context has no hard scan bound under concurrent source mutation. No performance improvement claim.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--samples', type=int, default=11)
    parser.add_argument('--warmup', type=int, default=3)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.samples < 1 or args.warmup < 0:
        parser.error('positive samples and nonnegative warmup required')
    report = measure(args.samples, args.warmup)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({name: {k: v for k, v in stats.items() if k != 'samples'}
                      for name, stats in report['scenarios'].items()}, indent=2))
