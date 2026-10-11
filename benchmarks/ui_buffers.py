"""Real cell storage, text cache and resize baselines; traced memory is not RSS.

python -B -S benchmarks/ui_buffers.py --samples 31 --memory-samples 7
"""
import argparse
from pathlib import Path
import sys
from time import perf_counter_ns

from _ui_bench import emit, environment, summaries, traced

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cereja.ui.buffer import CellBuffer, Style  # noqa: E402
from cereja.ui import text  # noqa: E402

DIMENSIONS = ((80, 24), (120, 40), (240, 80))
UNICODE = 'Ledger e\u0301 \u754c \U0001f469\u200d\U0001f4bb '
WORKLOADS = ('blank', 'two_blank_frames', 'dense_ascii', 'dense_unicode_styles',
             'resize_grow', 'resize_shrink')
LONG_INPUT = False


def allocate(width, height, workload):
    frame = CellBuffer(width, height)
    if workload == 'two_blank_frames':
        return frame, CellBuffer(width, height)
    if workload in ('dense_ascii', 'dense_unicode_styles') or workload.startswith('resize_'):
        unicode = workload != 'dense_ascii'
        repeats = width if LONG_INPUT else (width + text.text_metrics(UNICODE).line_widths()[0] - 1) // text.text_metrics(UNICODE).line_widths()[0]
        row = text.text_metrics(UNICODE * repeats).clip(width) if unicode else 'x' * width
        for y in range(height):
            frame.draw_text(0, y, row, style=Style((40, 140, 200), bold=bool(y % 2)) if unicode else Style())
    if workload.startswith('resize_'):
        delta = 1 if workload == 'resize_grow' else -1
        return frame, frame.resized(width + 8 * delta, height + 2 * delta)
    return frame


def timed(function):
    start = perf_counter_ns()
    value = function()
    elapsed = perf_counter_ns() - start
    del value
    return {'elapsed_ns': elapsed}


def main():
    global LONG_INPUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=int, default=31)
    parser.add_argument('--memory-samples', type=int, default=7)
    parser.add_argument('--warmup', type=int, default=3)
    parser.add_argument('--output')
    parser.add_argument('--long-input', action='store_true', help='Reproduce preliminary overlong input stress')
    args = parser.parse_args()
    LONG_INPUT = args.long_input
    if min(args.samples, args.memory_samples, args.warmup) < 1:
        parser.error('samples and warmup must be positive')
    report = {'environment': environment(),
              'conditions': {'dimensions': DIMENSIONS, 'samples': args.samples,
                             'memory_samples': args.memory_samples, 'warmup': args.warmup,
                             'seed': None, 'text': UNICODE, 'workloads': WORKLOADS, 'long_input': LONG_INPUT,
                             'window': 'Allocation/draw/resize function, warm imports/metrics/styles; '
                                       'GC enabled; timing separate from tracemalloc.',
                             'resize': 'Dense Unicode source and result alive together; +/-8 columns, +/-2 rows.',
                             'memory': 'Retained and peak traced Python bytes and live traced blocks while frames '
                                       'are alive; not RSS, total allocation churn or logical payload budgets.',
                             'text_window': '512-code-point fixed source, cold shared metrics cache cleared before '
                                            'each window; warm cache primed before each window. No process restart.',
                             'limits': 'No composition/rendering/I/O/application; fixed styles and repeated rows.'},
              'results': [], 'text_results': []}
    for width, height in DIMENSIONS:
        for workload in WORKLOADS:
            operation = lambda: allocate(width, height, workload)
            for _ in range(args.warmup):
                operation()
            raw = [timed(operation) for _ in range(args.samples)]
            memory = [traced(operation) for _ in range(args.memory_samples)]
            report['results'].append({'width': width, 'height': height, 'workload': workload,
                                      'raw': raw, 'summary': summaries(raw),
                                      'memory_raw': memory, 'memory_summary': summaries(memory)})
    for profile, source in (('ascii', 'Ledger result ' * 40), ('unicode', UNICODE * 40)):
        source = source[:512]
        for cache in ('cold', 'warm'):
            raw, memory = [], []
            for _ in range(args.warmup + args.samples):
                text._cached_metrics.cache_clear()
                if cache == 'warm':
                    text.text_metrics(source)
                raw.append(timed(lambda: text.text_metrics(source)))
            raw = raw[args.warmup:]
            for _ in range(args.memory_samples):
                text._cached_metrics.cache_clear()
                if cache == 'warm':
                    text.text_metrics(source)
                memory.append(traced(lambda: text.text_metrics(source)))
            report['text_results'].append({'profile': profile, 'cache': cache, 'source': source,
                                           'code_points': len(source), 'raw': raw,
                                           'summary': summaries(raw), 'memory_raw': memory,
                                           'memory_summary': summaries(memory)})
    emit(report, args.output)


if __name__ == '__main__':
    main()
