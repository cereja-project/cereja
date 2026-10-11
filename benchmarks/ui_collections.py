"""UI-11 bounded synthetic examples and separate admission/paint measurements."""
import argparse
import hashlib
from pathlib import Path
import sys
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _ui_bench import emit, environment, summaries, traced
from cereja.ui.buffer import CellBuffer, Rect
from cereja.ui.collections import Row, Column, TreeNode, CollectionLimits, SelectableList, Table, TreeView
from cereja.ui.editing import TextContent, TextInput
from cereja.ui.events import KeyEvent
from cereja.ui.layout import Constraint
from cereja.ui.text import TextPolicy

SIZES = ((120, 40), (80, 24), (40, 12))
WORKLOADS = ('list_64', 'list_4096', 'table_4096', 'tree_broad_4096',
             'tree_cap_100000', 'tree_deep_10000', 'canonical_byte_cap')

def fixture(workload):
    if workload.startswith('list_'):
        count = int(workload.split('_')[1])
        return SelectableList('list', (Row(str(i), (f'item {i:05} e\u0301界😀',)) for i in range(count)))
    if workload == 'table_4096':
        return Table('table', (Column('ID', Constraint.fixed(6)), Column('Name'), Column('Value')),
                     (Row(str(i), (str(i), f'item {i:05}', '界 value e\u0301')) for i in range(4096)))
    if workload in ('tree_broad_4096', 'tree_cap_100000'):
        count = 4096 if workload == 'tree_broad_4096' else 100000
        return TreeView('tree', (TreeNode(str(i), f'node {i:05} 界',
                                         parent='0' if i else None, branch=not i) for i in range(count)))
    if workload == 'tree_deep_10000':
        return TreeView('tree', (TreeNode(str(i), f'depth {i}', parent=str(i-1) if i else None,
                                         branch=True) for i in range(10000)))
    if workload == 'canonical_byte_cap':
        content = TextContent('shared-snippet', 0, '  code\t  \n\n' * 4096)
        return SelectableList('list', (Row(str(i), (f'snippet {i}',), content) for i in range(1000)))
    raise ValueError('unknown workload')

def prepare(workload, size, *, timed=True):
    started = perf_counter_ns()
    widget = fixture(workload)
    admitted = perf_counter_ns()
    if isinstance(widget, TreeView):
        if workload == 'tree_deep_10000':
            for index in range(widget.status.retained_count):
                widget.expand(str(index))
        else:
            widget.expand('0')
    projected = perf_counter_ns()
    frame = CellBuffer(*size)
    widget.paint(frame, Rect(0, 0, size[0] - 1, size[1]))
    began = perf_counter_ns()
    action = widget.handle(KeyEvent('end'))
    view = widget.paint(frame, Rect(0, 0, size[0] - 1, size[1]))
    ended = perf_counter_ns()
    if action.kind not in ('changed', 'handled'):
        raise AssertionError('unexpected navigation intent')
    report = {'admission_us': (admitted - started) / 1000,
              'projection_setup_us': (projected - admitted) / 1000,
              'event_to_buffer_us': (ended - began) / 1000,
              'painted_rows': view.painted_rows, 'formatted_cells': view.formatted_cells,
              'retained_items': widget.status.retained_count,
              'canonical_payload_bytes': widget.status.retained_bytes,
              'examined_items': widget.status.examined_count, 'projection_rows': len(widget.order),
              'limit': widget.status.limit, 'result_state': widget.status.state}
    return report if timed else (widget, frame, view)

def sample(workload, size):
    return prepare(workload, size)

