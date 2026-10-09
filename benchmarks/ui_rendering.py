"""Warm real core stages, full/dirty controls and memory transport, not Ledger.

python -B -S benchmarks/ui_rendering.py --samples 31 --output rendering.json
Defaults cover 80x24, 120x40, 240x80. No native I/O or emulator is involved.
"""

import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter_ns
from unittest.mock import patch

from _ui_bench import emit, environment, summaries, traced

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cereja.ui.buffer import CellBuffer, Layer, Rect, Style, compose  # noqa: E402
from cereja.ui import rendering  # noqa: E402
from cereja.ui.terminal import CapabilityOptions, TerminalSession  # noqa: E402
from cereja.ui.testing import VirtualBackend  # noqa: E402
from cereja.ui.text import text_metrics  # noqa: E402

DIMENSIONS = ((80, 24), (120, 40), (240, 80))
WORKLOADS = ('unchanged', 'one_cell', 'one_row', 'ten_percent', 'all_drawable_cells',
             'initial_full', 'resize_grow', 'resize_shrink')
PROFILES = ('ascii', 'unicode_styles')
LONG_INPUT = False
STYLES = (Style((20, 180, 90), bold=True), Style(208, underline=True),
          Style((160, 100, 220), (15, 20, 25), italic=True), Style(dim=True))


class MemorySink(VirtualBackend):
    """Acknowledged text with counters. UTF-8 byte counting is outside timing."""

    commit_cells = None

    def _step(self, *args):
        return None

    def reset_counters(self):
        self.write_count = self.flush_count = 0
        self.last_text = ''

    def write(self, text):
        self.last_text = text
        self.write_count += 1
        return len(text)

    def flush(self):
        self.flush_count += 1


def timed(function, *args, **kwargs):
    start = perf_counter_ns()
    value = function(*args, **kwargs)
    return value, perf_counter_ns() - start


def row_text(width, profile, changed=False):
    token = ('result e\u0301 \u754c \U0001f469\u200d\U0001f4bb ' if changed else
             'Ledger a\u0301 \u6f22 \U0001f468\u200d\U0001f469\u200d\U0001f467 ') if profile != 'ascii' else ('y' if changed else 'x')
    repeats = width if LONG_INPUT else (width + text_metrics(token).line_widths()[0] - 1) // text_metrics(token).line_widths()[0]
    return text_metrics(token * repeats).clip(width)


def fill(frame, profile):
    text = row_text(frame.width - 1, profile)
    for y in range(frame.height):
        frame.draw_text(0, y, text, style=STYLES[y % len(STYLES)] if profile != 'ascii' else Style())


