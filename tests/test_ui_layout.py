"""Requirement-derived geometry, damage and state-preservation checks for #307."""

from dataclasses import replace
import itertools
from pathlib import Path
import runpy
import sys
import unittest

from cereja.ui.buffer import CellBuffer, Rect
from cereja.ui.layout import Constraint, Viewport, inset, layout_damage, split_columns, split_rows
from cereja.ui.rendering import dirty_diff, full_diff


def text_rows(frame):
    return tuple(''.join(cell.text for cell in row) for row in frame.rows)


class LayoutTest(unittest.TestCase):
    def test_ledger_cell_allocations_and_composer_are_exact(self):
        for width, height, body_height in ((120, 40, 32), (80, 24, 16), (40, 12, 4)):
            with self.subTest(size=(width, height)):
                root = Rect(0, 0, width - 1, height)
                header, body, pager, composer = split_rows(root, (
                    Constraint.fixed(3), Constraint(minimum=4),
                    Constraint.fixed(1), Constraint.fixed(4)))
                self.assertEqual((header, body, pager, composer), (
                    Rect(0, 0, width - 1, 3), Rect(0, 3, width - 1, body_height),
                    Rect(0, height - 5, width - 1, 1), Rect(0, height - 4, width - 1, 4)))
                title, fields, actions = split_rows(body, (
                    Constraint.fixed(1), Constraint(), Constraint.fixed(1)))
                self.assertEqual(fields.height, height - 10)
                self.assertEqual(actions.y + actions.height, pager.y)

    def test_weighted_columns_cap_and_redistribute_without_lost_cells(self):
        columns = split_columns(Rect(2, 3, 12, 4), (
            Constraint(maximum=2, weight=1), Constraint(weight=2), Constraint(weight=1)), gap=1)
        self.assertEqual(columns, (Rect(2, 3, 2, 4), Rect(5, 3, 5, 4), Rect(11, 3, 3, 4)))
        self.assertEqual(split_columns(Rect(0, 0, 1, 1), (
            Constraint(weight=1), Constraint(weight=1000))), (Rect(0, 0, 0, 1), Rect(0, 0, 1, 1)))

    def test_zero_weight_and_capped_tracks_leave_trailing_space(self):
        self.assertEqual(split_rows(Rect(0, 0, 3, 9), (
            Constraint.fixed(2), Constraint(minimum=1, weight=0))),
            (Rect(0, 0, 3, 2), Rect(0, 2, 3, 1)))
        self.assertEqual(split_columns(Rect(0, 0, 9, 2), (Constraint(maximum=2),)),
                         (Rect(0, 0, 2, 2),))

    def test_undersized_minima_are_clipped_in_order(self):
        self.assertEqual(split_rows(Rect(0, 0, 3, 4), (
            Constraint.fixed(3), Constraint.fixed(3))),
            (Rect(0, 0, 3, 3), Rect(0, 3, 3, 1)))
        self.assertEqual(split_columns(Rect(0, 0, 1, 1), (Constraint(),) * 4, gap=2),
                         (Rect(0, 0, 0, 1), Rect(1, 0, 0, 1),
                          Rect(1, 0, 0, 1), Rect(1, 0, 0, 1)))

    def test_exhaustive_small_partitions_are_contained_and_disjoint(self):
        for size, count, gap in itertools.product(range(8), range(5), range(3)):
            bounds = Rect(-2, 5, size, 3)
            tracks = split_columns(bounds, (Constraint(minimum=1, maximum=3),) * count, gap=gap)
            previous = bounds.x
            for track in tracks:
                self.assertGreaterEqual(track.x, previous)
                self.assertLessEqual(track.x + track.width, bounds.x + bounds.width)
                self.assertEqual((track.y, track.height), (5, 3))
                previous = track.x + track.width
            self.assertEqual(len(tracks), count)

    def test_padding_is_saturating_and_stays_inside_original_bounds(self):
        self.assertEqual(inset(Rect(2, 3, 8, 7), left=2, top=1, right=1, bottom=3),
                         Rect(4, 4, 5, 3))
        self.assertEqual(inset(Rect(2, 3, 1, 0), left=9, top=9, right=9, bottom=9),
                         Rect(3, 3, 0, 0))
        self.assertEqual(split_rows(Rect(2, 3, 0, 0), (Constraint(),)), (Rect(2, 3, 0, 0),))
        self.assertEqual(split_rows(Rect(0, 0, 1, 1), ()), ())

    def test_invalid_geometry_fails_explicitly(self):
        for operation, exception in (
            (lambda: Constraint(minimum=True), TypeError),
            (lambda: Constraint(maximum=-1), ValueError),
            (lambda: Constraint(minimum=3, maximum=2), ValueError),
            (lambda: Constraint(weight=-1), ValueError),
            (lambda: split_rows(Rect(0, 0, 2, 2), ['x']), TypeError),
            (lambda: split_rows(Rect(0, 0, 2, 2), [Constraint()], gap=True), TypeError),
            (lambda: inset(Rect(0, 0, 2, 2), left=-1), ValueError),
            (lambda: Viewport(Rect(0, 0, 2, 2), -1, 2), ValueError),
            (lambda: Viewport(Rect(0, 0, 2, 2), 1, 2, scroll_y=True), TypeError),
            (lambda: Viewport(Rect(0, 0, 2, 2), 1, 2, clip='x'), TypeError),
        ):
            with self.subTest(operation=operation), self.assertRaises(exception):
                operation()


