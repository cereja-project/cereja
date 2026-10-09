"""Reproducible retained/peak Python allocations for cell storage, not UI speed.

Run from the checkout with: python -B -S benchmarks/ui_buffers.py --samples 5
Imports and shared text/style caches are warmed before each tracing window.
"""

import argparse
import gc
import json
from pathlib import Path
import platform
from statistics import median
import sys
import tracemalloc


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cereja.ui.buffer import CellBuffer  # noqa: E402
from cereja.ui.text import text_metrics  # noqa: E402


def allocate(width, height, workload):
    frame = CellBuffer(width, height)
    if workload == 'two_blank_frames':
        return frame, CellBuffer(width, height)
    if workload == 'dense_ascii':
        for y in range(height):
            frame.draw_text(0, y, 'x' * width)
    return frame


def measure(width, height, workload, samples):
    text_metrics('x' * width)
    allocate(width, height, workload)
    retained, peak = [], []
    for _ in range(samples):
        gc.collect()
        tracemalloc.start()
        frame = allocate(width, height, workload)
        current_bytes, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        retained.append(current_bytes)
        peak.append(peak_bytes)
        del frame
    return {'retained_bytes': median(retained), 'peak_bytes': median(peak)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=int, default=5)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error('--samples must be positive')
    results = []
    for width, height in ((80, 24), (120, 40), (240, 80)):
        for workload in ('blank', 'two_blank_frames', 'dense_ascii'):
            results.append({'width': width, 'height': height, 'workload': workload,
                            **measure(width, height, workload, args.samples)})
    print(json.dumps({'python': sys.version, 'platform': platform.platform(),
                      'pointer_bits': 64 if sys.maxsize > 2 ** 32 else 32,
                      'samples': args.samples, 'measurement': 'median traced Python bytes',
                      'cache_state': 'warm imports and shared metrics/style caches',
                      'results': results}, indent=2))


if __name__ == '__main__':
    main()