def draw_workload(base, workload, profile):
    if workload.startswith('resize_'):
        delta = 1 if workload == 'resize_grow' else -1
        frame = base.resized(base.width + 8 * delta, base.height + 2 * delta)
        return frame, [Rect(0, 0, frame.width, frame.height)]
    frame = base.copy()
    area = (base.width - 1) * base.height
    count = {'unchanged': 0, 'one_cell': 1, 'one_row': base.width - 1,
             'ten_percent': max(1, area // 10), 'all_drawable_cells': area,
             'initial_full': 0}[workload]
    damage = []
    for y in range(frame.height):
        cells = min(frame.width - 1, count)
        if cells:
            style = STYLES[(y + 1) % len(STYLES)] if profile != 'ascii' else Style()
            frame.draw_text(0, y, row_text(cells, profile, True), style=style)
            damage.append(Rect(0, y, cells, 1))
            count -= cells
    return frame, damage


def sample(width, height, workload, profile):
    base = CellBuffer(width, height)
    fill(base, profile)
    size = [base.size]
    sink = MemorySink(size=lambda: size[0], options=CapabilityOptions(color=24))
    sink.reset_counters()
    with TerminalSession(sink) as session:
        (source, damage), paint_ns = timed(draw_workload, base, workload, profile)
        overlay = CellBuffer(min(16, source.width), min(2, source.height))
        fill(overlay, profile)
        ox, oy = source.width - overlay.width, source.height - overlay.height
        frame, compose_ns = timed(compose, *source.size,
                                  [Layer(source), Layer(overlay, ox, oy, z=1)])
        damage = damage + [Rect(ox, oy, overlay.width, overlay.height)]
        old = compose(*base.size, [Layer(base), Layer(overlay, base.width - overlay.width,
                                                              base.height - overlay.height, z=1)])
        front = None if workload == 'initial_full' else rendering._prepare_frame(old, session.capabilities)
        back, prepare_ns = timed(rendering._prepare_frame, frame, session.capabilities)
        full, full_diff_ns = timed(rendering.full_diff, front, back)
        dirty, dirty_diff_ns = timed(rendering.dirty_diff, front, back, damage)
        assert full == dirty
        is_full = front is None or front.size != back.size
        text, encode_ns = timed(rendering._encode, back, full, rendering.Cursor(), full=is_full)
        _, snapshot_ns = timed(lambda: back.rows)
        size[0] = frame.size
        sink.reset_counters()
        _, write_sink_ns = timed(sink.write, text) if text else (None, 0)
        _, flush_sink_ns = timed(sink.flush) if text else (None, 0)
        values = {'paint_ns': paint_ns, 'compose_ns': compose_ns, 'prepare_ns': prepare_ns,
                  'full_diff_ns': full_diff_ns, 'dirty_diff_ns': dirty_diff_ns,
                  'encode_ns': encode_ns, 'snapshot_ns': snapshot_ns,
                  'write_sink_ns': write_sink_ns, 'flush_sink_ns': flush_sink_ns,
                  'utf8_bytes': len(text.encode('utf-8')), 'writes': sink.write_count,
                  'flushes': sink.flush_count}
        # Alternate matched controls; old-front priming stays outside the window.
        order = ('full', 'dirty') if sample.sequence % 2 == 0 else ('dirty', 'full')
        sample.sequence += 1
        for path in order:
            renderer = rendering.Renderer(session)
            if front is not None:
                size[0] = old.size
                renderer.render(old)
            size[0] = frame.size
            sink.reset_counters()
            kwargs = {} if path == 'full' else {'damage': damage}
            _, elapsed = timed(renderer.render, frame, **kwargs)
            assert sink.last_text == text
            assert sink.write_count == sink.flush_count == (1 if text else 0)
            values[path + '_render_memory_ns'] = elapsed
        renderer = rendering.Renderer(session)
        if front is not None:
            size[0] = old.size
            renderer.render(old)
        size[0] = frame.size
        sink.reset_counters()
        stages = {}
        cell_constructions = 0
        with ExitStack() as stack:
            original_cell = rendering.Cell
            def counted_cell(*args, **kwargs):
                nonlocal cell_constructions
                cell_constructions += 1
                return original_cell(*args, **kwargs)
            stack.enter_context(patch.object(rendering, 'Cell', counted_cell))
            for name in ('_prepare_frame', 'dirty_diff', '_encode'):
                original = getattr(rendering, name)
                def wrap(*args, _name=name, _original=original, **kwargs):
                    value, elapsed = timed(_original, *args, **kwargs)
                    stages[_name] = elapsed
                    return value
                stack.enter_context(patch.object(rendering, name, wrap))
            _, values['instrumented_dirty_render_ns'] = timed(renderer.render, frame, damage=damage)
        values.update({'instrumented_prepare_ns': stages['_prepare_frame'],
                       'instrumented_diff_ns': stages['dirty_diff'],
                       'instrumented_encode_ns': stages['_encode'],
                       'prepare_cell_constructions': cell_constructions})
        assert sink.last_text == text
        return values


sample.sequence = 0


def main():
    global LONG_INPUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=int, default=31)
    parser.add_argument('--warmup', type=int, default=3)
    parser.add_argument('--memory-samples', type=int, default=7)
    parser.add_argument('--width', type=int)
    parser.add_argument('--height', type=int)
    parser.add_argument('--output')
    parser.add_argument('--transport', choices=('memory', 'windows'), default='memory')
    parser.add_argument('--native-child', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--long-input', action='store_true', help='Reproduce the preliminary overlong input stress')
    args = parser.parse_args()
    LONG_INPUT = args.long_input
    if min(args.samples, args.warmup, args.memory_samples) < 1:
        parser.error('sample counts and warmup must be positive')
    if (args.width is None) != (args.height is None):
        parser.error('width and height must be supplied together')
    dimensions = ((args.width, args.height),) if args.width is not None else DIMENSIONS
    if any(w < 10 or h < 3 for w, h in dimensions):
        parser.error('resize workloads require width >= 10 and height >= 3')
    if args.transport == 'windows':
        if os.name != 'nt':
            parser.error('Windows console transport requires Windows')
        if args.native_child:
            emit(native_output(args.samples, args.warmup), args.output)
        else:
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 0
            completed = subprocess.run(
                [sys.executable, '-B', '-S', __file__, '--transport', 'windows', '--native-child',
                 '--samples', str(args.samples), '--warmup', str(args.warmup)]
                + (['--long-input'] if args.long_input else []),
                cwd=Path(__file__).resolve().parents[1], startupinfo=startup,
                creationflags=subprocess.CREATE_NEW_CONSOLE, capture_output=True,
                text=True, encoding='utf-8', timeout=120)
            if completed.returncode:
                raise RuntimeError(completed.stdout + completed.stderr)
            emit(json.loads(completed.stdout), args.output)
        return
    conditions = {'dimensions': dimensions, 'profiles': PROFILES, 'workloads': WORKLOADS,
                  'samples': args.samples, 'warmup': args.warmup, 'memory_samples': args.memory_samples,
                  'seed': None, 'long_input': LONG_INPUT,
                  'data': 'Fixed tokens repeated by cell width (or column count for long-input stress); four row styles.',
                  'windows': 'Setup/old-front prime outside each timed operation; perf_counter_ns; '
                             'GC enabled; tracemalloc in separate untimed whole-sample windows.',
                  'capabilities': 'Interactive Unicode, RGB24, cursor hidden at 0,0, final column reserved.',
                  'cache': 'Warm imports/styles/text; representative row inputs fit the 1024-code-point metrics cache. '
                           'Long-input stress may bypass that cache.',
                  'composition': 'Two opaque layers; bottom-right 16x2 overlay; damage includes overlay.',
                  'resize': 'From each base size to +/-8 columns and +/-2 rows; same-content resize.',
                  'statistics': 'Nearest-rank p95, MAD, min/max; stage medians are not additive.',
                  'memory': 'Whole sample including setup and controls; live blocks are not allocation churn or RSS.',
                  'allocations': 'Cell constructor calls inside instrumented preparation, not total Python allocation churn.',
                  'limits': 'No widgets/layout/application/domain, native I/O, emulator/SSH/ConPTY, '
                            'input-to-visible latency, arbitrary style counts or cross-platform performance.'}
    report = {'environment': environment(), 'conditions': conditions, 'results': []}
    for width, height in dimensions:
        for profile in PROFILES:
            for workload in WORKLOADS:
                for _ in range(args.warmup):
                    sample(width, height, workload, profile)
                raw = [sample(width, height, workload, profile) for _ in range(args.samples)]
                memory = [traced(lambda: sample(width, height, workload, profile))
                          for _ in range(args.memory_samples)]
                report['results'].append({'width': width, 'height': height, 'profile': profile,
                                          'workload': workload, 'raw': raw, 'summary': summaries(raw),
                                          'memory_raw': memory, 'memory_summary': summaries(memory)})
    emit(report, args.output)


def native_output(samples, warmup):
    """Measure native transport of fixed payloads, without claiming visible frames."""
    from cereja.ui.windows import WindowsBackend
    report = {'environment': environment(), 'conditions': {
        'transport': 'Hidden fresh Windows console, WriteConsoleW UTF-16; UTF-8 bytes are logical payload accounting',
        'long_input': LONG_INPUT,
        'samples': samples, 'warmup': warmup, 'dimensions': DIMENSIONS,
        'limits': 'Fixed encoded payloads, not Renderer viewport validation or visual acknowledgement. '
                  'Logical dimensions may exceed native viewport; no emulator/SSH/ConPTY or application latency. '
                  'Session acquisition/setup/encode/restoration outside timing; stage wrappers inside transaction.'},
              'results': []}
    with open('CONIN$', 'r', encoding='utf-8') as inp, open('CONOUT$', 'w', encoding='utf-8') as out:
        backend = WindowsBackend(inp, out, environ={})
        before_modes = backend._api.get_mode(backend._input), backend._api.get_mode(backend._output)
        try:
            with TerminalSession(backend) as session:
                if session.capabilities.plain:
                    raise RuntimeError('native console did not accept interactive VT')
                report['native_viewport'] = backend.dimensions()
                report['native_color_depth'] = session.capabilities.color_depth
                for width, height in DIMENSIONS:
                    for profile in PROFILES:
                        frame = CellBuffer(width, height)
                        fill(frame, profile)
                        back = rendering._prepare_frame(frame, session.capabilities)
                        payload = rendering._encode(back, rendering.full_diff(None, back),
                                                    rendering.Cursor(), full=True)
                        raw = []
                        for _ in range(warmup + samples):
                            stages = {'write_ns': 0, 'flush_ns': 0, 'writes': 0, 'flushes': 0}
                            with ExitStack() as stack:
                                for name in ('write', 'flush'):
                                    original = getattr(backend, name)
                                    def wrap(*args, _name=name, _original=original, **kwargs):
                                        value, elapsed = timed(_original, *args, **kwargs)
                                        stages[_name + '_ns'] += elapsed
                                        stages[_name + 's' if _name == 'write' else 'flushes'] += 1
                                        return value
                                    stack.enter_context(patch.object(backend, name, wrap))
                                success, total = timed(session._write_frame, payload)
                            assert success and stages['writes'] >= 1 and stages['flushes'] == 1
                            raw.append({**stages, 'transaction_instrumented_ns': total,
                                        'utf8_bytes': len(payload.encode('utf-8')),
                                        'utf16_code_units': len(payload.encode('utf-16-le')) // 2})
                        raw = raw[warmup:]
                        report['results'].append({'width': width, 'height': height, 'profile': profile,
                                                  'workload': 'full_encoded_payload', 'raw': raw,
                                                  'summary': summaries(raw)})
            report['modes_restored'] = before_modes == (backend._api.get_mode(backend._input),
                                                       backend._api.get_mode(backend._output))
            report['cleanup_failures'] = len(session.cleanup_failures)
            assert report['modes_restored'] and not session.cleanup_failures
        finally:
            backend.close()
    return report


if __name__ == '__main__':
    main()