class ViewportTest(unittest.TestCase):
    def test_offsets_clamp_without_rewriting_requested_anchor(self):
        view = Viewport(Rect(2, 3, 5, 4), 8, 10, scroll_x=99, scroll_y=99)
        self.assertEqual(view.offset, (3, 6))
        self.assertEqual(view.visible, Rect(3, 6, 5, 4))
        self.assertEqual(view.origin, (-1, -3))
        self.assertEqual((view.scroll_x, view.scroll_y), (99, 99))
        self.assertEqual(view.scrolled(dx=-1, dy=-2).offset, (2, 4))

    def test_resize_reveals_selected_item_and_preserves_external_state(self):
        editing = {'draft': '/context search TODO', 'caret': 11, 'range': (3, 8), 'focus': 'composer'}
        inspection = {'selected_id': 'result-1:row-71', 'selected_row': 71}
        before = (editing.copy(), inspection.copy())
        selected = Rect(0, inspection['selected_row'], 1, 1)
        view = Viewport(Rect(0, 3, 79, 16), 79, 100, scroll_y=63)
        compact = view.resized(Rect(0, 3, 39, 4)).ensure_visible(selected)
        self.assertEqual(compact.offset[1], 68)
        self.assertLessEqual(compact.visible.y, 71)
        self.assertGreater(compact.visible.y + compact.visible.height, 71)
        hidden = compact.resized(Rect(0, 0, 0, 0)).ensure_visible(selected)
        self.assertEqual((hidden.scroll_x, hidden.scroll_y), (compact.scroll_x, compact.scroll_y))
        self.assertEqual(hidden.scrolled(dy=100), hidden)
        restored = hidden.resized(compact.rect)
        self.assertEqual(restored.offset, compact.offset)
        self.assertEqual((editing, inspection), before)

    def test_ensure_visible_honors_both_axes_and_oversized_target(self):
        view = Viewport(Rect(2, 3, 5, 4), 20, 30)
        moved = view.ensure_visible(Rect(12, 15, 2, 2))
        self.assertEqual(moved.offset, (9, 13))
        self.assertEqual(moved.ensure_visible(Rect(1, 2, 9, 8)).offset, (1, 2))
        self.assertEqual(moved.ensure_visible(Rect(12, 15, 1, 1)), moved)
        with self.assertRaises(ValueError):
            view.ensure_visible(Rect(19, 0, 2, 1))

    def test_nested_clip_maps_to_logical_content(self):
        view = Viewport(Rect(1, 2, 8, 4), 100, 100, scroll_x=3, scroll_y=8,
                        clip=Rect(3, 3, 4, 2))
        self.assertEqual(view.clip_rect, Rect(3, 3, 4, 2))
        self.assertEqual(view.visible, Rect(5, 9, 4, 2))
        frame = CellBuffer(12, 8)
        frame.draw_text(0, 7, 'composer')
        ox, oy = view.origin
        for row in range(view.visible.y, view.visible.y + view.visible.height):
            frame.draw_text(ox + 3, oy + row, '01234567', clip=view.clip_rect)
        self.assertEqual(text_rows(frame)[3:5], ('   2345     ',) * 2)
        self.assertEqual(text_rows(frame)[7], 'composer    ')
        self.assertEqual(text_rows(frame)[2], ' ' * 12)

    def test_wide_glyph_edges_reuse_buffer_occupancy_policy(self):
        view = Viewport(Rect(2, 0, 2, 1), 5, 1, scroll_x=1)
        frame = CellBuffer(6, 1)
        frame.draw_text(*view.origin, '界a界', clip=view.clip_rect)
        self.assertEqual(text_rows(frame), ('   a  ',))
        self.assertTrue(all(cell.width == 1 for cell in frame.rows[0]))

    def test_content_smaller_than_view_and_disjoint_clip_are_empty_safe(self):
        view = Viewport(Rect(2, 3, 9, 8), 2, 1)
        self.assertEqual(view.visible, Rect(0, 0, 2, 1))
        clipped = replace(view, clip=Rect(12, 3, 1, 1))
        self.assertEqual(clipped.visible.width, 0)
        self.assertLessEqual(clipped.visible.x, view.content_width)
        self.assertEqual(Viewport(Rect(0, 0, 0, 0), 0, 0).visible, Rect(0, 0, 0, 0))

    def test_long_content_only_requests_visible_rows(self):
        view = Viewport(Rect(0, 3, 39, 4), 100, 10**9, scroll_y=800000000)
        reads = []
        frame = CellBuffer(40, 12)
        for row in range(view.visible.y, view.visible.y + view.visible.height):
            reads.append(row)
            frame.draw_text(view.origin[0], view.origin[1] + row, str(row), clip=view.clip_rect)
        self.assertEqual(reads, list(range(800000000, 800000004)))
        self.assertEqual(text_rows(frame)[3:7], tuple(f'{row:<40}' for row in reads))


