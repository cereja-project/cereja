"""Expected cell grids and an independent sparse-glyph composition oracle."""

from dataclasses import FrozenInstanceError
import random
import unittest

from cereja.ui.buffer import CellBuffer, Layer, Rect, Style, compose
from cereja.ui.testing import VirtualBackend
from cereja.ui.text import TextPolicy, text_metrics


DEFAULT = Style()
RED = Style(foreground=1, bold=True)
BLUE = Style(background=(12, 34, 56), underline=True)


def grid(frame):
    return tuple(tuple((cell.text, cell.width, cell.style) for cell in row)
                 for row in frame.rows)


def row(*entries, style=DEFAULT):
    return tuple((text, width, style) for text, width in entries)


class Reference:
    """Sparse whole glyphs plus blank backgrounds, without CellBuffer operations.

    Unicode measurement is deliberately shared; geometry, replacement and grid
    expansion use a separate representation and set-based visibility oracle.
    """

    def __init__(self, width, height, style=DEFAULT):
        self.width, self.height = width, height
        self.backgrounds = {(x, y): style for y in range(height) for x in range(width)}
        self.glyphs = []

    def allowed(self, clip):
        return {point for point in self.backgrounds if clip is None or (
            clip.x <= point[0] < clip.x + clip.width and
            clip.y <= point[1] < clip.y + clip.height)}

    def stamp(self, x, y, text, width, style):
        footprint = {(x + offset, y) for offset in range(width)}
        kept = []
        for gx, gy, value, span, previous_style in self.glyphs:
            occupied = {(gx + offset, gy) for offset in range(span)}
            if occupied & footprint:
                for point in occupied:
                    self.backgrounds[point] = previous_style
            else:
                kept.append((gx, gy, value, span, previous_style))
        self.glyphs = kept
        for point in footprint:
            self.backgrounds[point] = style
        if text != ' ':
            self.glyphs.append((x, y, text, width, style))

    def paint(self, x, y, text, width, style, allowed):
        footprint = {(x + offset, y) for offset in range(width)}
        visible = footprint & allowed
        if footprint <= allowed:
            self.stamp(x, y, text, width, style)
        else:
            for cx, cy in sorted(visible):
                self.stamp(cx, cy, ' ', 1, style)

    def draw(self, x, y, text, style=DEFAULT, clip=None, policy=TextPolicy(), tab_size=4):
        allowed = self.allowed(clip)
        column, line = 0, 0
        for unit in text_metrics(text, policy).units:
            if unit.kind == 'newline':
                column, line = 0, line + 1
            elif unit.kind == 'tab':
                end = column + tab_size - column % tab_size
                while column < end:
                    self.paint(x + column, y + line, ' ', 1, style, allowed)
                    column += 1
            else:
                self.paint(x + column, y + line, unit.text, unit.width, style, allowed)
                column += unit.width

    def clear(self, clip=None, style=DEFAULT):
        for x, y in sorted(self.allowed(clip), key=lambda point: (point[1], point[0])):
            self.stamp(x, y, ' ', 1, style)

    def blit(self, source, x, y, clip=None):
        allowed = self.allowed(clip)
        for sy, cells in enumerate(source.grid()):
            for sx, (text, width, style) in enumerate(cells):
                if width:
                    self.paint(x + sx, y + sy, text, width, style, allowed)

    def grid(self):
        cells = {point: (' ', 1, style) for point, style in self.backgrounds.items()}
        for x, y, text, width, style in self.glyphs:
            cells[x, y] = (text, width, style)
            if width == 2:
                cells[x + 1, y] = ('', 0, style)
        return tuple(tuple(cells[x, y] for x in range(self.width))
                     for y in range(self.height))


