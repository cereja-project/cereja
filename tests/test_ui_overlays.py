"""UI-10 keyboard, state restoration, compact review and stale-consent contracts."""

from dataclasses import replace
from pathlib import Path
import runpy
import sys
import threading
import unittest

from cereja.ui.buffer import CellBuffer, Rect
from cereja.ui.editing import TextInput
from cereja.ui.events import KeyEvent, PasteEvent, ResizeEvent
from cereja.ui.focus import FocusManager, FocusScope, FocusTarget
from cereja.ui.overlays import (Suggestion, Suggestions, FormField, ParameterForm,
                               ReviewTarget, Confirmation, HelpOverlay, OverlayStack, overlay_bounds)
from cereja.ui.scheduling import EventLoop
from cereja.ui.terminal import TerminalSession, CapabilityOptions
from cereja.ui.testing import VirtualBackend
from cereja.ui.text import TextPolicy


def key(name, text='', *mods, repeat=1):
    return KeyEvent(name, text, frozenset(mods), repeat)


def owner():
    return FocusManager(FocusScope('base', (FocusTarget('composer'), FocusTarget('result'))))


def form():
    return ParameterForm('params', 'Synthetic parameters', (
        FormField('source', 'Source', '/owned/input', required=True, help='Explicit synthetic source'),
        FormField('destination', 'Destination', required=True),
        FormField('kind', 'Kind', 'file', validator=lambda value: None if value == 'file' else 'Use file'),
    ))


def target(**changes):
    value = ReviewTarget('synthetic', 'source-id:1', '/owned/output', 'file',
                         'create, refuse existing', 'synthetic-no-clobber', 'absent:1', permitted=True)
    return replace(value, **changes)


def paint(stack, current=None, size=(40, 12), ascii_only=True):
    width, height = size
    frame = CellBuffer(width, height, policy=TextPolicy(ascii_only=ascii_only))
    dock = Rect(2, max(0, height - 4), max(0, width - 4), min(4, height))
    frame.draw_text(2, dock.y, 'persistent composer', clip=dock)
    view = stack.paint(frame, Rect(0, 0, max(0, width - 1), height), dock, current_target=current)
    return frame, view


class SuggestionsTest(unittest.TestCase):
    def shelf(self, draft='/s', **kwargs):
        field = TextInput('composer', draft, **kwargs)
        shelf = Suggestions('slash', field, (
            Suggestion('system', '/system', '/system ', 'System example'),
            Suggestion('search', '/search', '/search ', 'Search example'),
            Suggestion('tree', '/tree', '/tree ', 'Tree example')))
        stack = OverlayStack(owner())
        stack.open(shelf)
        return field, shelf, stack

    def test_first_enter_inserts_second_enter_only_returns_submit(self):
        field, shelf, stack = self.shelf()
        self.assertEqual(stack.handle(key('enter', repeat=50)).kind, 'inserted')
        self.assertEqual(field.text, '/system ')
        self.assertEqual(field.caret, 8)
        self.assertIsNone(stack.top)
        self.assertEqual(stack.focus.focused, 'composer')
        self.assertEqual(field.handle(key('enter')).kind, 'submit')

    def test_tab_accepts_escape_preserves_and_filtering_is_stable(self):
        field, shelf, stack = self.shelf()
        stack.handle(key('down'))
        self.assertEqual(shelf.selected, 'search')
        stack.handle(key('e', 'e'))
        self.assertEqual([item.identity for item in shelf.matches], ['search'])
        self.assertEqual(shelf.selected, 'search')
        self.assertEqual(stack.handle(key('tab')).kind, 'inserted')
        self.assertEqual(field.text, '/search ')
        stack.open(Suggestions('again', field, (Suggestion('x', 'x', 'x'),)))
        before = field.content, field.caret, field.selection
        self.assertEqual(stack.handle(key('escape')).kind, 'back')
        self.assertEqual((field.content, field.caret, field.selection), before)

    def test_empty_matches_consume_enter_tab_and_leave_draft(self):
        field, shelf, stack = self.shelf('/missing')
        before = field.content, field.caret
        for name in ('enter', 'tab', 'up', 'down'):
            self.assertEqual(stack.handle(key(name)).kind, 'handled')
        self.assertIs(stack.top, shelf)
        self.assertEqual((field.content, field.caret), before)

    def test_prefix_replacement_preserves_suffix_and_rejects_stale_acceptance(self):
        field, shelf, stack = self.shelf('/s --value keep')
        field.move(2)
        shelf.refresh()
        field.insert('e')
        self.assertEqual(stack.handle(key('enter')).kind, 'rejected')
        self.assertEqual(field.text, '/se --value keep')
        self.assertEqual(stack.handle(key('enter')).kind, 'inserted')
        self.assertEqual(field.text, '/search  --value keep')

    def test_rejected_acceptance_restores_original_selection_and_keeps_shelf(self):
        field = TextInput('composer', '/s', max_bytes=4)
        field.set_selection(0, 2)
        shelf = Suggestions('slash', field, (Suggestion('system', '/system', '/system '),))
        stack = OverlayStack(owner())
        stack.open(shelf)
        before = field.content, field.caret, field.selection
        self.assertEqual(stack.handle(key('enter')).kind, 'rejected')
        self.assertEqual((field.content, field.caret, field.selection), before)
        self.assertIs(stack.top, shelf)

    def test_navigation_selection_is_not_text_selection_and_copy_owns_composer(self):
        field, _, stack = self.shelf()
        self.assertEqual(stack.handle(key('c', '', 'ctrl')).kind, 'exit')
        field.set_selection(0, 2)
        self.assertEqual(stack.handle(key('c', '', 'ctrl')).selection.text, '/s')
        self.assertIsNotNone(stack.top)

    def test_catalogue_bounds_and_duplicate_id_fail_before_opening(self):
        field = TextInput('composer', '/')
        with self.assertRaises(ValueError):
            Suggestions('x', field, (Suggestion('same', 'a', 'a'), Suggestion('same', 'b', 'b')))
        with self.assertRaises(ValueError):
            Suggestions('x', field, (Suggestion(str(i), 'x', 'x') for i in range(300)))
        with self.assertRaises(ValueError):
            Suggestion('x', 'x' * 70000, 'x')


