"""UI-06 requirements: grids, damage oracle, trusted output and transport faults."""

from dataclasses import replace
from io import StringIO
import random
import re
import subprocess
import sys
import unittest

from cereja.ui.buffer import Cell, CellBuffer, Layer, Rect, Style, compose
from cereja.ui.rendering import Cursor, Renderer, dirty_diff, full_diff
from cereja.ui.terminal import CapabilityOptions, StreamBackend, TerminalSession
from cereja.ui.testing import VirtualBackend
from cereja.ui.text import TextPolicy, text_metrics


class VTGrid:
    """Independent subset decoder, with immediate wrap/scroll as a test trap.

    Only the frozen text metrics are shared. No renderer/diff/painting code is
    used to apply encoded output. An unexpected control fails the test.
    """

    def __init__(self, width, height):
        self.width, self.height = width, height
        self.rows = [[Cell() for _ in range(width)] for _ in range(height)]
        self.x = self.y = 0
        self.style = Style()
        self.visible = False
        self.origin = True
        self.margin_reset = False
        self.printed = []
        self.cancel_count = 0
        self.pending = ''

    def _erase(self, x, y):
        previous = self.rows[y][x]
        lead = x - 1 if previous.width == 0 else x
        for i in range(lead, lead + self.rows[y][lead].width):
            self.rows[y][i] = Cell(' ', 1, previous.style)

    def _style(self, values):
        s = self.style
        names = {1: 'bold', 2: 'dim', 3: 'italic', 4: 'underline',
                 7: 'reverse', 9: 'strikethrough'}
        i = 0
        while i < len(values):
            v = values[i]
            if v == 0:
                s = Style()
            elif v in names:
                s = replace(s, **{names[v]: True})
            elif 30 <= v <= 37 or 90 <= v <= 97:
                s = replace(s, foreground=v - (90 if v >= 90 else 30) + (8 if v >= 90 else 0))
            elif 40 <= v <= 47 or 100 <= v <= 107:
                s = replace(s, background=v - (100 if v >= 100 else 40) + (8 if v >= 100 else 0))
            elif v in (38, 48):
                key = 'foreground' if v == 38 else 'background'
                if values[i + 1] == 5:
                    s = replace(s, **{key: values[i + 2]})
                    i += 2
                elif values[i + 1] == 2:
                    s = replace(s, **{key: tuple(values[i + 2:i + 5])})
                    i += 4
                else:
                    raise AssertionError('unsupported color control')
            else:
                raise AssertionError(f'unexpected SGR {v}')
            i += 1
        self.style = s

    def feed(self, output):
        output = self.pending + output
        self.pending = ''
        offset = 0
        while offset < len(output):
            if output[offset] == '\x18':
                self.cancel_count += 1
                offset += 1
                continue
            if output[offset] == '\x1b':
                control = re.match(r'\x1b\[(\??[0-9;]*)([A-Za-z])', output[offset:])
                if control is None:
                    cancel = output.find('\x18', offset + 1)
                    if cancel >= 0:
                        offset = cancel
                        continue
                    if re.fullmatch(r'\x1b(?:\[(?:\??[0-9;]*)?)?', output[offset:]):
                        self.pending = output[offset:]
                        return
                    raise AssertionError('unexpected or fragmented control')
                raw, final = control.groups()
                if raw.startswith('?'):
                    if raw == '?25' and final in ('h', 'l'):
                        self.visible = final == 'h'
                    elif raw == '?6' and final == 'l':
                        self.origin = False
                    else:
                        raise AssertionError('unexpected private mode')
                else:
                    values = [int(v) for v in raw.split(';')] if raw else []
                    if final == 'H':
                        if self.origin or not self.margin_reset:
                            raise AssertionError('cursor used before coordinate reset')
                        self.y, self.x = values[0] - 1, values[1] - 1
                        if not (0 <= self.x < self.width and 0 <= self.y < self.height):
                            raise AssertionError('cursor outside terminal')
                    elif final == 'm':
                        self._style(values or [0])
                    elif final == 'J' and values == [2]:
                        self.rows = [[Cell(' ', 1, self.style) for _ in range(self.width)]
                                     for _ in range(self.height)]
                    elif final == 'r' and not values:
                        self.margin_reset = True
                    else:
                        raise AssertionError(f'unexpected control {raw}{final}')
                offset += control.end()
                continue
            end = offset
            while end < len(output) and output[end] not in ('\x1b', '\x18'):
                end += 1
            for unit in text_metrics(output[offset:end]).units:
                if unit.kind != 'grapheme':
                    raise AssertionError('unexpected text control')
                if self.x + unit.width >= self.width:
                    raise AssertionError('print at right margin could wrap/scroll')
                for column in range(self.x, self.x + unit.width):
                    self._erase(column, self.y)
                self.rows[self.y][self.x] = Cell(unit.text, unit.width, self.style)
                if unit.width == 2:
                    self.rows[self.y][self.x + 1] = Cell('', 0, self.style)
                self.printed.append((self.x, self.y, unit.text))
                self.x += unit.width
            offset = end

    @property
    def grid(self):
        return tuple(tuple(row) for row in self.rows)