class DamageTest(unittest.TestCase):
    def test_add_remove_move_and_noop_damage(self):
        bounds = Rect(0, 0, 8, 5)
        first, moved = Rect(1, 1, 2, 2), Rect(4, 1, 2, 2)
        self.assertEqual(layout_damage([first], [first], bounds), ())
        self.assertEqual(layout_damage([first], [moved], bounds), (first, moved))
        self.assertEqual(layout_damage([first], [], bounds), (first,))
        self.assertEqual(layout_damage([], [moved], bounds), (moved,))
        self.assertEqual(layout_damage([Rect(-1, -1, 2, 2)], [], bounds), (Rect(0, 0, 1, 1),))

    def test_damage_budget_falls_back_to_bounds_and_validates_inputs(self):
        bounds = Rect(0, 0, 8, 5)
        self.assertEqual(layout_damage([], [Rect(0, 0, 1, 1), Rect(2, 2, 1, 1)],
                                       bounds, max_regions=1), (bounds,))
        self.assertEqual(layout_damage([], [Rect(9, 9, 1, 1)], bounds), ())
        with self.assertRaises(ValueError):
            layout_damage([], [], bounds, max_regions=0)
        with self.assertRaises(TypeError):
            layout_damage([], ['x'], bounds)

    def test_geometry_damage_matches_full_diff_for_removed_and_moved_content(self):
        bounds = Rect(0, 0, 12, 8)
        old, new = Rect(1, 1, 4, 2), Rect(6, 3, 3, 1)
        front, back = CellBuffer(12, 8), CellBuffer(12, 8)
        front.draw_text(old.x, old.y, 'old\ntext', clip=old)
        back.draw_text(new.x, new.y, 'new', clip=new)
        self.assertEqual(dirty_diff(front, back, layout_damage([old], [new], bounds)),
                         full_diff(front, back))


class LayoutExampleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.old_path = sys.path[:]
        sys.path.insert(0, str(root / 'benchmarks'))
        cls.example = runpy.run_path(str(root / 'benchmarks/ui_layout.py'))

    @classmethod
    def tearDownClass(cls):
        sys.path[:] = cls.old_path

    def test_ascii_frames_keep_selected_row_draft_and_reserved_column(self):
        for width, height in ((120, 40), (80, 24), (40, 12)):
            frame = self.example['demo'](width, height)
            rows = text_rows(frame)
            self.assertEqual((len(rows), set(map(len, rows))), (height, {width}))
            self.assertTrue(all(row[-1] == ' ' for row in rows))
            self.assertTrue(any('> [071]' in row for row in rows[3:height - 5]))
            self.assertIn('/tree --path ./docs', rows[height - 3])
            self.assertTrue(all(ord(char) < 128 for row in rows for char in row))
        recovery = text_rows(self.example['demo'](32, 10))
        self.assertIn('Size recovery', recovery[0])
        self.assertIn('No task is running.', recovery[3])

    def test_benchmark_is_geometry_only_and_uses_bounded_regions(self):
        for workload in ('resize', 'long_content'):
            result = self.example['sample'](workload)
            self.assertGreater(result['elapsed_ns'], 0)
            self.assertLessEqual(result['visible_rows'], 32)
            self.assertLessEqual(result['damage_regions'], 8)


if __name__ == '__main__':
    unittest.main()