class FormTest(unittest.TestCase):
    def test_validation_retains_good_values_focuses_and_reveals_first_error(self):
        params = form()
        focus = owner()
        stack = OverlayStack(focus)
        stack.open(params)
        focus.focus('@primary')
        result = stack.handle(key('enter'))
        self.assertEqual(result.kind, 'rejected')
        self.assertEqual(params.errors, {'destination': 'Required'})
        self.assertEqual(params.input('source').text, '/owned/input')
        self.assertEqual(focus.focused, 'destination')
        frame, view = paint(stack)
        self.assertTrue(view.cursor.visible)
        self.assertTrue(any('Destination *' in ''.join(c.text for c in row) for row in frame.rows))
        self.assertTrue(any('Required' in ''.join(c.text for c in row) for row in frame.rows))
        stack.handle(PasteEvent('/owned/output'))
        focus.focus('@primary')
        result = stack.handle(key('enter'))
        self.assertEqual(result.kind, 'submit')
        self.assertEqual(dict(result.values)['destination'], '/owned/output')
        self.assertTrue(params.validated)
        self.assertIs(stack.top, params)

    def test_help_returns_exact_field_and_draft_state_after_resize(self):
        draft = TextInput('composer', 'a\u0301👩\u200d💻')
        draft.set_selection(0, 2)
        params = form()
        stack = OverlayStack(owner())
        stack.open(params)
        params.input('source').set_selection(0, 6)
        state = (draft.content, draft.caret, draft.selection,
                 params.input('source').content, params.input('source').selection)
        self.assertEqual(stack.handle(key('f1')).kind, 'help')
        stack.handle(key('tab'))
        stack.handle(key('x', 'x'))
        paint(stack, size=(3, 1))
        paint(stack, size=(120, 40))
        stack.handle(key('escape'))
        self.assertIs(stack.top, params)
        self.assertEqual(stack.focus.focused, 'source')
        self.assertEqual(state, (draft.content, draft.caret, draft.selection,
                                params.input('source').content, params.input('source').selection))

    def test_back_preserves_values_and_restores_result_invoker(self):
        focus = owner()
        focus.focus('result')
        stack = OverlayStack(focus)
        params = form()
        stack.open(params)
        params.input('destination').insert('/kept')
        focus.focus('@back')
        self.assertEqual(stack.handle(key('enter')).kind, 'back')
        self.assertEqual(focus.focused, 'result')
        stack.open(params)
        self.assertEqual(params.input('destination').text, '/kept')

    def test_tab_shift_tab_are_contained_and_skip_disabled_fields(self):
        params = ParameterForm('p', 'P', (FormField('a', 'A'), FormField('b', 'B', enabled=False)))
        stack = OverlayStack(owner())
        stack.open(params)
        stack.handle(key('tab'))
        self.assertEqual(stack.focus.focused, '@primary')
        stack.handle(key('tab', '', 'shift'))
        self.assertEqual(stack.focus.focused, 'a')
        self.assertEqual(params.input('b').text, '')

    def test_validator_focus_change_cannot_submit_or_close_another_scope(self):
        focus = owner()
        def validator(value):
            focus.push(FocusScope('foreign', (FocusTarget('source'),)))
        params = ParameterForm('p', 'P', (FormField('source', 'Source', 'x', validator=validator),))
        stack = OverlayStack(focus)
        stack.open(params)
        action = stack.handle(key('enter'))
        self.assertEqual(action.kind, 'rejected')
        self.assertEqual(action.values, ())
        self.assertEqual(focus.scope.identity, 'foreign')
        self.assertIs(stack.top, params)

    def test_callback_failure_is_safe_not_raw_diagnostics(self):
        def failure(value):
            raise ValueError('secret URL token')
        params = ParameterForm('p', 'P', (FormField('a', 'A', 'x', validator=failure),))
        stack = OverlayStack(owner())
        stack.open(params)
        action = stack.handle(key('enter'))
        self.assertEqual(action.kind, 'rejected')
        self.assertEqual(params.errors['a'], 'Validation unavailable')
        self.assertNotIn('secret', action.reason)

    def test_validator_mutation_never_validates_a_different_snapshot(self):
        params = None
        def validator(value):
            params.input('a').insert('changed')
        params = ParameterForm('p', 'P', (FormField('a', 'A', 'x', validator=validator),))
        action = params.validate()
        self.assertEqual(action.kind, 'rejected')
        self.assertFalse(params.validated)
        self.assertEqual(params.errors, {'a': 'Changed during validation'})

    def test_direct_edit_invalidates_validation_and_copy_failure_preserves_state(self):
        params = ParameterForm('p', 'P', (FormField('a', 'A', 'a\u0301界'),))
        params.validate()
        self.assertTrue(params.validated)
        params.input('a').insert('x')
        self.assertFalse(params.validated)
        stack = OverlayStack(owner())
        stack.open(params)
        params.input('a').set_selection(0, 2)
        before = params.snapshot
        for _ in range(3):
            self.assertEqual(stack.handle(key('c', '', 'ctrl')).selection.text, 'a\u0301')
            self.assertEqual(params.snapshot, before)

    def test_paste_sanitization_bounds_and_disabled_fields(self):
        params = ParameterForm('p', 'P', (FormField('a', 'A'),), max_input_bytes=8)
        stack = OverlayStack(owner())
        stack.open(params)
        stack.handle(PasteEvent('\x1b\x07'))
        self.assertEqual(params.input('a').text, r'\x1b\x07')
        before = params.snapshot
        self.assertEqual(stack.handle(PasteEvent('/run\n')).kind, 'rejected')
        self.assertEqual(params.snapshot, before)


