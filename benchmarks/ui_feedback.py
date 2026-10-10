"""Bounded synthetic feedback demo and aggregate compute/output measurements."""
import argparse
from dataclasses import asdict
import hashlib
from pathlib import Path
import sys
from time import perf_counter_ns

from _ui_bench import emit, environment, summaries

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cereja.ui.buffer import CellBuffer, Rect
from cereja.ui.events import KeyEvent, TimerEvent
from cereja.ui.feedback import ActivityIndicator, InlineStatus, ProgressBar
from cereja.ui.scheduling import EventLoop
from cereja.ui.terminal import CapabilityOptions, TerminalSession
from cereja.ui.testing import VirtualBackend
from cereja.ui.text import TextPolicy

COUNTS = (1, 16, 64, 256)
MODES = ('local', 'low-bandwidth', 'off', 'plain')


def sample(count, mode, *, output=False, rounds=4):
    """Real elapsed CPU-side work over virtual deadlines; output is an in-memory sink."""
    if count not in COUNTS or mode not in MODES or not 1 <= rounds <= 16:
        raise ValueError('unsupported bounded workload')
    backend = VirtualBackend(size=(80, max(8, count)),
        input_interactive=mode != 'plain', output_interactive=mode != 'plain',
        options=CapabilityOptions(color=0, unicode=False, reduced_motion=mode == 'off'))
    with TerminalSession(backend) as session:
        loop = EventLoop(session, lambda e: None, clock=backend.clock, low_bandwidth=mode == 'low-bandwidth')
        frame = CellBuffer(80, max(8, count), policy=TextPolicy(ascii_only=True))
        widgets = []
        dirty = []
        paints = 0
        keys = []
        def handle(event):
            nonlocal paints
            if type(event) is TimerEvent:
                widget, rect = route[event.owner]
                if widget.handle(event):
                    dirty.append(widget.paint(frame, rect))
                    paints += 1
            elif type(event) is KeyEvent:
                keys.append(event.text)
        loop.handler = handle
        begin = perf_counter_ns()
        for i in range(count):
            widget = ActivityIndicator(loop, str(i), 'Synthetic known activity', active=True,
                                       kind='dots' if i % 2 else 'spinner')
            rect = Rect(0, i, 79, 1)
            widget.paint(frame, rect)
            widgets.append((widget, rect))
        create_ns = perf_counter_ns() - begin
        route = {widget.owner: (widget, rect) for widget, rect in widgets}
        peak_timers = loop.timer_count
        if output:
            loop.request_render(frame)
            loop.turn()
        before = asdict(loop.metrics)
        byte_start = len(backend.output.encode('utf-8'))
        begin = perf_counter_ns()
        # Aggregate changed rows before taking one full latest-frame snapshot.
        for step in range(rounds):
            backend.advance(loop.indicator_interval)
            backend.inject_input(KeyEvent(str(step), str(step)))
            target = before['timer_events'] + peak_timers * (step + 1)
            loop.turn()
            while loop.metrics.timer_events < target:
                loop.turn()
            if output and dirty:
                loop.request_render(frame, decorative=True)
                loop.turn()
            dirty.clear()
        active_ns = perf_counter_ns() - begin
        active = {key: value - before[key] for key, value in asdict(loop.metrics).items()}
        active_bytes = len(backend.output.encode('utf-8')) - byte_start
        assert keys == [str(i) for i in range(rounds)]
        begin = perf_counter_ns()
        for widget, rect in widgets:
            widget.update('success', 'Synthetic complete')
            widget.paint(frame, rect)
            widget.close()
        dispose_ns = perf_counter_ns() - begin
        assert loop.timer_count == 0
        if output:
            loop.request_render(frame)  # Real completion is meaningful even in plain/motion off.
            backend.advance(1)
            loop.turn()
        idle_start = asdict(loop.metrics)
        for _ in range(10):
            backend.advance(100)
            loop.turn()
        idle = {key: value - idle_start[key] for key, value in asdict(loop.metrics).items()}
        assert all(idle[key] == 0 for key in ('timer_events', 'renders', 'writes', 'flushes'))
        loop.close()
    return {'create_ns': create_ns, 'active_ns': active_ns, 'dispose_ns': dispose_ns,
            'virtual_active_seconds': rounds * loop.indicator_interval, 'peak_timers': peak_timers, 'active_paints': paints, 'active_utf8_bytes': active_bytes,
            **{'active_' + key: active[key] for key in ('turns', 'timer_events', 'renders', 'writes', 'flushes')},
            **{'idle_' + key: idle[key] for key in ('timer_events', 'renders', 'writes', 'flushes')},
            'final_timers': 0, 'ordered_keys': len(keys)}


