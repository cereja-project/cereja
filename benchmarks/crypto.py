"""Compare current crypto primitives with the historical implementation.

Run: python benchmarks/crypto.py --samples 7
Measurements exclude file I/O. Memory is Python allocations, not process RSS.
No thresholds are imposed on CI; ciphertext is not printed.
"""
import argparse
import gc
import hashlib
import hmac
import json
from pathlib import Path
import platform
import statistics
import sys
import time
import tracemalloc
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cereja.hashtools import _crypto as crypto  # noqa: E402


def baseline_xor(a, b):
    return bytes(x ^ y for x, y in zip(a, b))


def baseline_stream(key, iv, length):
    chunks = []
    counter = 0
    remaining = length
    while remaining > 0:
        digest = hmac.new(key, iv + counter.to_bytes(4, 'big'), hashlib.sha256).digest()
        chunks.append(digest)
        remaining -= len(digest)
        counter += 1
    return b''.join(chunks)[:length]


def peak_bytes(operation):
    gc.collect()
    tracemalloc.start()
    try:
        result = operation()
        peak = tracemalloc.get_traced_memory()[1]
        del result
        return peak
    finally:
        tracemalloc.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=int, default=7)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error('--samples must be positive')
    variants = {
        'baseline': (baseline_stream, baseline_xor),
        'optimized': (crypto._generate_keystream, crypto._xor_bytes),
    }
    report = {'python': platform.python_version(), 'platform': platform.system(),
              'samples': args.samples, 'measurements': []}
    for size in (1024, 1048576, 8388608):
        data = b'x' * size
        timings = {name: {'encrypt': [], 'decrypt': []} for name in variants}
        # Warm both paths outside the timed samples.
        for stream, xor in variants.values():
            with patch.object(crypto, '_generate_keystream', stream), patch.object(crypto, '_xor_bytes', xor):
                assert crypto.decrypt(crypto.encrypt(data, 'benchmark'), 'benchmark') == data
        for iteration in range(args.samples):
            order = list(variants) if iteration % 2 == 0 else list(reversed(variants))
            for name in order:
                stream, xor = variants[name]
                with patch.object(crypto, '_generate_keystream', stream), patch.object(crypto, '_xor_bytes', xor):
                    start = time.perf_counter()
                    encrypted = crypto.encrypt(data, 'benchmark')
                    timings[name]['encrypt'].append((time.perf_counter() - start) * 1000)
                    start = time.perf_counter()
                    restored = crypto.decrypt(encrypted, 'benchmark')
                    timings[name]['decrypt'].append((time.perf_counter() - start) * 1000)
                    assert restored == data
        measurement = {'input_bytes': size, 'variants': {}}
        for name, (stream, xor) in variants.items():
            with patch.object(crypto, '_generate_keystream', stream), patch.object(crypto, '_xor_bytes', xor):
                encrypted = crypto.encrypt(data, 'benchmark')
                measurement['variants'][name] = {
                    'median_ms': {operation: round(statistics.median(values), 3)
                                  for operation, values in timings[name].items()},
                    'peak_python_bytes': {
                        'encrypt': peak_bytes(lambda: crypto.encrypt(data, 'benchmark')),
                        'decrypt': peak_bytes(lambda: crypto.decrypt(encrypted, 'benchmark')),
                        'xor': peak_bytes(lambda: xor(data, data)),
                    },
                }
        report['measurements'].append(measurement)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