def example(kind='tree', size=(40, 12), state='complete', *, ascii_only=True):
    width, height = size
    composer = TextInput('composer', '/draft remains independent')
    content = TextContent('synthetic-snippet', 1, '  source\ttext  \n\n  final\n')
    limits = CollectionLimits(max_items=3 if state == 'truncated' else 32)
    source = state if state in ('error', 'incomplete', 'loading') else 'complete'
    count = 0 if state == 'empty' else 12
    if kind == 'tree':
        widget = TreeView('tree', (TreeNode(str(i), 'root' if i == 0 else f'node {i} e\u0301界 ' * 3,
            parent='0' if i else None, branch=not i, state=source if i == 0 else 'complete',
            content=content if i == 1 else None) for i in range(count)), limits=limits)
        if count:
            widget.expand('0')
    else:
        data = (Row(str(i), (f'item {i} e\u0301界 ' * 3,) if kind == 'list' else (str(i), f'item {i} 界 ' * 3),
                    content if i == 1 else None) for i in range(count))
        widget = (SelectableList('list', data, limits=limits, state=source) if kind == 'list' else
                  Table('table', (Column('ID', Constraint.fixed(4)), Column('Name')), data,
                        limits=limits, state=source))
    if '1' in widget.order:
        widget.select('1')
        widget.set_text_selection('1', 0, len(content.text))
    frame = CellBuffer(width, height, policy=TextPolicy(ascii_only=ascii_only))
    frame.draw_text(1, 0, 'Synthetic collections | no domain execution', clip=Rect(1, 0, max(0, width-2), 1))
    view = widget.paint(frame, Rect(1, 1, max(0, width-3), max(0, height-6)))
    composer.paint(frame, Rect(1, max(0, height-3), max(0, width-3), 1), focused=False)
    frame.draw_text(1, max(0, height-2), 'Arrows navigate | Enter requests inspect',
                    clip=Rect(1, max(0, height-2), max(0, width-2), 1))
    action = widget.handle(KeyEvent('c', modifiers=frozenset({'ctrl'})))
    return {'rows': [''.join(cell.text for cell in row) for row in frame.rows],
            'composer': composer.text, 'selected': widget.selected, 'status': widget.status.state,
            'visible_ids': view.visible_ids, 'painted_rows': view.painted_rows,
            'copy': action.selection.text if action.selection is not None else None,
            'retained_count': widget.status.retained_count}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--kind', choices=('list', 'table', 'tree'), default='tree')
    parser.add_argument('--state', choices=('complete', 'empty', 'error', 'loading', 'incomplete', 'truncated'),
                        default='complete')
    parser.add_argument('--size', choices=('120x40', '80x24', '40x12'), default='40x12')
    parser.add_argument('--unicode', action='store_true')
    parser.add_argument('--samples', type=int, default=31)
    parser.add_argument('--warmup', type=int, default=3)
    parser.add_argument('--memory-samples', type=int, default=3)
    parser.add_argument('--output')
    args = parser.parse_args()
    if min(args.samples, args.warmup, args.memory_samples) < 1:
        parser.error('sample counts must be positive')
    if args.demo:
        print('\n'.join(example(args.kind, tuple(map(int, args.size.split('x'))), args.state,
                                ascii_only=not args.unicode)['rows']))
        return
    names = ('cereja/ui/collections.py', 'cereja/ui/editing.py', 'cereja/ui/focus.py', 'cereja/ui/layout.py',
             'cereja/ui/text.py', 'cereja/ui/buffer.py', 'benchmarks/ui_collections.py', 'benchmarks/_ui_bench.py')
    report = {'environment': environment(),
              'source_git_lf_sha256': {name: hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
                                       for name in names},
              'conditions': {'sizes': SIZES, 'samples': args.samples, 'warmup': args.warmup,
                  'memory_samples': args.memory_samples, 'workloads': WORKLOADS,
                  'admission': 'Caller fixture generation, sanitization, bounded ingestion and initial projection.',
                  'projection_setup': 'One broad root expansion, or 129 explicit deep expansions; separate from paint.',
                  'event_to_buffer': 'One End navigation event and repaint of an already allocated cell buffer.',
                  'memory': 'Untimed construction/projection/paint; widget, buffer and view stay alive through snapshot. '
                            'Canonical metrics, dictionaries and caches count in traced bytes; not RSS/global memory.',
                  'limits': 'No scheduler pacing, renderer, terminal acknowledgement, human input, clipboard, domain '
                            'or application latency. Visible paint differs from bounded snapshot/expansion work. '
                            'Caps are admission policies, not #304 optimizations or Ledger calibration.'},
              'results': []}
    for size in SIZES:
        for workload in WORKLOADS:
            for _ in range(args.warmup):
                sample(workload, size)
            raw = [sample(workload, size) for _ in range(args.samples)]
            memory = [traced(lambda: prepare(workload, size, timed=False)) for _ in range(args.memory_samples)]
            report['results'].append({'size': size, 'workload': workload, 'raw': raw, 'summary': summaries(raw),
                                      'memory_raw': memory, 'memory_summary': summaries(memory)})
    emit(report, args.output)

if __name__ == '__main__':
    main()