def reserved_grid(frame):
    """Expected conservative viewport, directly from immutable input cells."""
    result = []
    for row in frame.rows:
        cells = list(row)
        if cells:
            if cells[-1].width == 0:
                cells[-2] = Cell(' ', 1, cells[-1].style)
            cells[-1] = Cell()
        result.append(tuple(cells))
    return tuple(result)


class DiffTest(unittest.TestCase):
    def test_text_style_and_wide_occupancy_are_compared(self):
        old = CellBuffer(6, 1)
        old.draw_text(1, 0, '界')
        new = old.copy()
        new.draw_text(2, 0, 'x', style=Style(bold=True))
        self.assertEqual(full_diff(old, new), (Rect(1, 0, 2, 1),))
        self.assertEqual(dirty_diff(old, new, [Rect(2, 0, 1, 1)]), full_diff(old, new))
        self.assertEqual(full_diff(new, new.copy()), ())

    def test_resize_and_initial_frame_ignore_damage(self):
        old = CellBuffer(4, 2)
        new = old.resized(3, 1)
        self.assertEqual(dirty_diff(old, new, []), (Rect(0, 0, 3, 1),))
        self.assertEqual(full_diff(None, old), (Rect(0, 0, 4, 1), Rect(0, 1, 4, 1)))

    def test_wide_shift_chain_closes_old_and_new_footprints(self):
        old = CellBuffer(8, 1)
        old.draw_text(0, 0, '界界界')
        new = CellBuffer(8, 1)
        new.draw_text(1, 0, '界界界')
        self.assertEqual(full_diff(old, new), (Rect(0, 0, 7, 1),))
        self.assertEqual(dirty_diff(old, new, [Rect(0, 0, 7, 1)]), full_diff(old, new))

    def test_leader_only_change_carries_unchanged_continuation(self):
        old = CellBuffer(4, 1)
        old.draw_text(0, 0, '界')
        new = old.copy()
        new.draw_text(0, 0, '語')
        self.assertEqual(old.cell(1, 0), new.cell(1, 0))
        self.assertEqual(full_diff(old, new), (Rect(0, 0, 2, 1),))

    def test_damage_is_clipped_merged_and_typed(self):
        old = CellBuffer(4, 2)
        new = old.copy()
        new.draw_text(1, 0, 'ab')
        damage = [Rect(-10, -4, 20, 10)] * 100 + [Rect(0, 0, 0, 1)]
        self.assertEqual(dirty_diff(old, new, damage), full_diff(old, new))
        self.assertEqual(dirty_diff(old, new, [Rect(100, 0, 5, 2)]), ())
        with self.assertRaises(TypeError):
            dirty_diff(old, new, ['raw'])
        with self.assertRaises(TypeError):
            full_diff(old, object())

    def test_policy_change_invalidates_even_with_equal_cells(self):
        old = CellBuffer(3, 1)
        new = CellBuffer(3, 1, policy=TextPolicy(ambiguous_width=2))
        self.assertEqual(dirty_diff(old, new, []), (Rect(0, 0, 3, 1),))

    def test_fixed_seed_scenes_match_oracle_and_encoded_grids(self):
        # Old/new layer footprints include overlap, movement, disappearance and
        # z-order changes. Narrow damage fixtures above exercise wide neighbors.
        words = ['ab', '界', '語x', 'e\u0301', '\u0301', '👨\u200d👩\u200d👧', '♥️', '\x1b[31m', '']
        styles = [Style(), Style(foreground=2, bold=True), Style(background=9, underline=True)]
        for seed in (0, 1, 298, 299, 300, 104729):
            rng = random.Random(seed)
            layers = []
            previous = None
            size = (12, 4)
            backend = VirtualBackend(size=lambda: size)
            reference_backend = VirtualBackend(size=lambda: size)
            with TerminalSession(backend) as session, TerminalSession(reference_backend) as reference_session:
                renderer = Renderer(session, verify_damage=True)
                reference_renderer = Renderer(reference_session)
                grid = VTGrid(*size)
                for step in range(100):
                    old_layers = list(layers)
                    action = step % 7
                    if action in (0, 1) or not layers:
                        b = CellBuffer(rng.randrange(1, 7), rng.randrange(1, 4))
                        b.draw_text(0, 0, rng.choice(words), style=rng.choice(styles))
                        layers.append(Layer(b, rng.randrange(-2, size[0]), rng.randrange(-1, size[1]), rng.randrange(3)))
                        layers = layers[-5:]
                    elif action == 2:
                        layers.pop(rng.randrange(len(layers)))
                    elif action in (3, 4):
                        i = rng.randrange(len(layers))
                        item = layers[i]
                        layers[i] = replace(item, x=rng.randrange(-2, size[0]), y=rng.randrange(-1, size[1]),
                                            z=rng.randrange(3))
                    elif action == 5:
                        i = rng.randrange(len(layers))
                        item = layers[i]
                        b = item.buffer.copy()
                        b.draw_text(rng.randrange(b.width), 0, rng.choice(words), style=rng.choice(styles),
                                    clip=Rect(0, 0, b.width, b.height))
                        layers[i] = replace(item, buffer=b)
                    else:
                        new_size = (rng.randrange(1, 15), rng.randrange(1, 6))
                        if new_size != size:
                            size = new_size
                            grid = VTGrid(*size)
                    frame = compose(*size, layers)
                    damage = [Rect(l.x, l.y, l.buffer.width, l.buffer.height) for l in old_layers + layers]
                    with self.subTest(seed=seed, step=step):
                        self.assertEqual(dirty_diff(previous, frame, damage), full_diff(previous, frame))
                        offset = len(backend.output)
                        reference_offset = len(reference_backend.output)
                        renderer.render(frame, damage=damage)
                        reference_renderer.render(frame)
                        self.assertEqual(backend.output[offset:], reference_backend.output[reference_offset:])
                        grid.feed(backend.output[offset:])
                        self.assertEqual(grid.grid, reserved_grid(frame))
                    previous = frame

    def test_seeded_incremental_clips_styles_and_occupancy(self):
        words = ['abc', '界語', 'e\u0301x', '🇧🇷', '👨\u200d👩\u200d👧', '\n界', '\tx', '\x1b]52;evil']
        for seed in (300, 1700, 104729):
            rng = random.Random(seed)
            frame = CellBuffer(16, 5)
            for step in range(120):
                old = frame.copy()
                clip = Rect(rng.randrange(-2, frame.width + 2), rng.randrange(-1, frame.height + 1),
                            rng.randrange(1, 9), rng.randrange(1, 5))
                style = Style(foreground=rng.choice((None, 2, 9)), bold=bool(rng.randrange(2)))
                if step % 9 == 0:
                    frame = frame.resized(rng.randrange(1, 20), rng.randrange(1, 7))
                    damage = []
                elif step % 3 == 0:
                    frame.clear(clip=clip, style=style)
                    damage = [clip]
                else:
                    x, y = rng.randrange(-3, frame.width + 2), rng.randrange(-2, frame.height + 1)
                    word = rng.choice(words)
                    metrics = text_metrics(word)
                    bounds = Rect(x, y, max(metrics.line_widths()), len(metrics.line_widths()))
                    frame.draw_text(x, y, word, clip=clip, style=style)
                    damage = [bounds.intersection(clip)]
                with self.subTest(seed=seed, step=step):
                    self.assertEqual(dirty_diff(old, frame, damage), full_diff(old, frame))