class CellBufferTest(unittest.TestCase):
    def assert_valid(self, frame):
        self.assertEqual(len(frame.rows), frame.height)
        for cells in frame.rows:
            self.assertEqual(len(cells), frame.width)
            for index, cell in enumerate(cells):
                if cell.width == 0:
                    self.assertGreater(index, 0)
                    self.assertEqual(cells[index - 1].width, 2)
                    self.assertEqual(cell.text, '')
                    self.assertEqual(cell.style, cells[index - 1].style)
                if cell.width == 2:
                    self.assertLess(index + 1, frame.width)
                    self.assertEqual(cells[index + 1].width, 0)

    def test_blank_and_zero_dimension_frames(self):
        self.assertEqual(grid(CellBuffer(3, 1)), (row((' ', 1), (' ', 1), (' ', 1)),))
        for width, height in ((0, 0), (0, 3), (5, 0)):
            frame = CellBuffer(width, height)
            self.assertEqual(frame.size, (width, height))
            self.assertEqual(frame.rows, tuple(() for _ in range(height)))
            frame.draw_text(-2, -1, '界\nabc')
            frame.clear()
            self.assert_valid(frame)
        for args, error in (((-1, 2), ValueError), ((True, 2), TypeError), ((1.5, 2), TypeError)):
            with self.assertRaises(error):
                CellBuffer(*args)

    def test_immutable_cells_snapshots_and_copy_ownership(self):
        frame = CellBuffer(3, 1)
        frame.draw_text(0, 0, '界', style=RED)
        snapshot, copied = frame.rows, frame.copy()
        with self.assertRaises(FrozenInstanceError):
            snapshot[0][0].text = 'x'
        frame.draw_text(1, 0, 'a')
        self.assertEqual(copied.rows, snapshot)
        self.assertNotEqual(frame.rows, snapshot)
        with self.assertRaises(IndexError):
            frame.cell(-1, 0)
        with self.assertRaises(IndexError):
            frame.cell(3, 0)
        with self.assertRaises(TypeError):
            frame.cell(0.0, 0)

    def test_effective_style_interning_and_equality_include_occupancy(self):
        frame = CellBuffer(4, 1)
        frame.draw_text(0, 0, '界', style=Style(foreground=1, bold=True))
        frame.draw_text(2, 0, 'a', style=Style(foreground=1, bold=True))
        self.assertIs(frame.cell(0, 0).style, frame.cell(2, 0).style)
        self.assertIs(frame.cell(0, 0).style, frame.cell(1, 0).style)
        self.assertNotEqual(frame.cell(0, 0), frame.cell(1, 0))
        self.assertNotEqual(CellBuffer(1, 1).rows, CellBuffer(1, 1, style=RED).rows)
        for kwargs, error in (({'foreground': 256}, ValueError),
                              ({'background': (1, 2, -1)}, ValueError),
                              ({'foreground': 'red'}, TypeError),
                              ({'bold': 1}, TypeError)):
            with self.assertRaises(error):
                Style(**kwargs)

    def test_shared_unicode_metrics_golden_grid(self):
        frame = CellBuffer(12, 1)
        frame.draw_text(0, 0, 'Aé e\u0301界👨\u200d👩\u200d👧\u200d👦🇧🇷\u0301')
        expected = row(('A', 1), ('é', 1), (' ', 1), ('e\u0301', 1),
                       ('界', 2), ('', 0), ('👨\u200d👩\u200d👧\u200d👦', 2), ('', 0),
                       ('?', 1), (' ', 1), (' ', 1), (' ', 1))
        # The attached mark makes the flag non-RGI, so #298 falls back as a whole.
        self.assertEqual(grid(frame), (expected,))
        isolated = CellBuffer(1, 1)
        isolated.draw_text(0, 0, '\u0301')
        self.assertEqual(isolated.cell(0, 0).text, '◌\u0301')

    def test_replacing_either_wide_half_clears_entire_old_footprint(self):
        for column in (0, 1):
            frame = CellBuffer(3, 1)
            frame.draw_text(0, 0, '界', style=RED)
            frame.draw_text(column, 0, 'x', style=BLUE)
            expected = [(' ', 1, RED), (' ', 1, RED), (' ', 1, DEFAULT)]
            expected[column] = ('x', 1, BLUE)
            self.assertEqual(grid(frame), (tuple(expected),))
            self.assert_valid(frame)

    def test_wide_replacement_clears_two_overlapping_glyphs(self):
        frame = CellBuffer(4, 1)
        frame.draw_text(0, 0, '界界', style=RED)
        frame.draw_text(1, 0, '😃', style=BLUE)
        self.assertEqual(grid(frame), (((' ', 1, RED), ('😃', 2, BLUE),
                                       ('', 0, BLUE), (' ', 1, RED)),))
        self.assert_valid(frame)

    def test_clear_expands_to_previous_wide_footprint(self):
        frame = CellBuffer(4, 1)
        frame.draw_text(1, 0, '界', style=RED)
        frame.clear(clip=Rect(2, 0, 1, 1), style=BLUE)
        self.assertEqual(grid(frame), (((' ', 1, DEFAULT), (' ', 1, RED),
                                       (' ', 1, BLUE), (' ', 1, DEFAULT)),))

    def test_clip_edges_become_styled_blanks_without_split_clusters(self):
        for x, clip, expected in (
            (-1, None, row((' ', 1), ('a', 1), (' ', 1))),
            (1, None, row((' ', 1), ('界', 2), ('', 0))),
            (2, None, row((' ', 1), (' ', 1), (' ', 1))),
            (0, Rect(1, 0, 2, 1), row((' ', 1), (' ', 1), ('a', 1))),
            (0, Rect(0, 0, 1, 1), row((' ', 1), (' ', 1), (' ', 1))),
        ):
            with self.subTest(x=x, clip=clip):
                frame = CellBuffer(3, 1)
                frame.draw_text(x, 0, '界a', clip=clip)
                self.assertEqual(grid(frame), (expected,))
                self.assert_valid(frame)
        frame = CellBuffer(1, 1)
        frame.draw_text(0, 0, '界', style=RED)
        self.assertEqual(grid(frame), (row((' ', 1), style=RED),))

    def test_blit_clips_source_wide_edges_and_is_opaque(self):
        source = CellBuffer(3, 1, style=RED)
        source.draw_text(0, 0, '界', style=RED)
        for x in (-1, 2):
            target = CellBuffer(3, 1)
            target.draw_text(0, 0, 'abc')
            target.blit(source, x, 0)
            expected = (((' ', 1, RED), (' ', 1, RED), ('c', 1, DEFAULT)) if x == -1
                        else (('a', 1, DEFAULT), ('b', 1, DEFAULT), (' ', 1, RED)))
            self.assertEqual(grid(target), (expected,))
            self.assert_valid(target)

    def test_self_blit_uses_source_snapshot(self):
        frame = CellBuffer(6, 1)
        frame.draw_text(0, 0, 'ab界')
        frame.blit(frame, 1, 0)
        self.assertEqual(grid(frame), (row(('a', 1), ('a', 1), ('b', 1),
                                         ('界', 2), ('', 0), (' ', 1)),))

    def test_multiline_tabs_use_local_metrics_without_wrapping(self):
        frame = CellBuffer(7, 2)
        frame.draw_text(1, 0, 'a\t界\nxy')
        self.assertEqual(grid(frame), (
            row((' ', 1), ('a', 1), (' ', 1), (' ', 1), (' ', 1), ('界', 2), ('', 0)),
            row((' ', 1), ('x', 1), ('y', 1), (' ', 1), (' ', 1), (' ', 1), (' ', 1))))
        frame = CellBuffer(1, 2)
        frame.draw_text(0, -1, 'abc\nz')
        self.assertEqual(grid(frame), (row(('z', 1)), row((' ', 1))))

    def test_normalization_and_width_policy_are_shared(self):
        for policy in (TextPolicy(), TextPolicy(ambiguous_width=2), TextPolicy(ascii_only=True)):
            frame = CellBuffer(24, 1, policy=policy)
            text = '\x1b[31m·界❤️'
            frame.draw_text(0, 0, text)
            reference = Reference(24, 1)
            reference.draw(0, 0, text, policy=policy)
            self.assertEqual(grid(frame), reference.grid())
            self.assertNotIn('\x1b', ''.join(cell.text for cell in frame.rows[0]))
            self.assert_valid(frame)

    def test_resize_preserves_intersection_and_blanks_cut_wide_glyph(self):
        frame = CellBuffer(4, 2, style=BLUE)
        frame.draw_text(1, 0, '界', style=RED)
        resized = frame.resized(2, 3, style=DEFAULT)
        self.assertEqual(grid(resized), (
            ((' ', 1, BLUE), (' ', 1, RED)),
            row((' ', 1), (' ', 1), style=BLUE), row((' ', 1), (' ', 1))))
        self.assertEqual(frame.size, (4, 2))
        self.assert_valid(resized)

    def test_invalid_operations_do_not_change_frame(self):
        frame = CellBuffer(2, 1)
        before = frame.rows
        for action, error in (
            (lambda: frame.draw_text(True, 0, 'a'), TypeError),
            (lambda: frame.draw_text(0, 0, 'a', tab_size=0), ValueError),
            (lambda: frame.draw_text(0, 0, 'a', style='red'), TypeError),
            (lambda: frame.draw_text(0, 0, 'a', clip=(0, 0, 1, 1)), TypeError),
            (lambda: frame.blit(CellBuffer(2, 1, policy=TextPolicy(ascii_only=True))), ValueError),
            (lambda: Rect(0, 0, -1, 1), ValueError),
        ):
            with self.assertRaises(error):
                action()
            self.assertEqual(frame.rows, before)

    def test_rect_intersection_empty_clips_and_large_tabs(self):
        self.assertEqual(Rect(-2, -1, 5, 3).intersection(Rect(0, 0, 4, 4)), Rect(0, 0, 3, 2))
        frame = CellBuffer(3, 1)
        frame.draw_text(0, 0, 'abc')
        before = frame.rows
        frame.draw_text(0, 0, '界', clip=Rect(0, 0, 0, 1))
        frame.clear(clip=Rect(10, 10, 3, 3))
        self.assertEqual(frame.rows, before)
        frame.draw_text(-999999, 0, '\tx', tab_size=1000000, style=RED)
        self.assertEqual(grid(frame), (row((' ', 1), ('x', 1), style=RED) + (('c', 1, DEFAULT),),))

    def test_compose_zero_sizes_validation_and_policy_preservation(self):
        policy = TextPolicy(ambiguous_width=2)
        source = CellBuffer(2, 1, policy=policy)
        source.draw_text(0, 0, '·')
        self.assertEqual(compose(2, 1, (Layer(source) for _ in range(1)), policy=policy).rows,
                         source.rows)
        self.assertEqual(source.copy().policy, policy)
        self.assertEqual(source.resized(0, 3).rows, ((), (), ()))
        for size in ((0, 3), (3, 0), (0, 0)):
            self.assert_valid(compose(*size, [Layer(source)], policy=policy))
        for operation, error in ((lambda: compose(2, 1, [Layer(source)]), ValueError),
                                 (lambda: compose(2, 1, [source]), TypeError),
                                 (lambda: Layer(source, z=True), TypeError),
                                 (lambda: CellBuffer(2, 1, policy=None), TypeError)):
            with self.assertRaises(error):
                operation()

    def test_exhaustive_small_wide_overlap_and_clip_grids(self):
        source = CellBuffer(4, 1, style=BLUE)
        source.draw_text(0, 0, '界界', style=BLUE)
        source_reference = Reference(4, 1, BLUE)
        source_reference.draw(0, 0, '界界', style=BLUE)
        for width in range(6):
            for offset in range(-4, 6):
                for left in range(-1, 7):
                    for span in range(7):
                        clip = Rect(left, 0, span, 1)
                        frame, expected = CellBuffer(width, 1), Reference(width, 1)
                        frame.draw_text(0, 0, 'a界😃', style=RED)
                        expected.draw(0, 0, 'a界😃', style=RED)
                        frame.blit(source, offset, clip=clip)
                        expected.blit(source_reference, offset, 0, clip)
                        with self.subTest(width=width, offset=offset, left=left, span=span):
                            self.assertEqual(grid(frame), expected.grid())
                            self.assert_valid(frame)

    def test_composition_z_order_ties_opaque_blanks_and_layer_clip(self):
        low, high = CellBuffer(4, 1), CellBuffer(2, 1, style=BLUE)
        low.draw_text(0, 0, '界ab', style=RED)
        high.draw_text(0, 0, 'x', style=BLUE)
        expected = (((' ', 1, RED), ('x', 1, BLUE), (' ', 1, BLUE), ('b', 1, RED)),)
        self.assertEqual(grid(compose(4, 1, [Layer(high, 1, 0, z=10), Layer(low)])), expected)
        self.assertEqual(grid(compose(4, 1, [Layer(low), Layer(high, 1)])), expected)
        clipped = compose(4, 1, [Layer(low), Layer(high, 1, clip=Rect(2, 0, 1, 1))])
        self.assertEqual(grid(clipped), ((('界', 2, RED), ('', 0, RED),
                                        (' ', 1, BLUE), ('b', 1, RED)),))
        reverse = compose(4, 1, [Layer(high, 1), Layer(low)])
        self.assertEqual(grid(reverse), grid(low))

    def test_move_remove_and_resize_recompose_without_stale_pixels(self):
        background, overlay = CellBuffer(5, 1), CellBuffer(1, 1)
        background.draw_text(0, 0, 'a界bc')
        overlay.draw_text(0, 0, 'x')
        first = compose(5, 1, [Layer(background), Layer(overlay, 2)])
        moved = compose(5, 1, [Layer(background), Layer(overlay, 4)])
        self.assertEqual(grid(first), (row(('a', 1), (' ', 1), ('x', 1), ('b', 1), ('c', 1)),))
        self.assertEqual(grid(moved), (row(('a', 1), ('界', 2), ('', 0), ('b', 1), ('x', 1)),))
        self.assertEqual(grid(compose(5, 1, [Layer(background)])), grid(background))
        self.assertEqual(grid(compose(2, 1, [Layer(background)])), (row(('a', 1), (' ', 1)),))

    def test_virtual_backend_retains_owned_complete_frame_snapshots(self):
        frame = CellBuffer(2, 1)
        frame.draw_text(0, 0, '界')
        backend = VirtualBackend(size=frame.size)
        backend.commit_cells(frame.rows)
        before = backend.cells
        frame.clear()
        self.assertNotEqual(frame.rows, before)
        self.assertEqual(backend.cell_frames, (before,))

    def test_seeded_incremental_paint_clear_and_resize_against_sparse_reference(self):
        for seed in (299, 1700, 104729):
            rng = random.Random(seed)
            frame, reference = CellBuffer(12, 5), Reference(12, 5)
            for step in range(120):
                action = rng.choice(('paint', 'clear', 'resize'))
                clip = Rect(rng.randrange(-2, 10), rng.randrange(-1, 5),
                            rng.randrange(8), rng.randrange(5))
                style = rng.choice((DEFAULT, RED, BLUE))
                if action == 'paint':
                    x, y = rng.randrange(-3, 13), rng.randrange(-2, 6)
                    text = rng.choice(('界😃ab', 'e\u0301\t界', '🇧🇷\n❤️x', '\x1b[0m', 'abc'))
                    frame.draw_text(x, y, text, style=style, clip=clip)
                    reference.draw(x, y, text, style=style, clip=clip)
                elif action == 'clear':
                    frame.clear(clip=clip, style=style)
                    reference.clear(clip=clip, style=style)
                else:
                    width, height = rng.randrange(16), rng.randrange(7)
                    frame = frame.resized(width, height, style=style)
                    resized = Reference(width, height, style)
                    resized.blit(reference, 0, 0)
                    reference = resized
                with self.subTest(seed=seed, step=step, action=action):
                    self.assertEqual(grid(frame), reference.grid())
                    self.assert_valid(frame)

    def test_seeded_scene_overlap_move_remove_resize_against_sparse_reference(self):
        for seed in (0, 1, 299, 298, 1700, 104729):
            rng = random.Random(seed)
            policy = rng.choice((TextPolicy(), TextPolicy(ascii_only=True),
                                 TextPolicy(ambiguous_width=2)))
            scene = []
            width, height = 12, 5
            for step in range(120):
                action = ('add', 'move', 'remove', 'resize', 'reorder')[step % 5]
                if action == 'add' or not scene:
                    sw, sh = rng.randrange(1, 9), rng.randrange(1, 4)
                    style = rng.choice((DEFAULT, RED, BLUE))
                    source = CellBuffer(sw, sh, policy=policy, style=style)
                    reference = Reference(sw, sh, style)
                    text = rng.choice(('界x😃', 'e\u0301\t·', 'a\n❤️🇧🇷', '👨\u200d👩\u200d👧\u200d👦ab'))
                    source.draw_text(0, 0, text, style=style)
                    reference.draw(0, 0, text, style=style, policy=policy)
                    clip = None if rng.randrange(2) else Rect(
                        rng.randrange(-2, 10), rng.randrange(-1, 5), rng.randrange(10), rng.randrange(6))
                    scene.append([source, reference, rng.randrange(-4, 15),
                                  rng.randrange(-2, 6), rng.randrange(-2, 3), clip])
                elif action == 'move':
                    item = rng.choice(scene)
                    item[2:4] = rng.randrange(-4, 15), rng.randrange(-2, 6)
                elif action == 'remove':
                    scene.pop(rng.randrange(len(scene)))
                elif action == 'resize':
                    width, height = rng.randrange(20), rng.randrange(8)
                else:
                    rng.shuffle(scene)
                    rng.choice(scene)[4] = rng.randrange(-2, 3)
                frame = compose(width, height, [Layer(s, x, y, z, clip)
                                               for s, _, x, y, z, clip in scene], policy=policy)
                expected = Reference(width, height)
                for _, source, x, y, _, clip in sorted(scene, key=lambda item: item[4]):
                    expected.blit(source, x, y, clip)
                with self.subTest(seed=seed, step=step, action=action):
                    self.assertEqual(grid(frame), expected.grid())
                    self.assert_valid(frame)


if __name__ == '__main__':
    unittest.main()
