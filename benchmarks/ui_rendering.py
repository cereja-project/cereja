"""Isolated warm UI-06 stages and UTF-8 payload counts, not application latency.

python -B -S benchmarks/ui_rendering.py --samples 31
Uses a synchronous memory sink, with no terminal, OS writes or flush cost.
"""

import argparse
import json
from pathlib import Path
import platform
from statistics import median
import sys
from time import perf_counter_ns
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cereja.ui.buffer import CellBuffer, Layer, Rect, compose  # noqa: E402
from cereja.ui import rendering  # noqa: E402
from cereja.ui.terminal import TerminalSession  # noqa: E402
from cereja.ui.testing import VirtualBackend  # noqa: E402


class MemorySink(VirtualBackend):
    """Acknowledge text synchronously, retain counters rather than output/logs."""

    commit_cells = None

    def _step(self, *args):
        return None

    def reset_counters(self):
        self.bytes = self.write_count = self.flush_count = 0
        self.write_ns = self.flush_ns = 0

    def write(self, text):
        start = perf_counter_ns()
        self.bytes += len(text.encode('utf-8'))
        self.write_count += 1
        self.write_ns += perf_counter_ns() - start
        return len(text)

    def flush(self):
        start = perf_counter_ns()
        self.flush_count += 1
        self.flush_ns += perf_counter_ns() - start


def timed(function, *args, **kwargs):
    start = perf_counter_ns()
    result = function(*args, **kwargs)
    return result, perf_counter_ns() - start


def draw_workload(base, count):
    frame = base.copy()
    remaining = count
    damage = []
    for y in range(frame.height):
        cells = min(frame.width - 1, remaining)
        if cells:
            frame.draw_text(0, y, 'y' * cells)
            damage.append(Rect(0, y, cells, 1))
            remaining -= cells
    return frame, damage


def sample(width, height, count):
    base = CellBuffer(width, height)
    for y in range(height):
        base.draw_text(0, y, 'x' * (width - 1))
    sink = MemorySink(size=base.size)
    sink.reset_counters()
    with TerminalSession(sink) as session:
        renderer = rendering.Renderer(session)
        renderer.render(base)
        sink.reset_counters()
        (source, damage), paint_ns = timed(draw_workload, base, count)
        frame, compose_ns = timed(compose, width, height, [Layer(source)])
        stages = {}

        def instrument(name):
            original = getattr(rendering, name)

            def wrapped(*args, **kwargs):
                value, elapsed = timed(original, *args, **kwargs)
                stages[name] = elapsed
                return value
            return patch.object(rendering, name, wrapped)

        with instrument('_prepare_frame'), instrument('dirty_diff'), instrument('_encode'):
            _, render_ns = timed(renderer.render, frame, damage=damage)
        # Independently time the full oracle on the same effective inputs. This
        # is outside render_ns and does not count as an output transaction.
        back = rendering._prepare_frame(frame, session.capabilities)
        front = rendering._prepare_frame(base, session.capabilities)
        reference, full_diff_ns = timed(rendering.full_diff, front, back)
        assert reference == rendering.dirty_diff(front, back, damage)
        assert sink.write_count == sink.flush_count == (1 if count else 0)
        return {
            'paint_ns': paint_ns, 'compose_ns': compose_ns,
            'prepare_ns': stages['_prepare_frame'], 'full_diff_ns': full_diff_ns,
            'dirty_diff_ns': stages['dirty_diff'], 'encode_ns': stages['_encode'],
            'render_total_ns': render_ns, 'write_sink_ns': sink.write_ns,
            'flush_sink_ns': sink.flush_ns, 'utf8_bytes': sink.bytes,
            'writes': sink.write_count, 'flushes': sink.flush_count,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=int, default=31)
    parser.add_argument('--width', type=int, default=80)
    parser.add_argument('--height', type=int, default=24)
    args = parser.parse_args()
    if args.samples < 1 or args.width < 2 or args.height < 1:
        parser.error('samples/height must be positive; width must be at least 2')
    area = (args.width - 1) * args.height
    workloads = [('unchanged', 0), ('one_cell', 1), ('one_row', args.width - 1),
                 ('ten_percent', max(1, area // 10)), ('all_drawable_cells', area)]
    results = []
    for name, count in workloads:
        sample(args.width, args.height, count)  # Warm imports/metrics and paths.
        values = [sample(args.width, args.height, count) for _ in range(args.samples)]
        results.append({'workload': name, 'changed_cells': count,
                        **{key: median([s[key] for s in values]) for key in values[0]}})
    print(json.dumps({'python': sys.version, 'platform': platform.platform(),
                      'dimensions': [args.width, args.height], 'drawable_cells': area,
                      'samples': args.samples, 'statistic': 'median',
                      'conditions': 'warm imports/metrics; ASCII; one default style; contiguous row-major changes; '
                                    'caller damage; synchronous memory sink; cursor hidden at 0,0; reserved final column',
                      'limits': 'No OS transport/emulator/SSH/ConPTY, UI input/layout/widgets, cold imports or application latency. '
                                'Stage medians are not additive. render_total includes preparation, dirty diff, encoding, '
                                'snapshot allocation, instrument overhead, transport and front commit; full_diff is separate.',
                      'results': results}, indent=2))


if __name__ == '__main__':
    main()
