"""Bounded UI-09 examples and virtual input-to-flushed-frame measurements.

Run from any directory with Python 3.11+ and the standard library. This is a
synthetic toolkit harness, not the official Cereja UI or a clipboard backend.
"""

import argparse
import hashlib
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from _ui_bench import emit, environment, summaries, traced
from cereja.ui.buffer import CellBuffer, Rect
from cereja.ui.editing import TextInput
from cereja.ui.events import KeyEvent, PasteEvent
from cereja.ui.focus import FocusManager, FocusScope, FocusTarget
from cereja.ui.layout import Constraint, inset, split_rows
from cereja.ui.scheduling import EventLoop
from cereja.ui.terminal import TerminalSession
from cereja.ui.testing import VirtualBackend
from cereja.ui.text import TextPolicy

SIZES = ((120, 40), (80, 24), (40, 12))
WORKLOADS = {
    'ascii': ('/synthetic --value ' + 'x' * 32, KeyEvent('x', 'x')),
    'unicode': ('a\u0301界👩\u200d💻🇧🇷 ' * 8, KeyEvent('x', 'x')),
    'long_input': ('a\u0301界👩\u200d💻 ' * 512, PasteEvent('x\t\n/synthetic')),
}


def paint(field, size, *, ascii_only=False, focused=True, status='Synthetic input example'):
    width, height = size
    frame = CellBuffer(width, height, policy=TextPolicy(ascii_only=ascii_only))
    bounds = Rect(0, 0, max(0, width - 1), height)
    body, dock = split_rows(bounds, (Constraint(), Constraint.fixed(4)))
    frame.draw_text(2, body.y, status, clip=body)
    frame.draw_text(2, body.y + 1, 'No command parser, job or clipboard transport.', clip=body)
    frame.draw_text(2, dock.y, '-' * max(0, width - 4), clip=dock)
    view = field.paint(frame, inset(Rect(dock.x, dock.y + 1, dock.width, min(1, dock.height)),
                                   left=2, right=1), focused=focused)
    frame.draw_text(2, dock.y + 2, 'Enter: submit intent | Ctrl+C: copy/exit intent', clip=dock)
    frame.draw_text(2, dock.y + 3, 'No history | no animation | retained LF/TAB', clip=dock)
    return frame, view.cursor


def example(size=(40, 12), *, ascii_only=False):
    """Reproducible editing, selection, contained help and state restoration."""
    field = TextInput('draft', 'a\u0301👩\u200d💻')
    focus = FocusManager(FocusScope('base', (FocusTarget('draft'), FocusTarget('result'))))
    field.handle(KeyEvent('left', modifiers=frozenset({'shift'})))
    copy = field.handle(KeyEvent('c', modifiers=frozenset({'ctrl'})))
    before = field.content, field.caret, field.selection
    focus.push(FocusScope('help', (FocusTarget('close'),)))
    focus.traverse()
    focus.pop()
    if (field.content, field.caret, field.selection) != before or focus.focused != 'draft':
        raise AssertionError('help lost edit/focus state')
    # Explicit insertion replaces the range and executes zero commands.
    field.insert('/synthetic\n\tvalue  ')
    frame, cursor = paint(field, size, ascii_only=ascii_only,
                          status='Copy requested; transport unavailable. Draft retained.')
    return {'copy_text': copy.selection.text, 'copy_revision': copy.selection.content.revision,
            'draft': field.text, 'focus': focus.focused, 'cursor_visible': cursor.visible,
            'rows': [''.join(cell.text for cell in row) for row in frame.rows]}


