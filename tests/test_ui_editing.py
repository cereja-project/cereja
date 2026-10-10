"""UI-09 requirements: canonical text, keyboard ownership and scope restoration."""

from pathlib import Path
import runpy
import sys
import threading
import unittest

from cereja.ui.buffer import CellBuffer, Rect
from cereja.ui.events import KeyEvent, PasteEvent, ResizeEvent
from cereja.ui.editing import TextContent, TextSelection, TextInput, copy_action
from cereja.ui.focus import FocusTarget, FocusScope, FocusManager, focus_markers
from cereja.ui.scheduling import EventLoop
from cereja.ui.terminal import TerminalSession
from cereja.ui.testing import VirtualBackend
from cereja.ui.text import TextPolicy


def key(name, text='', *modifiers, repeat=1):
    return KeyEvent(name, text, frozenset(modifiers), repeat)


class EditingTest(unittest.TestCase):
    def test_grapheme_motion_selection_and_deletion(self):
        field = TextInput('draft', 'a\u0301界👩\u200d💻🇧🇷q')
        field.handle(key('left'))
        self.assertEqual(field.caret, 8)
        field.handle(key('left', '', 'shift'))
        self.assertEqual((field.selection.start, field.selection.end), (6, 8))
        self.assertEqual(field.selection.text, '🇧🇷')
        field.handle(key('backspace'))
        self.assertEqual(field.text, 'a\u0301界👩\u200d💻q')
        field.handle(key('backspace'))
        self.assertEqual(field.text, 'a\u0301界q')
        field.handle(key('home'))
        field.handle(key('delete'))
        self.assertEqual(field.text, '界q')
        self.assertEqual(field.caret, 0)

    def test_selection_direction_collapse_and_draft_ends(self):
        field = TextInput('draft', 'abcdef')
        field.set_selection(5, 2)
        field.handle(key('left'))
        self.assertEqual(field.caret, 2)
        self.assertIsNone(field.selection)
        field.set_selection(2, 5)
        field.handle(key('right'))
        self.assertEqual(field.caret, 5)
        field.handle(key('home', '', 'shift'))
        self.assertEqual(field.selection.text, 'abcde')
        field.handle(key('end', '', 'shift'))
        self.assertEqual(field.selection.text, 'f')

    def test_edit_resegments_at_join_without_splitting_combining_cluster(self):
        field = TextInput('draft', '\u0301x')
        field.move(0)
        field.handle(key('a', 'a'))
        self.assertEqual(field.text, 'a\u0301x')
        self.assertEqual(field.caret, 2)
        field.handle(key('backspace'))
        self.assertEqual(field.text, 'x')
        field = TextInput('draft', '👩💻')
        field.move(1)
        field.insert('\u200d')
        self.assertEqual(field.text, '👩\u200d💻')
        self.assertEqual(field.caret, 3)

    def test_printable_q_slash_suggestion_and_paste_never_submit(self):
        field = TextInput('draft')
        for event in (key('q', 'q'), PasteEvent('/system\n/download')):
            self.assertEqual(field.handle(event).kind, 'changed')
        self.assertEqual(field.handle(key('enter')).kind, 'submit')
        self.assertEqual(field.text, 'q/system\n/download')
        field.set_selection(0, len(field.text))
        self.assertEqual(field.insert('/tree ').kind, 'changed')
        self.assertEqual(field.text, '/tree ')
        self.assertEqual(field.caret, 6)

    def test_safe_paste_and_rejected_expansion_preserve_all_edit_state(self):
        field = TextInput('draft', 'keep', max_bytes=16)
        field.set_selection(1, 3)
        before = (field.content, field.caret, field.selection)
        action = field.handle(PasteEvent('\x1b' * 8))
        self.assertEqual(action.kind, 'rejected')
        self.assertTrue(action.reason)
        self.assertEqual((field.content, field.caret, field.selection), before)
        field.set_selection(0, 4)
        field.handle(PasteEvent('\x1b\x07\r\x7f'))
        self.assertEqual(field.text, r'\x1b\x07\x0d\x7f')
        self.assertFalse(any(ord(char) < 32 for char in field.text))

    def test_canonical_copy_preserves_source_whitespace_at_every_size(self):
        source = '  ```py\n\t  x = 1  \n\n  ```  \n'
        field = TextInput('draft', source)
        field.handle(key('a', '', 'ctrl'))
        for width, ascii_only in ((120, False), (80, False), (40, True), (3, True)):
            frame = CellBuffer(width, 2, policy=TextPolicy(ascii_only=ascii_only))
            field.paint(frame, Rect(0, 0, width - 1, 1), focused=True)
            action = field.handle(key('c', '', 'ctrl'))
            self.assertEqual(action.kind, 'copy')
            self.assertEqual(action.selection.text, source)
            self.assertEqual(action.selection.content.identity, 'draft')
            self.assertEqual(action.selection.content.revision, 0)
        self.assertEqual(field.text, source)

    def test_selection_pins_immutable_safe_revision_and_logical_range(self):
        old = TextContent('snippet', 7, '  a\t\n\n界  \x1b')
        selected = TextSelection(old, 2, 8)
        new = TextContent('snippet', 8, 'replacement')
        self.assertEqual(selected.text, 'a\t\n\n界 ')
        self.assertEqual(selected.content.revision, 7)
        self.assertEqual(new.revision, 8)
        self.assertIn(r'\x1b', old.text)
        with self.assertRaises(ValueError):
            TextSelection(TextContent('x', 1, 'a\u0301'), 0, 1)
        with self.assertRaises(ValueError):
            TextSelection(old, -1, 2)

    def test_copy_requests_without_acknowledgement_preserve_state(self):
        field = TextInput('draft', 'chosen')
        field.set_selection(0, 6)
        before = (field.content, field.caret, field.selection)
        for _ in range(3):
            action = field.handle(key('c', '', 'ctrl'))
            self.assertEqual(action.kind, 'copy')
            # A consumer may report unavailable/failed. No transport or exit is
            # called by the toolkit, and another key still requests the same copy.
            self.assertIsNotNone(action.selection)
            self.assertEqual((field.content, field.caret, field.selection), before)
            self.assertEqual(field.handle(key('c', '', 'ctrl')).kind, 'copy')
        self.assertEqual(copy_action(None).kind, 'exit')
        self.assertEqual(copy_action(TextSelection(field.content, 0, 0)).kind, 'exit')

    def test_only_current_key_owner_can_request_copy(self):
        draft = TextInput('draft', 'saved')
        draft.set_selection(0, 5)
        result = TextInput('result', 'navigation')
        manager = FocusManager(FocusScope('base', (FocusTarget('draft'), FocusTarget('result'))))
        manager.traverse()
        controls = {'draft': draft, 'result': result}
        self.assertEqual(controls[manager.focused].handle(key('c', '', 'ctrl')).kind, 'exit')
        self.assertEqual(draft.selection.text, 'saved')
        self.assertEqual(focus_markers(False, True), ' *')

    def test_repeat_is_bounded_and_atomic(self):
        field = TextInput('draft', 'ab', max_bytes=8)
        self.assertEqual(field.handle(key('x', 'x', repeat=10**12)).kind, 'rejected')
        self.assertEqual(field.text, 'ab')
        field.handle(key('x', 'x', repeat=3))
        self.assertEqual(field.text, 'abxxx')
        field.handle(key('left', repeat=10**12))
        self.assertEqual(field.caret, 0)
        field.handle(key('delete', repeat=2))
        self.assertEqual(field.text, 'xxx')

    def test_empty_paste_preserves_selection_and_native_altgr_stays_text(self):
        field = TextInput('draft', 'saved')
        field.set_selection(0, 5)
        before = field.content, field.caret, field.selection
        self.assertEqual(field.handle(PasteEvent('')).kind, 'handled')
        self.assertEqual((field.content, field.caret, field.selection), before)
        field.handle(key('€', '€', 'ctrl', 'alt'))
        self.assertEqual(field.text, '€')
        field.handle(key('€', '€', 'ctrl', 'alt', 'shift'))
        self.assertEqual(field.text, '€€')

    def test_selection_collapse_reports_change_and_revisions_advance_on_edits(self):
        field = TextInput('draft', 'abc')
        field.set_selection(0, 3)
        pinned = field.selection
        self.assertEqual(field.handle(key('left')).kind, 'changed')
        field.insert('x')
        self.assertEqual(field.content.revision, 1)
        self.assertEqual(pinned.text, 'abc')
        field.move(len(field.text))
        self.assertEqual(field.handle(key('delete')).kind, 'handled')
        self.assertEqual(field.content.revision, 1)

    def test_unknown_modified_keys_do_not_rewrite_input(self):
        field = TextInput('draft', 'q')
        for event in (key('z', 'z', 'ctrl'), key('x', 'x', 'alt'),
                      key('left', '', 'ctrl'), key('f1'), ResizeEvent(3, 1)):
            self.assertEqual(field.handle(event).kind, 'unhandled')
        self.assertEqual(field.text, 'q')

    def test_viewport_reveals_caret_without_slicing_graphemes_or_mutating_draft(self):
        field = TextInput('draft', 'abc界👩\u200d💻' + 'z' * 2000)
        field.set_selection(3, len(field.text))
        before = (field.content, field.caret, field.selection)
        for width in (40, 9, 4, 3, 0, 120):
            frame = CellBuffer(width, 2)
            view = field.paint(frame, Rect(0, 0, width, 1), focused=True)
            if width > 2:
                self.assertTrue(view.cursor.visible)
                self.assertTrue(2 <= view.cursor.x < width)
            else:
                self.assertFalse(view.cursor.visible)
            self.assertEqual((field.content, field.caret, field.selection), before)
        field.move(3)
        frame = CellBuffer(3, 1)
        view = field.paint(frame, Rect(0, 0, 3, 1), focused=True)
        self.assertEqual(view.cursor.x, 2)
        self.assertEqual(frame.cell(2, 0).text, ' ')

    def test_multiline_paste_active_line_and_tabs_preserve_canonical_text(self):
        field = TextInput('draft', 'head\n\t界\n')
        field.move(7)
        frame = CellBuffer(8, 1)
        view = field.paint(frame, Rect(0, 0, 8, 1), focused=True)
        self.assertEqual(view.line_start, 5)
        self.assertTrue(view.cursor.visible)
        field.move(len(field.text))
        view = field.paint(frame, Rect(0, 0, 8, 1), focused=True)
        self.assertEqual(view.line_start, 8)
        self.assertEqual(field.text, 'head\n\t界\n')

    def test_ascii_fallback_display_does_not_change_logical_copy(self):
        field = TextInput('draft', '界👩\u200d💻')
        field.handle(key('a', '', 'ctrl'))
        frame = CellBuffer(8, 1, policy=TextPolicy(ascii_only=True))
        view = field.paint(frame, Rect(0, 0, 8, 1), focused=True)
        self.assertEqual(view.cursor.x, 4)
        self.assertEqual(''.join(cell.text for cell in frame.rows[0])[:4], '>*??')
        self.assertEqual(field.selection.text, '界👩\u200d💻')

    def test_paint_clips_caret_and_damage_to_visible_ancestor(self):
        field = TextInput('draft', '12345678')
        frame = CellBuffer(12, 2)
        frame.draw_text(0, 0, 'outside!')
        view = field.paint(frame, Rect(2, 0, 8, 1), clip=Rect(5, 0, 3, 1), focused=True)
        self.assertTrue(5 <= view.cursor.x < 8)
        self.assertEqual(frame.cell(0, 0).text, 'o')
        self.assertEqual(frame.cell(1, 0).text, 'u')

    def test_mutation_from_worker_is_rejected(self):
        field = TextInput('draft', 'keep')
        errors = []
        def worker():
            try:
                field.insert('x')
            except RuntimeError as error:
                errors.append(error)
        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        self.assertEqual(len(errors), 1)
        self.assertEqual(field.text, 'keep')

    def test_constructor_and_selection_validation(self):
        for kwargs in ({'max_bytes': 0}, {'max_bytes': True}):
            with self.assertRaises((TypeError, ValueError)):
                TextInput('x', **kwargs)
        with self.assertRaises(ValueError):
            TextInput('x', 'abc', max_bytes=2)
        with self.assertRaises(ValueError):
            TextContent('', 0, 'x')
        with self.assertRaises(ValueError):
            TextContent('x', -1, 'x')
        field = TextInput('x', 'a\u0301')
        with self.assertRaises(ValueError):
            field.move(1)


