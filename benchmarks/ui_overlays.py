"""UI-10 bounded synthetic views and event-to-cell-buffer baseline (stdlib only)."""

import argparse
import hashlib
from pathlib import Path
import sys
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from _ui_bench import emit, environment, summaries, traced
from cereja.ui.buffer import CellBuffer, Rect
from cereja.ui.editing import TextInput
from cereja.ui.events import KeyEvent, PasteEvent
from cereja.ui.focus import FocusManager, FocusScope, FocusTarget
from cereja.ui.overlays import (Suggestion, Suggestions, FormField, ParameterForm,
                               ReviewTarget, Confirmation, OverlayStack)
from cereja.ui.text import TextPolicy

SIZES = ((120, 40), (80, 24), (40, 12))


def base():
    return OverlayStack(FocusManager(FocusScope('base', (FocusTarget('composer'), FocusTarget('result')))))


def fixture_form():
    return ParameterForm('params', 'Synthetic parameters', (
        FormField('source', 'Source', '/synthetic/source', required=True, help='No real path is read.'),
        FormField('destination', 'Destination', required=True, help='A synthetic target; no file is written.'),
        FormField('kind', 'Kind', 'file', help='Caller supplies supported kinds/policies.'),
    ))


def draw(stack, composer, size, *, current=None, ascii_only=False):
    width, height = size
    frame = CellBuffer(width, height, policy=TextPolicy(ascii_only=ascii_only))
    dock = Rect(2, height - 4, max(0, width - 4), 4)
    frame.draw_text(dock.x, dock.y, '-' * dock.width, clip=dock)
    composer.paint(frame, Rect(dock.x, dock.y + 1, dock.width, 1),
                   focused=stack.top is None or isinstance(stack.top, Suggestions))
    frame.draw_text(dock.x, dock.y + 2, 'Synthetic only | no execution/clipboard', clip=dock)
    frame.draw_text(dock.x, dock.y + 3, 'One key event, one intent | no history', clip=dock)
    view = stack.paint(frame, Rect(0, 0, width - 1, height), dock, current_target=current)
    return frame, view


def example(state='suggestions', size=(40, 12), *, ascii_only=True):
    composer = TextInput('composer', '/s')
    stack = base()
    shelf = Suggestions('slash', composer, (
        Suggestion('system', '/system', '/system ', 'Synthetic system suggestion'),
        Suggestion('search', '/search', '/search ', 'Synthetic search suggestion')))
    stack.open(shelf)
    trace = []
    params, current = None, None
    if state != 'suggestions':
        trace.append(stack.handle(KeyEvent('enter')).kind)
        trace.append(composer.handle(KeyEvent('enter')).kind)
        params = fixture_form()
        stack.open(params)
        trace.append(stack.handle(KeyEvent('enter')).kind)
        if state == 'help':
            trace.append(stack.handle(KeyEvent('f1')).kind)
        if state in ('review', 'stale'):
            stack.handle(PasteEvent('/synthetic/output/' + '界' * 80))
            stack.focus.focus('@primary')
            trace.append(stack.handle(KeyEvent('enter')).kind)
            stack.close()
            current = ReviewTarget('synthetic-create', 'fixture:1', params.input('destination').text,
                                   'file', 'create; refuse existing', 'synthetic-only', 'absent:1', permitted=True)
            review = Confirmation('review', current, form=params)
            stack.open(review)
            draw(stack, composer, size, current=current, ascii_only=ascii_only)
            if state == 'stale':
                params.input('destination').insert('changed')
    frame, view = draw(stack, composer, size, current=current, ascii_only=ascii_only)
    return {'rows': [''.join(cell.text for cell in row) for row in frame.rows],
            'composer': composer.text, 'focus': stack.focus.focused, 'trace': trace,
            'cursor_visible': view.cursor.visible, 'overlay_rect': view.rect,
            'values': dict(params.values) if params is not None else {}}


def sample(workload, size):
    composer = TextInput('composer', '/tool-')
    stack = base()
    current = None
    if workload == 'filter_256':
        stack.open(Suggestions('catalogue', composer, (
            Suggestion(str(index), f'/tool-{index:03}', f'/tool-{index:03} ', 'synthetic') for index in range(256))))
        event = KeyEvent('1', '1')
    elif workload == 'form_error':
        stack.open(fixture_form())
        event = KeyEvent('enter')
    elif workload == 'long_review_page':
        current = ReviewTarget('synthetic', 'fixture:1', '/synthetic/' + '界' * 512,
                               'file', 'create; refuse existing', 'synthetic-only', 'absent:1', permitted=True)
        stack.open(Confirmation('review', current))
        draw(stack, composer, size, current=current)
        event = KeyEvent('page_down')
    else:
        raise ValueError('unknown workload')
    started = perf_counter_ns()
    action = stack.handle(event, current_target=current)
    frame, view = draw(stack, composer, size, current=current)
    elapsed = perf_counter_ns() - started
    if action.kind not in ('changed', 'rejected'):
        raise AssertionError('unexpected workload intent')
    return {'event_to_buffer_us': elapsed / 1000,
            'visible_rows': view.viewport.visible.height,
            'cells': frame.width * frame.height}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--state', choices=('suggestions', 'form', 'help', 'review', 'stale'), default='form')
    parser.add_argument('--size', choices=('120x40', '80x24', '40x12'), default='40x12')
    parser.add_argument('--ascii', action='store_true')
    parser.add_argument('--samples', type=int, default=31)
    parser.add_argument('--warmup', type=int, default=3)
    parser.add_argument('--memory-samples', type=int, default=3)
    parser.add_argument('--output')
    args = parser.parse_args()
    if min(args.samples, args.warmup, args.memory_samples) < 1:
        parser.error('sample counts must be positive')
    if args.demo:
        value = example(args.state, tuple(map(int, args.size.split('x'))), ascii_only=args.ascii)
        print('\n'.join(value['rows']))
        return
    names = ('cereja/ui/overlays.py', 'benchmarks/ui_overlays.py', 'benchmarks/_ui_bench.py')
    report = {
        'environment': environment(),
        'source_git_lf_sha256': {name: hashlib.sha256((ROOT / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
                               for name in names},
        'conditions': {
            'sizes': SIZES, 'samples': args.samples, 'warmup': args.warmup, 'memory_samples': args.memory_samples,
            'workloads': {'filter_256': 'Stable prefix filtering over 256 caller-supplied synthetic suggestions.',
                          'form_error': 'Three fields; explicit validation and first-error reveal.',
                          'long_review_page': 'Synthetic target of 512 CJK characters; full details wrapping and paging stress.'},
            'window': 'One UI-owned keyboard event through models/layout/paint into a fresh cell buffer; GC enabled.',
            'units': 'microseconds; separate untimed traced Python bytes/blocks',
            'limits': 'No scheduler pacing, renderer/output acknowledgement, OS terminal, human input, clipboard, '
                      'domain/application, RSS or absolute performance gate. No change to #304 budgets.',
            'memory': 'Untimed window includes fixture construction, canonical state, wrapping and frame; not cumulative allocations.'},
        'results': []}
    for size in SIZES:
        for workload in report['conditions']['workloads']:
            for _ in range(args.warmup):
                sample(workload, size)
            raw = [sample(workload, size) for _ in range(args.samples)]
            memory = [traced(lambda: sample(workload, size)) for _ in range(args.memory_samples)]
            report['results'].append({'size': size, 'workload': workload, 'raw': raw, 'summary': summaries(raw),
                                      'memory_raw': memory, 'memory_summary': summaries(memory)})
    emit(report, args.output)


if __name__ == '__main__':
    main()