def sample(workload, size):
    """OS-warm virtual injection, real monotonic scheduler delay and CPU work."""
    initial, event = WORKLOADS[workload]
    field = TextInput('draft', initial)
    backend = VirtualBackend(size=size)
    milestones = {}
    loop = None
    def handle(received):
        milestones['handler'] = time.perf_counter()
        action = field.handle(received)
        if action.kind != 'changed':
            raise AssertionError('benchmark editing event did not change text')
        frame, cursor = paint(field, size)
        loop.request_render(frame, cursor=cursor)
        milestones['request'] = time.perf_counter()
    with TerminalSession(backend) as session:
        loop = EventLoop(session, handle, clock=time.monotonic)
        try:
            frame, cursor = paint(field, size)
            loop.request_render(frame, cursor=cursor)
            loop.turn()
            flushes = backend.flush_count
            started = time.perf_counter()
            backend.inject_input(event)
            loop.turn()
            wait_seconds = 0.0
            while loop.metrics.renders < 2:
                deadline = loop.next_deadline
                if deadline is None:
                    raise AssertionError('pending input frame has no deadline')
                delay = max(0.0, deadline - time.monotonic())
                wait_seconds += delay
                if delay:
                    time.sleep(delay)
                loop.turn()
            finished = time.perf_counter()
            if backend.flush_count != flushes + 1 or loop.timer_count:
                raise AssertionError('expected exactly one acknowledged event frame and no timers')
            return {'input_to_frame_ms': (finished - started) * 1000,
                    'input_to_handler_ms': (milestones['handler'] - started) * 1000,
                    'handler_to_request_ms': (milestones['request'] - milestones['handler']) * 1000,
                    'scheduler_sleep_ms': wait_seconds * 1000,
                    'renders': 1, 'flushes': 1}
        finally:
            loop.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--ascii', action='store_true')
    parser.add_argument('--size', choices=('120x40', '80x24', '40x12'), default='40x12')
    parser.add_argument('--samples', type=int, default=31)
    parser.add_argument('--warmup', type=int, default=3)
    parser.add_argument('--memory-samples', type=int, default=3)
    parser.add_argument('--output')
    args = parser.parse_args()
    if min(args.samples, args.warmup, args.memory_samples) < 1:
        parser.error('sample counts and warmup must be positive')
    if args.demo:
        value = example(tuple(map(int, args.size.split('x'))), ascii_only=args.ascii)
        print('\n'.join(value['rows']))
        return
    sources = ('cereja/ui/editing.py', 'cereja/ui/focus.py', 'benchmarks/ui_editing.py',
               'benchmarks/_ui_bench.py')
    report = {
        'environment': environment(),
        'source_git_lf_sha256': {name: hashlib.sha256((ROOT / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
                               for name in sources},
        'conditions': {
            'sizes': SIZES, 'workloads': list(WORKLOADS), 'samples': args.samples,
            'warmup': args.warmup, 'memory_samples': args.memory_samples,
            'units': 'milliseconds; separate traced Python bytes/blocks',
            'arrival': 'One event immediately after a primed frame; no workers/backlog.',
            'window': 'VirtualBackend injection through editing/layout/scheduler/renderer to acknowledged flush. '
                      'Real monotonic time/sleep includes the unchanged 30 Hz frame ceiling; no busy wait.',
            'data': {name: {'canonical_codepoints': len(TextInput('fixture', text).text),
                            'event': type(event).__name__} for name, (text, event) in WORKLOADS.items()},
            'limits': 'In-memory output acknowledgements; no OS terminal, human input, visual presentation, '
                      'emulator/SSH/ConPTY, clipboard, domain/application, RSS or universal latency claim. '
                      'Long input is stress, not representative Ledger usage.',
            'memory': 'Separate untimed tracemalloc sample; includes fixture/session creation and instrumentation.',
        }, 'results': []}
    for size in SIZES:
        for workload in WORKLOADS:
            for _ in range(args.warmup):
                sample(workload, size)
            raw = [sample(workload, size) for _ in range(args.samples)]
            memory = [traced(lambda: sample(workload, size)) for _ in range(args.memory_samples)]
            report['results'].append({'size': size, 'workload': workload, 'raw': raw, 'summary': summaries(raw),
                                      'memory_raw': memory, 'memory_summary': summaries(memory)})
    emit(report, args.output)


if __name__ == '__main__':
    main()