class ConfirmationTest(unittest.TestCase):
    def review(self, value=None, params=None):
        value = value or target()
        stack = OverlayStack(owner())
        confirm = Confirmation('review', value, form=params)
        stack.open(confirm)
        paint(stack, value)
        return value, confirm, stack

    def test_default_is_back_and_explicit_run_returns_exact_tuple_only(self):
        value, confirm, stack = self.review()
        self.assertEqual(stack.focus.focused, '@back')
        self.assertEqual(stack.handle(key('enter'), current_target=value).kind, 'back')
        self.assertIsNone(confirm.authorization(value))
        stack.open(confirm)
        paint(stack, value)
        stack.handle(key('tab'))
        action = stack.handle(key('enter'), current_target=value)
        self.assertEqual(action.kind, 'confirmed')
        self.assertEqual(action.target, value)
        self.assertEqual(confirm.authorization(value), value)

    def test_review_binding_cannot_be_reassigned_without_explicit_review(self):
        value, confirm, stack = self.review()
        for name, replacement in (('target', replace(value, destination='/different')),
                                  ('form', None), ('stale', False), ('details', confirm.details)):
            with self.assertRaises(AttributeError):
                setattr(confirm, name, replacement)
        help_view = HelpOverlay('help', 'Help', 'text')
        help_view.select(0, 0)
        self.assertIsNone(help_view.selection)

    def test_every_exact_tuple_change_invalidates_and_resets_safe_focus(self):
        for name in ('action', 'source', 'destination', 'output_kind', 'effects', 'policy', 'version'):
            value, confirm, stack = self.review()
            stack.focus.focus('@primary')
            changed = replace(value, **{name: getattr(value, name) + ':changed'})
            self.assertEqual(stack.handle(key('enter'), current_target=changed).kind, 'rejected')
            self.assertIsNone(confirm.authorization(changed))
            self.assertEqual(stack.focus.focused, '@back')
            self.assertTrue(confirm.stale)
            self.assertEqual(stack.handle(key('enter'), current_target=value).kind, 'back')

    def test_edit_even_then_revert_invalidates_form_bound_consent(self):
        params = ParameterForm('p', 'P', (FormField('source', 'Source', 'same'),))
        params.validate()
        value, confirm, stack = self.review(params=params)
        stack.focus.focus('@primary')
        self.assertEqual(stack.handle(key('enter'), current_target=value).kind, 'confirmed')
        params.input('source').insert('x')
        params.input('source').handle(key('backspace'))
        self.assertEqual(params.input('source').text, 'same')
        self.assertIsNone(confirm.authorization(value))
        self.assertTrue(confirm.stale)
        with self.assertRaises(ValueError):
            confirm.review(value)
        params.validate()
        confirm.review(value)
        stack.open(confirm)
        paint(stack, value)
        self.assertEqual(stack.focus.focused, '@back')

    def test_unsupported_policy_unavailable_target_or_hidden_review_cannot_confirm(self):
        value, confirm, stack = self.review(target(permitted=False))
        self.assertNotIn('@primary', stack.focus.scope.eligible)
        stack.handle(key('tab'))
        self.assertNotEqual(stack.focus.focused, '@primary')
        value, confirm, stack = self.review()
        paint(stack, value, size=(0, 0))
        self.assertNotIn('@primary', stack.focus.scope.eligible)
        confirm.review(value)
        stack.focus.focus('@back')
        self.assertEqual(stack.handle(key('enter')).kind, 'back')
        with self.assertRaises(ValueError):
            ReviewTarget('a', '\x1braw', 'd', 'o', 'e', 'p', 'v')

    def test_target_representation_cannot_forge_another_field_with_line_breaks(self):
        import json
        value = target(destination='/owned/\nPolicy: overwrite\t"new"\\name  ')
        lines = value.plain_text.splitlines()
        self.assertEqual(len(lines), 7)
        encoded = next(line for line in lines if line.startswith('Destination: ')).split(': ', 1)[1]
        self.assertEqual(json.loads(encoded), value.destination)
        self.assertEqual(sum(line.startswith('Policy: ') for line in lines), 1)

    def test_paint_changed_target_restores_back_and_keeps_identity_and_actions_visible(self):
        value, confirm, stack = self.review()
        stack.focus.focus('@primary')
        frame, view = paint(stack, replace(value, version='changed:2'))
        rows = [''.join(c.text for c in row) for row in frame.rows]
        self.assertEqual(stack.focus.focused, '@back')
        self.assertTrue(any('Changed | To: "/owned/output"' in row for row in rows))
        self.assertTrue(any('[Help]' in row and '[PgUp/PgDn]' in row for row in rows))
        self.assertIsNone(confirm.authorization(value))

    def test_short_target_header_has_no_previous_caption_residue(self):
        value, confirm, stack = self.review(target(destination='/x'))
        frame, view = paint(stack, value)
        row = ''.join(cell.text for cell in frame.rows[view.rect.y]).strip()
        self.assertEqual(row, 'Review to: "/x"')

    def test_long_exact_target_is_paged_and_not_reconstructed_for_copy(self):
        value, confirm, stack = self.review(target(destination='/owned/' + '界' * 200))
        frame, view = paint(stack, value)
        self.assertGreater(view.viewport.content_height, view.viewport.rect.height)
        old = confirm.details.content
        stack.handle(key('a', '', 'ctrl'), current_target=value)
        copy = stack.handle(key('c', '', 'ctrl'), current_target=value)
        self.assertEqual(copy.kind, 'copy')
        self.assertEqual(copy.selection.content, old)
        self.assertIn(value.destination, copy.selection.text)
        self.assertNotIn('[Run]', copy.selection.text)
        stack.handle(key('page_down'), current_target=value)
        frame, after = paint(stack, value, ascii_only=False)
        self.assertGreater(after.viewport.offset[1], 0)
        self.assertEqual(confirm.details.content, old)


