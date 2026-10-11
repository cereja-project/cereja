"""Frozen #307 geometry baseline and bounded plain-text layout example.

python -B -S benchmarks/ui_layout.py --demo --size 40x12 --selected 71
python -B -S benchmarks/ui_layout.py --samples 31 --memory-samples 7 --output report.json
"""

import argparse
import hashlib
from pathlib import Path
import sys
from time import perf_counter_ns

from _ui_bench import emit, environment, summaries, traced

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cereja.ui.buffer import CellBuffer, Rect, Style  # noqa: E402
from cereja.ui.layout import Constraint, Viewport, inset, layout_damage, split_rows  # noqa: E402
from cereja.ui.text import TextPolicy  # noqa: E402

SIZES = ((120, 40), (80, 24), (40, 12))
TRACKS = (Constraint.fixed(3), Constraint(minimum=4), Constraint.fixed(1), Constraint.fixed(4))
ITERATIONS = 100
CONTENT_ROWS = 1_000_000
CONTENT_COLUMNS = 256
SELECTED_ROW = 800_071


def regions(width, height):
    return split_rows(Rect(0, 0, max(0, width - 1), height), TRACKS)


def sample(workload):
    """Time geometry only; no row generation, cell painting, I/O or retention."""
    previous = regions(*SIZES[0])
    view = Viewport(previous[1], CONTENT_COLUMNS, CONTENT_ROWS, scroll_y=SELECTED_ROW - 8)
    start = perf_counter_ns()
    for index in range(ITERATIONS):
        current = regions(*SIZES[index % len(SIZES)]) if workload == 'resize' else previous
        view = view.resized(current[1]).ensure_visible(Rect(0, SELECTED_ROW, 1, 1))
        damage = layout_damage(previous, current, Rect(0, 0, *SIZES[index % len(SIZES)]))
        visible = view.visible
        previous = current
    elapsed = perf_counter_ns() - start
    return {'elapsed_ns': elapsed, 'ns_per_iteration': elapsed / ITERATIONS,
            'visible_rows': visible.height, 'damage_regions': len(damage)}


def demo(width, height, selected=71):
    """One ASCII/no-color frame; synthetic rows, no keyboard or domain execution."""
    frame = CellBuffer(width, height, policy=TextPolicy(ascii_only=True))
    drawable = Rect(0, 0, max(0, width - 1), height)
    draft = '/tree --path ./docs'
    if width < 40 or height < 12:
        for row, line in enumerate(('Size recovery', f'Need 40x12; current {width}x{height}',
                                    'Resize to restore the saved view.', 'No task is running.')):
            frame.draw_text(0, row, line, clip=drawable)
        return frame
    header, body, pager, dock = regions(width, height)
    frame.draw_text(2, header.y, 'Ledger layout example (synthetic)', clip=header)
    frame.draw_text(2, header.y + 1, '-' * max(0, width - 4), clip=header)
    content = inset(body, left=2, right=1)
    content = Rect(content.x, content.y, min(75, content.width), content.height)
    view = Viewport(content, 75, 100, scroll_y=max(0, selected - 8))
    view = view.ensure_visible(Rect(0, selected, 1, 1))
    ox, oy = view.origin
    for row in range(view.visible.y, view.visible.y + view.visible.height):
        mark = '>' if row == selected else ' '
        frame.draw_text(ox, oy + row, f'{mark} [{row:03}] synthetic retained row',
                        clip=view.clip_rect, style=Style(reverse=row == selected))
    frame.draw_text(2, pager.y, f'Row {selected + 1}/100 | scroll is explicit', clip=pager)
    for row, line in enumerate(('-' * max(0, width - 4), '> ' + draft,
                                'Example only; no input dispatch', 'Idle | motion off | no history')):
        frame.draw_text(2, dock.y + row, line, clip=dock)
    return frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--size', choices=('120x40', '80x24', '40x12', '32x10'), default='80x24')
    parser.add_argument('--selected', type=int, default=71)
    parser.add_argument('--samples', type=int, default=31)
    parser.add_argument('--memory-samples', type=int, default=7)
    parser.add_argument('--warmup', type=int, default=3)
    parser.add_argument('--output')
    args = parser.parse_args()
    if not 0 <= args.selected < 100:
        parser.error('selected must be in 0..99')
    if min(args.samples, args.memory_samples, args.warmup) < 1:
        parser.error('samples and warmup must be positive')
    if args.demo:
        width, height = map(int, args.size.split('x'))
        print('\n'.join(''.join(cell.text for cell in row) for row in demo(width, height, args.selected).rows))
        return
    report = {'environment': environment(), 'source_git_lf_sha256': {
        name: hashlib.sha256((ROOT / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        for name in ('cereja/ui/layout.py', 'benchmarks/ui_layout.py', 'benchmarks/_ui_bench.py')},
        'conditions': {'sizes': SIZES, 'iterations_per_sample': ITERATIONS,
                       'content_rows': CONTENT_ROWS, 'content_columns': CONTENT_COLUMNS,
                       'selected_row': SELECTED_ROW, 'samples': args.samples,
                       'memory_samples': args.memory_samples, 'warmup': args.warmup,
                       'workloads': ['resize', 'long_content'],
                       'window': 'Warm pure geometry, visible-target adjustment and geometry damage; GC enabled.',
                       'data': 'Synthetic logical content dimensions; no million-row list is constructed.',
                       'limits': 'No rendering, clipboard, terminal, input, domain, RSS or application performance.',
                       'memory': 'Separate untimed tracemalloc windows; retained sample result and peak Python bytes.'},
        'results': []}
    for workload in ('resize', 'long_content'):
        for _ in range(args.warmup):
            sample(workload)
        raw = [sample(workload) for _ in range(args.samples)]
        memory = [traced(lambda: sample(workload)) for _ in range(args.memory_samples)]
        report['results'].append({'workload': workload, 'raw': raw, 'summary': summaries(raw),
                                  'memory_raw': memory, 'memory_summary': summaries(memory)})
    emit(report, args.output)


if __name__ == '__main__':
    main()