class FocusTest(unittest.TestCase):
    def base(self):
        return FocusScope('base', (FocusTarget('draft'), FocusTarget('header'),
                                  FocusTarget('disabled', enabled=False),
                                  FocusTarget('hidden', visible=False), FocusTarget('help')))

    def test_forward_backward_wrap_skip_and_distinct_markers(self):
        manager = FocusManager(self.base())
        self.assertEqual(manager.focused, 'draft')
        self.assertEqual(manager.traverse(), 'header')
        self.assertEqual(manager.traverse(), 'help')
        self.assertEqual(manager.traverse(), 'draft')
        self.assertEqual(manager.traverse(backward=True), 'help')
        self.assertEqual(focus_markers(True, False), '> ')
        self.assertEqual(focus_markers(False, True), ' *')
        self.assertEqual(focus_markers(True, True), '>*')

    def test_top_scope_contains_traversal_and_restores_invoker(self):
        manager = FocusManager(self.base())
        manager.focus('header')
        manager.push(FocusScope('form', (FocusTarget('path'), FocusTarget('back'))))
        manager.focus('back')
        manager.push(FocusScope('help', (FocusTarget('close'),)))
        self.assertEqual(manager.traverse(), 'close')
        self.assertEqual(manager.pop(), 'back')
        self.assertEqual(manager.pop(), 'header')
        self.assertEqual(manager.scope.identity, 'base')
        with self.assertRaises(ValueError):
            manager.pop()

    def test_removed_invoker_falls_next_then_previous_then_new(self):
        manager = FocusManager(self.base())
        manager.focus('header')
        manager.push(FocusScope('overlay', (FocusTarget('close'),)))
        manager.update(FocusScope('base', (FocusTarget('draft'), FocusTarget('help'))))
        self.assertEqual(manager.focused, 'close')
        self.assertEqual(manager.pop(), 'help')
        manager.update(FocusScope('base', (FocusTarget('draft'),)))
        self.assertEqual(manager.focused, 'draft')
        manager.update(FocusScope('base', ()))
        self.assertIsNone(manager.focused)
        manager.update(FocusScope('base', (FocusTarget('empty'),)))
        self.assertEqual(manager.focused, 'empty')

    def test_traversal_does_not_modify_editing_or_navigation_state(self):
        field = TextInput('draft', 'unchanged')
        field.set_selection(2, 5)
        selected_row, inspection = 'node-7', 'revision-3'
        before = (field.content, field.caret, field.selection, selected_row, inspection)
        manager = FocusManager(self.base())
        manager.push(FocusScope('help', (FocusTarget('close'),)))
        manager.pop()
        self.assertEqual((field.content, field.caret, field.selection, selected_row, inspection), before)

    def test_duplicates_unavailable_target_and_depth_are_explicit(self):
        with self.assertRaises(ValueError):
            FocusScope('x', (FocusTarget('same'), FocusTarget('same')))
        manager = FocusManager(self.base(), max_depth=2)
        with self.assertRaises(ValueError):
            manager.focus('hidden')
        manager.push(FocusScope('form', ()))
        with self.assertRaises(ValueError):
            manager.push(FocusScope('nested', ()))
        with self.assertRaises(ValueError):
            manager.push(self.base())