class OverlayGeometryTest(unittest.TestCase):
    def test_overlay_anchored_above_fixed_dock_and_clipped(self):
        for width, height in ((120, 40), (80, 24), (40, 12), (3, 1), (0, 0)):
            bounds = Rect(0, 0, max(0, width - 1), height)
            dock = Rect(2, max(0, height - 4), max(0, width - 4), min(4, height))
            rect = overlay_bounds(bounds, dock)
            self.assertLessEqual(rect.y + rect.height, max(bounds.y, dock.y))
            self.assertLessEqual(rect.width, dock.width)
            self.assertLessEqual(rect.x + rect.width, bounds.x + bounds.width)

    def test_compact_frames_preserve_composer_and_reveal_form_error_in_all_modes(self):
        for size in ((120, 40), (80, 24), (40, 12)):
            for ascii_only in (False, True):
                stack = OverlayStack(owner())
                params = form()
                stack.open(params)
                stack.handle(key('enter'))
                frame, view = paint(stack, size=size, ascii_only=ascii_only)
                dock_y = size[1] - 4
                self.assertIn('persistent composer', ''.join(c.text for c in frame.rows[dock_y]))
                self.assertTrue(view.cursor.visible)
                self.assertTrue(all(row[-1].text == ' ' for row in frame.rows))
                self.assertEqual(params.errors, {'destination': 'Required'})

    def test_help_wrap_copy_retains_tabs_blank_lines_whitespace_and_pinned_revision(self):
        help_view = HelpOverlay('help', 'Help', '  a\t\n\n界  \n')
        stack = OverlayStack(owner())
        stack.open(help_view)
        stack.handle(key('a', '', 'ctrl'))
        selection = stack.handle(key('c', '', 'ctrl')).selection
        for size in ((40, 12), (80, 24), (120, 40), (3, 1)):
            paint(stack, size=size)
            self.assertEqual(selection.text, '  a\t\n\n界  \n')
            self.assertEqual(help_view.selection, selection)
        stack.handle(key('escape'))
        self.assertEqual(stack.focus.focused, 'composer')

    def test_open_review_does_not_enable_run_before_new_inspectable_frame(self):
        value = target()
        review = Confirmation('review', value)
        stack = OverlayStack(owner())
        stack.open(review)
        self.assertNotIn('@primary', stack.focus.scope.eligible)
        paint(stack, value)
        stack.handle(key('escape'))
        stack.open(review)
        self.assertNotIn('@primary', stack.focus.scope.eligible)

    def test_help_content_is_readonly_and_selection_offsets_are_logical(self):
        help_view = HelpOverlay('help', 'Help', 'a\u0301界')
        help_view.select(0, 2)
        self.assertEqual(help_view.selection.text, 'a\u0301')
        with self.assertRaises(AttributeError):
            help_view.content = help_view.content
        with self.assertRaises(ValueError):
            help_view.select(0, 1)

    def test_topmost_overlay_only_owns_keys_and_depth_failure_is_atomic(self):
        focus = FocusManager(FocusScope('base', (FocusTarget('composer'),)), max_depth=2)
        stack = OverlayStack(focus)
        params = form()
        stack.open(params)
        with self.assertRaises(ValueError):
            stack.open(HelpOverlay('help', 'Help', 'bounded'))
        self.assertIs(stack.top, params)
        self.assertEqual(focus.scope.identity, 'params')

    def test_foreign_focus_scope_cannot_edit_or_be_closed_by_this_stack(self):
        focus = owner()
        stack = OverlayStack(focus)
        params = form()
        stack.open(params)
        focus.push(FocusScope('foreign', (FocusTarget('source'),)))
        before = params.snapshot
        self.assertEqual(stack.handle(PasteEvent('wrong owner')).kind, 'unhandled')
        self.assertEqual(params.snapshot, before)
        with self.assertRaises(ValueError):
            stack.close()
        self.assertEqual(focus.scope.identity, 'foreign')
        self.assertIs(stack.top, params)

    def test_help_at_depth_limit_reports_rejection_and_keeps_invoking_state(self):
        focus = FocusManager(FocusScope('base', (FocusTarget('composer'),)), max_depth=2)
        stack = OverlayStack(focus)
        stack.open(form())
        before = stack.top.snapshot
        self.assertEqual(stack.handle(key('f1')).kind, 'rejected')
        self.assertEqual(stack.top.snapshot, before)
        self.assertEqual(focus.scope.identity, 'params')

    def test_mutation_from_worker_fails_without_losing_state(self):
        stack = OverlayStack(owner())
        stack.open(form())
        failures = []
        def worker():
            try:
                stack.handle(PasteEvent('bad'))
            except RuntimeError as error:
                failures.append(error)
        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        self.assertEqual(len(failures), 1)
        self.assertEqual(stack.top.input('source').text, '/owned/input')