def example(*, motion=False, low_bandwidth=False, plain=False, kind='spinner'):
    """Fixed data replay. Returns one final snapshot, never an animation history."""
    backend = VirtualBackend(size=(80, 10), input_interactive=not plain, output_interactive=not plain)
    with TerminalSession(backend) as session:
        loop = EventLoop(session, lambda e: None, clock=backend.clock, low_bandwidth=low_bandwidth)
        loop.set_reduced_motion(not motion)
        activity = ActivityIndicator(loop, 'synthetic', 'Known synthetic activity', active=True, kind=kind)
        frame = CellBuffer(80, 10)
        activity.paint(frame, Rect(0, 0, 79, 1))
        canonical = activity.content
        loop.handler = activity.handle
        for _ in range(4):
            backend.advance(loop.indicator_interval)
            loop.turn()
            activity.paint(frame, Rect(0, 0, 79, 1))
        assert activity.content is canonical
        activity.update('success', 'Synthetic activity complete')
        activity.paint(frame, Rect(0, 0, 79, 1))
        ProgressBar('bytes', 'Synthetic count replay', completed=3, total=8,
                    reliable_total=True).paint(frame, Rect(0, 1, 79, 1))
        ProgressBar('unknown', 'Synthetic count replay', completed=3).paint(frame, Rect(0, 2, 79, 1))
        for y, (state, message) in enumerate((
            ('loading', 'Known CPU slot (synthetic placeholder)'),
            ('empty', 'No synthetic matches'), ('warning', 'Synthetic partial input; inspect cause'),
            ('error', 'Synthetic read failure; edit source'), ('idle', 'No work active')), 3):
            InlineStatus(str(y), state, message).paint(frame, Rect(0, y, 79, 1))
        activity.close()
        assert not loop.timer_count
        loop.close()
        return [''.join(c.text for c in row).rstrip() for row in frame.rows]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--motion', action='store_true')
    parser.add_argument('--low-bandwidth', action='store_true')
    parser.add_argument('--plain', action='store_true')
    parser.add_argument('--kind', choices=('spinner', 'dots'), default='spinner')
    parser.add_argument('--samples', type=int, default=31)
    parser.add_argument('--warmup', type=int, default=3)
    parser.add_argument('--output')
    args = parser.parse_args()
    if not 1 <= args.samples <= 100 or not 1 <= args.warmup <= 10:
        parser.error('samples must be 1..100 and warmup 1..10')
    if args.demo:
        print('\n'.join(example(motion=args.motion, low_bandwidth=args.low_bandwidth,
                                plain=args.plain, kind=args.kind)))
        return
    names = ('cereja/ui/feedback.py', 'cereja/ui/scheduling.py', 'cereja/ui/buffer.py',
             'cereja/ui/text.py', 'cereja/ui/editing.py', 'cereja/ui/rendering.py',
             'cereja/ui/_session.py', 'cereja/ui/testing.py',
             'benchmarks/ui_feedback.py', 'benchmarks/_ui_bench.py')
    report = {'environment': environment(),
        'source_git_lf_sha256': {n: hashlib.sha256((ROOT/n).read_bytes().replace(b'\r\n', b'\n')).hexdigest() for n in names},
        'conditions': {'counts': COUNTS, 'modes': MODES, 'samples': args.samples, 'warmup': args.warmup,
            'rounds': 4, 'geometry': '80 columns, max(8, count) rows; 256 rows is synthetic stress.',
            'clock': 'Virtual deadlines; perf_counter_ns measures actual elapsed computation. No real sleeps.',
            'boundaries': ['scheduler-to-CellBuffer', 'scheduler/CellBuffer/renderer-to-memory'],
            'output': 'Initial and real completion output excluded from active counters; virtual sink retains bounded test frames.',
            'limits': 'No real 4 ms wall-clock enforcement measurement, OS transport, terminal, human input, clipboard, '
                      'domain operation, Ledger latency or RSS/global heap claim. Source fingerprints identify measured dirty sources. '
                      '30/4 Hz frames and 8/2 Hz indicators remain candidates, not calibrated optimal rates.'},
        'results': []}
    for output in (False, True):
        for mode in MODES:
            for count in COUNTS:
                for _ in range(args.warmup):
                    sample(count, mode, output=output)
                raw = [sample(count, mode, output=output) for _ in range(args.samples)]
                report['results'].append({'count': count, 'mode': mode, 'output': output,
                                          'raw': raw, 'summary': summaries(raw)})
    emit(report, args.output)


if __name__ == '__main__':
    main()