class RenderingTest(unittest.TestCase):
    def test_unchanged_frame_and_cursor_do_no_io(self):
        backend = VirtualBackend(size=(5, 2))
        with TerminalSession(backend) as session:
            renderer = Renderer(session)
            frame = CellBuffer(5, 2)
            frame.draw_text(0, 0, 'abc')
            self.assertTrue(renderer.render(frame))
            before = (len(backend.writes), backend.flush_count)
            self.assertTrue(renderer.render(frame.copy(), damage=[]))
            self.assertEqual((len(backend.writes), backend.flush_count), before)
            self.assertTrue(renderer.screen_known)
            renderer.render(frame, cursor=Cursor(2, 1, True), damage=[])
            self.assertEqual(backend.flush_count, before[1] + 1)

    def test_plain_snapshot_never_emits_terminal_controls(self):
        backend = VirtualBackend(output_interactive=False)
        frame = CellBuffer(30, 2)
        frame.draw_text(0, 0, '\x1b]52;c;secret\x07\n界')
        with TerminalSession(backend) as session:
            renderer = Renderer(session)
            renderer.render(frame)
            before = (len(backend.writes), backend.flush_count)
            renderer.render(frame)
            self.assertEqual((len(backend.writes), backend.flush_count), before)
        self.assertNotIn('\x1b', backend.output)
        self.assertNotIn('\x07', backend.output)
        self.assertIn('\\x1b]52;c;secret\\x07', backend.output)
        self.assertEqual(backend.cells, frame.rows)

    def test_partial_write_and_flush_failure_keep_front_unknown(self):
        backend = VirtualBackend(size=(4, 1))
        frame = CellBuffer(4, 1)
        with TerminalSession(backend) as session:
            renderer = Renderer(session)
            renderer.render(frame)
            previous = renderer.front
            frame.draw_text(0, 0, 'x')
            backend.failures['write'] = [1, OSError('write')]
            with self.assertRaises(OSError):
                renderer.render(frame)
            self.assertEqual(renderer.front, previous)
            self.assertFalse(renderer.screen_known)
            self.assertTrue(session.needs_redraw)
            self.assertTrue(session.closed)

    def test_exact_grid_styles_wide_replacement_and_reserved_corner(self):
        backend = VirtualBackend(size=(6, 2))
        grid = VTGrid(6, 2)
        frame = CellBuffer(6, 2)
        style = Style(foreground=3, background=9, bold=True, dim=True, italic=True,
                      underline=True, reverse=True, strikethrough=True)
        frame.draw_text(0, 0, '界e\u0301', style=style)
        frame.draw_text(4, 1, '界', style=style)
        with TerminalSession(backend) as session:
            renderer = Renderer(session)
            renderer.render(frame, cursor=Cursor(5, 1, True))
            grid.feed(backend.output)
            expected = ((Cell('界', 2, style), Cell('', 0, style), Cell('e\u0301', 1, style),
                         Cell(), Cell(), Cell()),
                        (Cell(), Cell(), Cell(), Cell(), Cell(' ', 1, style), Cell()))
            self.assertEqual(grid.grid, expected)
            self.assertEqual(renderer.front, expected)
            self.assertEqual((grid.x, grid.y, grid.visible), (5, 1, True))
            offset = len(backend.output)
            frame.draw_text(1, 0, 'x')
            renderer.render(frame, damage=[Rect(1, 0, 1, 1)])
            grid.feed(backend.output[offset:])
            self.assertEqual(grid.grid, reserved_grid(frame))

    def test_last_column_never_printed_at_any_row_or_width(self):
        for width, height in ((1, 1), (1, 4), (2, 1), (2, 4), (8, 3)):
            with self.subTest(size=(width, height)):
                backend = VirtualBackend(size=(width, height))
                grid = VTGrid(width, height)
                frame = CellBuffer(width, height)
                for y in range(height):
                    frame.draw_text(0, y, 'x' * width)
                with TerminalSession(backend) as session:
                    renderer = Renderer(session)
                    renderer.render(frame)
                    grid.feed(backend.output)
                    self.assertEqual(grid.grid, reserved_grid(frame))
                    self.assertTrue(all(x < width - 1 for x, y, text in grid.printed))
                    self.assertIn('\x1b[2J', backend.output)

    def test_injection_attempts_are_visible_text_only(self):
        attempts = ['\x1b[2J', '\x1b]52;c;c2VjcmV0\x07', '\x1b]8;;https://evil\x1b\\',
                    '\x9b31m', '\x9d52;secret\x9c', '\x18\x00\r\b', '\ud800', '\u202e']
        for raw in attempts:
            with self.subTest(raw=ascii(raw)):
                frame = CellBuffer(80, 2)
                frame.draw_text(0, 0, raw)
                backend = VirtualBackend(size=frame.size)
                grid = VTGrid(*frame.size)
                with TerminalSession(backend) as session:
                    Renderer(session).render(frame)
                    grid.feed(backend.output)
                self.assertEqual(grid.grid, reserved_grid(frame))
                for cell in frame.rows[0]:
                    self.assertFalse(any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in cell.text))

    def test_short_write_suffixes_and_progress_bound(self):
        backend = VirtualBackend(size=(4, 1), write_counts=[1] * 200)
        frame = CellBuffer(4, 1)
        frame.draw_text(0, 0, 'ab')
        with TerminalSession(backend) as session:
            renderer = Renderer(session)
            renderer.render(frame)
            attempts = [op[1] for op in backend.operations if op[0] == 'write']
            self.assertEqual(len(attempts), len(backend.output))
            for i, suffix in enumerate(attempts):
                self.assertEqual(suffix, backend.output[i:])
            self.assertEqual(backend.flush_count, 1)
            self.assertEqual(renderer.front, reserved_grid(frame))
            VTGrid(*frame.size).feed(backend.output)

    def test_every_invalid_count_after_prefix_leaves_unknown_state(self):
        for count in (None, False, True, 0, -1, 10000, 0.5, '1'):
            with self.subTest(count=count):
                backend = VirtualBackend(size=(3, 1), write_counts=[1, count])
                with TerminalSession(backend) as session:
                    renderer = Renderer(session)
                    with self.assertRaises(OSError):
                        renderer.render(CellBuffer(3, 1))
                    self.assertIsNone(renderer.front)
                    self.assertFalse(renderer.screen_known)
                    self.assertTrue(session.closed)
                    self.assertEqual(backend.flush_count, 0)
                    self.assertEqual(len(backend.writes), 1)

    def test_flush_failure_and_test_hook_failure_never_commit_front(self):
        for operation in ('flush', 'commit_cells'):
            backend = VirtualBackend(size=(4, 1))
            frame = CellBuffer(4, 1)
            with TerminalSession(backend) as session:
                renderer = Renderer(session)
                renderer.render(frame)
                previous = renderer.front
                committed = backend.cells
                frame.draw_text(0, 0, 'new')
                failure = OSError(operation)
                backend.failures[operation] = failure
                with self.assertRaises(OSError) as caught:
                    renderer.render(frame)
                self.assertIs(caught.exception, failure)
                self.assertEqual(renderer.front, previous)
                self.assertEqual(backend.cells, committed)
                self.assertFalse(renderer.screen_known)
                self.assertTrue(session.needs_redraw)

    def test_reacquired_session_forces_full_redraw_after_each_failure(self):
        frame = CellBuffer(5, 2)
        frame.draw_text(0, 0, 'hello\n界x')
        for operation, failure in (('write', OSError()), ('flush', OSError()),
                                   ('write', BrokenPipeError()), ('flush', BrokenPipeError())):
            with self.subTest(operation=operation, error=type(failure).__name__):
                backend = VirtualBackend(size=frame.size, failures={operation: [1, failure] if operation == 'write' else failure})
                with TerminalSession(backend) as session:
                    renderer = Renderer(session)
                    if isinstance(failure, BrokenPipeError):
                        self.assertFalse(renderer.render(frame))
                        self.assertTrue(session.broken_pipe)
                    else:
                        with self.assertRaises(OSError):
                            renderer.render(frame)
                    self.assertFalse(renderer.screen_known)
                offset = len(backend.output)
                grid = VTGrid(*frame.size)
                if operation == 'write':
                    grid.feed(backend.output)
                with TerminalSession(backend) as recovered:
                    new_renderer = Renderer(recovered)
                    new_renderer.render(frame, damage=[])
                    transaction = backend.output[offset:]
                    self.assertTrue(transaction.startswith('\x18\x1b[0m'))
                    self.assertIn('\x1b[2J', transaction)
                    grid.feed(transaction)
                    self.assertEqual(grid.grid, reserved_grid(frame))
                    self.assertTrue(new_renderer.screen_known)

    def test_front_and_input_are_owned_snapshots(self):
        frame = CellBuffer(5, 1)
        frame.draw_text(0, 0, 'abc')
        backend = VirtualBackend(size=frame.size)
        with TerminalSession(backend) as session:
            renderer = Renderer(session)
            renderer.render(frame)
            snapshot = renderer.front
            frame.draw_text(0, 0, 'xyz')
            self.assertEqual(renderer.front, snapshot)
            self.assertEqual(backend.cells, snapshot)
            renderer.render(frame)
            self.assertEqual(snapshot[0][0].text, 'a')
            self.assertEqual(renderer.front[0][0].text, 'x')

    def test_front_stays_previous_until_successful_flush(self):
        backend = VirtualBackend(size=(4, 1))
        frame = CellBuffer(4, 1)
        with TerminalSession(backend) as session:
            renderer = Renderer(session)
            renderer.render(frame)
            previous = renderer.front
            frame.draw_text(0, 0, 'x')

            def observe():
                self.assertEqual(renderer.front, previous)
                self.assertFalse(renderer.screen_known)
                self.assertTrue(session.needs_redraw)
            backend.failures['write'] = observe
            backend.failures['flush'] = observe
            renderer.render(frame)
            self.assertTrue(renderer.screen_known)
            self.assertEqual(renderer.front[0][0].text, 'x')

    def test_interactive_backend_without_virtual_commit_hook(self):
        backend = VirtualBackend(size=(4, 1))
        backend.commit_cells = None
        with TerminalSession(backend) as session:
            renderer = Renderer(session)
            renderer.render(CellBuffer(4, 1))
            self.assertTrue(renderer.screen_known)

    def test_damage_verification_fails_before_io_and_keeps_front(self):
        backend = VirtualBackend(size=(5, 1))
        frame = CellBuffer(5, 1)
        with TerminalSession(backend) as session:
            renderer = Renderer(session, verify_damage=True)
            renderer.render(frame)
            previous = renderer.front
            before = len(backend.writes)
            frame.draw_text(2, 0, 'x')
            with self.assertRaisesRegex(ValueError, 'damage omits'):
                renderer.render(frame, damage=[])
            self.assertEqual(len(backend.writes), before)
            self.assertEqual(renderer.front, previous)
            self.assertTrue(renderer.screen_known)

    def test_plain_real_stream_no_optional_cell_commit_hook(self):
        output = StringIO()
        frame = CellBuffer(4, 2)
        frame.draw_text(0, 0, 'a\n界')
        with TerminalSession(StreamBackend(StringIO(), output, options=CapabilityOptions(unicode=True))) as session:
            renderer = Renderer(session)
            renderer.render(frame)
            before = output.getvalue()
            renderer.render(frame, cursor=Cursor(20, 20, True))
            self.assertEqual(output.getvalue(), before)
            self.assertEqual(before, 'a   \n界  \n')

    def test_capability_fallback_rgb_palette_and_no_color(self):
        frame = CellBuffer(6, 1)
        frame.draw_text(0, 0, 'x', style=Style(foreground=(255, 0, 0), background=196, bold=True))
        expected = {0: Style(bold=True), 16: Style(9, 9, bold=True),
                    256: Style(9, 196, bold=True), 24: Style((255, 0, 0), 196, bold=True)}
        for depth in (0, 16, 256, 24):
            with self.subTest(depth=depth):
                backend = VirtualBackend(size=frame.size, options=CapabilityOptions(color=depth))
                with TerminalSession(backend) as session:
                    renderer = Renderer(session)
                    renderer.render(frame)
                    grid = VTGrid(*frame.size)
                    grid.feed(backend.output)
                    self.assertEqual(grid.grid[0][0], Cell('x', 1, expected[depth]))
                    self.assertEqual(renderer.front, grid.grid)

    def test_equivalent_effective_color_is_a_noop(self):
        backend = VirtualBackend(size=(4, 1), options=CapabilityOptions(color=0))
        frame = CellBuffer(4, 1)
        with TerminalSession(backend) as session:
            renderer = Renderer(session)
            renderer.render(frame)
            before = (len(backend.writes), backend.flush_count)
            frame.draw_text(0, 0, ' ', style=Style(foreground=(0, 1, 2)))
            renderer.render(frame)
            self.assertEqual((len(backend.writes), backend.flush_count), before)

    def test_ascii_fallback_uses_shared_policy_and_rejects_wrong_frame(self):
        backend = VirtualBackend(size=(6, 1), options=CapabilityOptions(unicode=False))
        with TerminalSession(backend) as session:
            renderer = Renderer(session)
            with self.assertRaises(ValueError):
                renderer.render(CellBuffer(6, 1))
            self.assertEqual(len(backend.writes), 0)
            frame = CellBuffer(6, 1, policy=TextPolicy(ascii_only=True))
            frame.draw_text(0, 0, '界👨\u200d👩\u200d👧e\u0301')
            renderer.render(frame)
            self.assertEqual(tuple(c.text for c in renderer.front[0]), ('?', '?', '?', ' ', ' ', ' '))
            self.assertTrue(backend.output.isascii())

    def test_suspend_other_output_and_capabilities_require_redraw(self):
        backend = VirtualBackend(size=(4, 1))
        frame = CellBuffer(4, 1)
        with TerminalSession(backend) as session:
            renderer = Renderer(session)
            renderer.render(frame)
            for action in ('suspend', 'other_text', 'other_renderer', 'capability', 'invalidate'):
                with self.subTest(action=action):
                    if action == 'suspend':
                        with session.suspend():
                            self.assertFalse(renderer.screen_known)
                    elif action == 'other_text':
                        session.write_text('external')
                    elif action == 'other_renderer':
                        Renderer(session).render(frame)
                    elif action == 'capability':
                        session.capabilities = replace(session.capabilities, color_depth=0)
                    else:
                        renderer.invalidate()
                    self.assertFalse(renderer.screen_known)
                    offset = len(backend.output)
                    renderer.render(frame, damage=[])
                    self.assertIn('\x1b[2J', backend.output[offset:])
                    self.assertTrue(renderer.screen_known)

    def test_resize_clears_unknown_area_and_viewport_mismatch_fails(self):
        size = (6, 2)
        backend = VirtualBackend(size=lambda: size)
        frame = CellBuffer(*size)
        frame.draw_text(0, 0, 'abcde')
        with TerminalSession(backend) as session:
            renderer = Renderer(session)
            renderer.render(frame)
            before = len(backend.writes)
            with self.assertRaises(ValueError):
                renderer.render(CellBuffer(20, 20))
            self.assertEqual(len(backend.writes), before)
            for size in ((3, 1), (8, 4)):
                offset = len(backend.output)
                frame = frame.resized(*size)
                renderer.render(frame, damage=[])
                transaction = backend.output[offset:]
                self.assertIn('\x1b[2J', transaction)
                grid = VTGrid(*size)
                grid.feed(transaction)
                self.assertEqual(grid.grid, reserved_grid(frame))

    def test_zero_dimensions_are_supported_and_then_idle(self):
        for size in ((0, 0), (0, 3), (3, 0)):
            for plain in (False, True):
                with self.subTest(size=size, plain=plain):
                    backend = VirtualBackend(size=size, output_interactive=not plain)
                    with TerminalSession(backend) as session:
                        renderer = Renderer(session)
                        renderer.render(CellBuffer(*size))
                        before = (len(backend.writes), backend.flush_count)
                        renderer.render(CellBuffer(*size))
                        self.assertEqual((len(backend.writes), backend.flush_count), before)
                        self.assertTrue(renderer.screen_known)

    def test_cursor_and_frame_inputs_fail_before_transport(self):
        for args in ((True, 0), (-1, 0), (0, 0, 1)):
            with self.assertRaises((TypeError, ValueError)):
                Cursor(*args)
        backend = VirtualBackend(size=(4, 1))
        with TerminalSession(backend) as session:
            renderer = Renderer(session)
            for frame, cursor in ((object(), Cursor()), (CellBuffer(4, 1), 'raw'),
                                  (CellBuffer(4, 1), Cursor(4, 0))):
                with self.assertRaises((TypeError, ValueError)):
                    renderer.render(frame, cursor=cursor)
            self.assertEqual(len(backend.writes), 0)

    def test_renderer_is_not_loaded_by_lightweight_imports(self):
        script = ('import sys; import cereja; import cereja.ui; import cereja.ui.terminal; '
                  'assert "cereja.ui.rendering" not in sys.modules; '
                  'assert "cereja.ui.buffer" not in sys.modules; '
                  'assert "cereja.ui._unicode17" not in sys.modules; '
                  'assert "cereja.display" not in sys.modules')
        result = subprocess.run([sys.executable, '-B', '-S', '-c', script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