class VirtualOverlayReplayTest(unittest.TestCase):
    def test_keyboard_replay_copy_help_resize_and_no_idle_animation(self):
        size = [40, 12]
        backend = VirtualBackend(size=lambda: tuple(size), options=CapabilityOptions(
            color=0, unicode=False, reduced_motion=True))
        composer = TextInput('composer', '/s')
        stack = OverlayStack(owner())
        stack.open(Suggestions('slash', composer, (Suggestion('system', '/system', '/system '),)))
        seen = []
        loop = None
        def handle(event):
            if isinstance(event, ResizeEvent):
                size[:] = [event.width, event.height]
            elif stack.top:
                seen.append(stack.handle(event))
            else:
                seen.append(composer.handle(event))
            frame, view = paint(stack, size=tuple(size))
            loop.request_render(frame, cursor=view.cursor)
        with TerminalSession(backend) as session:
            loop = EventLoop(session, handle, clock=backend.clock)
            try:
                backend.inject_input(key('enter'), key('enter'), ResizeEvent(80, 24))
                loop.turn()
                self.assertEqual([action.kind for action in seen], ['inserted', 'submit'])
                self.assertEqual(composer.text, '/system ')
                writes = session.write_count
                loop.turn(block=True)
                self.assertEqual(session.write_count, writes)
                self.assertEqual(loop.timer_count, 0)
            finally:
                loop.close()


class OverlayExamplesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.old_path = sys.path[:]
        sys.path.insert(0, str(root / 'benchmarks'))
        cls.example = runpy.run_path(str(root / 'benchmarks/ui_overlays.py'))

    @classmethod
    def tearDownClass(cls):
        sys.path[:] = cls.old_path

    def test_selected_sizes_all_authored_states_are_bounded_and_preserve_draft(self):
        for size in ((120, 40), (80, 24), (40, 12)):
            for state in ('suggestions', 'form', 'help', 'review', 'stale'):
                result = self.example['example'](state, size, ascii_only=True)
                self.assertEqual(result['composer'], '/s' if state == 'suggestions' else '/system ')
                self.assertTrue(all(len(row) == size[0] and row[-1] == ' ' for row in result['rows']))
                self.assertTrue(all(ord(char) < 128 for row in result['rows'] for char in row))
                if state != 'suggestions':
                    self.assertEqual(result['trace'][:2], ['inserted', 'submit'])
                if state in ('review', 'stale'):
                    self.assertEqual(result['focus'], '@back')
                    self.assertTrue(any('[Help]' in row and '[PgUp/PgDn]' in row for row in result['rows']))

    def test_measurement_contract_has_bounded_visible_rows_and_no_output_sink(self):
        for workload in ('filter_256', 'form_error', 'long_review_page'):
            result = self.example['sample'](workload, (40, 12))
            self.assertGreater(result['event_to_buffer_us'], 0)
            self.assertLessEqual(result['visible_rows'], 6)
            self.assertEqual(result['cells'], 480)


if __name__ == '__main__':
    unittest.main()