class VirtualKeyboardTest(unittest.TestCase):
    def test_selected_sizes_no_color_ascii_reduced_motion_and_idle(self):
        from cereja.ui.terminal import CapabilityOptions
        for size in ((120, 40), (80, 24), (40, 12)):
            for ascii_only in (False, True):
                backend = VirtualBackend(size=size, options=CapabilityOptions(
                    color=0, unicode=not ascii_only, reduced_motion=True))
                field = TextInput('draft', 'a\u0301界👩\u200d💻')
                field.set_selection(0, len(field.text))
                with TerminalSession(backend) as session:
                    loop = EventLoop(session, lambda event: None, clock=backend.clock)
                    try:
                        frame = CellBuffer(*size, policy=TextPolicy(ascii_only=ascii_only))
                        view = field.paint(frame, Rect(0, size[1] - 1, size[0] - 1, 1), focused=True)
                        loop.request_render(frame, cursor=view.cursor)
                        loop.turn()
                        self.assertTrue(view.cursor.visible)
                        self.assertEqual(field.selection.text, 'a\u0301界👩\u200d💻')
                        writes = session.write_count
                        loop.turn(block=True)
                        self.assertEqual(session.write_count, writes)
                        self.assertEqual(loop.timer_count, 0)
                        self.assertEqual(loop.metrics.renders, 1)
                    finally:
                        loop.close()

    def test_ordered_paste_edit_focus_overlay_resize_to_frame_and_idle(self):
        size = [40, 12]
        backend = VirtualBackend(size=lambda: tuple(size))
        draft = TextInput('draft', 'a\u0301👩\u200d💻')
        other = TextInput('other')
        fields = {'draft': draft, 'other': other}
        focus = FocusManager(FocusScope('base', (FocusTarget('draft'), FocusTarget('other'))))
        actions = []
        loop = None
        def handle(event):
            if isinstance(event, ResizeEvent):
                size[:] = [event.width, event.height]
            elif isinstance(event, KeyEvent) and event.key == 'tab':
                focus.traverse(backward='shift' in event.modifiers)
            else:
                actions.append(fields[focus.focused].handle(event))
            frame = CellBuffer(*size)
            view = draft.paint(frame, Rect(0, max(0, size[1] - 1), max(0, size[0] - 1),
                                           min(1, size[1])), focused=focus.focused == 'draft')
            loop.request_render(frame, cursor=view.cursor)
        with TerminalSession(backend) as session:
            loop = EventLoop(session, handle, clock=backend.clock)
            self.addCleanup(loop.close)
            for event in (key('left', '', 'shift'), key('c', '', 'ctrl'),
                          key('tab'), PasteEvent('/tree\n'), key('tab', '', 'shift'),
                          ResizeEvent(4, 1)):
                backend.inject_input(event)
            loop.turn()
            self.assertEqual(actions[1].kind, 'copy')
            self.assertEqual(actions[1].selection.text, '👩\u200d💻')
            self.assertEqual(other.text, '/tree\n')
            self.assertEqual(draft.text, 'a\u0301👩\u200d💻')
            self.assertEqual(focus.focused, 'draft')
            self.assertEqual(loop.metrics.renders, 1)
            renders = loop.metrics.renders
            loop.turn()
            self.assertEqual(loop.metrics.renders, renders)
            self.assertEqual(loop.timer_count, 0)


class EditingExampleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.old_path = sys.path[:]
        sys.path.insert(0, str(root / 'benchmarks'))
        cls.example = runpy.run_path(str(root / 'benchmarks/ui_editing.py'))

    @classmethod
    def tearDownClass(cls):
        sys.path[:] = cls.old_path

    def test_example_is_source_faithful_and_keeps_reserved_column(self):
        for size in ((120, 40), (80, 24), (40, 12)):
            result = self.example['example'](size, ascii_only=True)
            self.assertEqual(result['copy_text'], '👩\u200d💻')
            self.assertEqual(result['draft'], 'a\u0301/synthetic\n\tvalue  ')
            self.assertEqual(result['focus'], 'draft')
            self.assertTrue(result['cursor_visible'])
            self.assertTrue(all(row[-1] == ' ' for row in result['rows']))
            self.assertTrue(all(ord(char) < 128 for row in result['rows'] for char in row))

    def test_measurement_includes_exactly_one_acknowledged_frame(self):
        result = self.example['sample']('unicode', (40, 12))
        self.assertEqual((result['renders'], result['flushes']), (1, 1))
        self.assertGreater(result['input_to_frame_ms'], result['handler_to_request_ms'])
        self.assertGreaterEqual(result['scheduler_sleep_ms'], 0)


if __name__ == '__main__':
    unittest.main()
