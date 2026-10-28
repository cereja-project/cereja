"""Inline feedback contracts, with explicit virtual time (not terminal acceptance)."""
import threading
import unittest

from cereja.ui.buffer import CellBuffer, Rect
from cereja.ui.editing import TextContent, TextInput, TextSelection, copy_action
from cereja.ui.collections import Row, SelectableList
from cereja.ui.events import EOFEvent, KeyEvent, PasteEvent, ProgressEvent, ResizeEvent, TimerEvent
from cereja.ui.feedback import ActivityIndicator, InlineStatus, ProgressBar
from cereja.ui.scheduling import EventLoop
from cereja.ui.terminal import CapabilityOptions, TerminalSession
from cereja.ui.testing import VirtualBackend


class FeedbackTest(unittest.TestCase):
    def setup_loop(self, **kwargs):
        backend = kwargs.pop('backend', VirtualBackend(size=(80, 8)))
        session = TerminalSession(backend)
        session.__enter__()
        loop = EventLoop(session, lambda event: None, clock=backend.clock, **kwargs)
        self.addCleanup(loop.close)
        return loop, backend

    def paint(self, widget, width=78, rect=None, **kwargs):
        frame = CellBuffer(80, 8)
        area = widget.paint(frame, rect or Rect(0, 0, width, 1), **kwargs)
        return frame, ''.join(c.text for c in frame.rows[0]), area

    def indicator(self, **kwargs):
        loop, backend = self.setup_loop(**kwargs)
        widget = ActivityIndicator(loop, 'job', 'Reading known input', active=True)
        loop.handler = widget.handle
        self.paint(widget)
        return widget, loop, backend

    def test_all_states_have_persistent_words_and_immediate_replacement(self):
        widget = InlineStatus('result', 'loading', 'Reading')
        for state, word in (('loading', 'Loading'), ('empty', 'Empty'), ('error', 'Error'),
                            ('success', 'Done'), ('warning', 'Warning'), ('canceled', 'Canceled')):
            widget.update(state, 'Useful next step')
            _, text, _ = self.paint(widget)
            self.assertIn(word + ': Useful next step', text)
            self.assertIn(word, widget.content.text)
        with self.assertRaises(ValueError):
            widget.update('unknown', 'Bad')
        self.assertEqual(widget.state, 'canceled')

    def test_message_admission_safe_canonical_whitespace_and_atomic_rejection(self):
        widget = InlineStatus('result', 'warning', '  input\tvalue  \n\nnext\x1b[31m')
        self.assertNotIn('\x1b', widget.content.text)
        self.assertIn('  input\tvalue  \n\nnext', widget.content.text)
        before = widget.content
        with self.assertRaises(ValueError):
            widget.update('error', 'x' * 65537)
        self.assertIs(widget.content, before)
        widget.update('warning', '  input\tvalue  \n\nnext\x1b[31m')
        self.assertIs(widget.content, before)
        _, text, _ = self.paint(widget)
        self.assertNotIn('\n', text)
        self.assertNotIn('next', text)

    def test_valid_progress_uses_integer_counts_without_claiming_operation_success(self):
        widget = ProgressBar('copy', 'Bytes copied', completed=3, total=8, reliable_total=True)
        self.assertTrue(widget.determinate)
        self.assertEqual(widget.percent, 37)
        _, text, _ = self.paint(widget)
        self.assertIn('3/8 (37%)', text)
        widget.update('Bytes copied', completed=8, total=8, reliable_total=True)
        self.assertEqual(widget.percent, 100)
        self.assertNotIn('Done', widget.content.text)
        self.assertNotIn('ETA', text)
        self.assertNotIn('Cancel', text)

    def test_invalid_or_untrusted_progress_never_has_percentage_or_bar(self):
        invalid = [(3, 8, False), (3, None, True), (0, 0, True), (9, 8, True),
                   (-1, 8, True), (True, 8, True), (3, False, True),
                   (float('nan'), 8, True), (3, float('inf'), True), (3.5, 8, True),
                   (2**64, 2**65, True)]
        for completed, total, reliable in invalid:
            with self.subTest(completed=completed, total=total, reliable=reliable):
                widget = ProgressBar('p', 'Observed bytes', completed=completed, total=total,
                                     reliable_total=reliable)
                _, text, _ = self.paint(widget)
                self.assertFalse(widget.determinate)
                self.assertIsNone(widget.percent)
                self.assertNotIn('%', text)
                self.assertNotIn('[#', text)
        self.assertIn('3 completed', ProgressBar('p', '', completed=3).content.text)

    def test_no_timer_before_visible_paint_or_for_unknown_activity(self):
        loop, _ = self.setup_loop()
        active = ActivityIndicator(loop, 'a', 'Known', active=True)
        unknown = ActivityIndicator(loop, 'b', 'Waiting')
        self.assertEqual(loop.timer_count, 0)
        self.paint(unknown)
        self.assertEqual(loop.timer_count, 0)
        self.paint(active, rect=Rect(0, 10, 20, 1))
        self.assertEqual(loop.timer_count, 0)
        self.paint(active)
        self.assertEqual(loop.timer_count, 1)

    def test_motion_off_reduced_plain_do_not_allocate_animation_timers(self):
        for mode in ('off', 'reduced', 'plain', 'no-cursor'):
            backend = VirtualBackend(size=(80, 8))
            if mode in ('plain', 'no-cursor'):
                backend = VirtualBackend(input_interactive=False, output_interactive=False)
            if mode == 'no-cursor':
                backend = VirtualBackend(options=CapabilityOptions(cursor=False))
            loop, _ = self.setup_loop(backend=backend)
            if mode == 'reduced':
                loop.set_reduced_motion(True)
            widget = ActivityIndicator(loop, 'a', 'Known', active=True, motion=mode != 'off')
            _, text, _ = self.paint(widget)
            self.assertIn('Loading: Known', text)
            self.assertEqual(loop.timer_count, 0)
            self.assertIsNone(loop.next_deadline)

    def test_color_unicode_and_motion_are_independent(self):
        loop, backend = self.setup_loop(backend=VirtualBackend(size=(80, 8),
            options=CapabilityOptions(color=0, unicode=False)))
        self.assertFalse(loop.session.capabilities.plain)
        self.assertEqual(loop.session.capabilities.color_depth, 0)
        widget = ActivityIndicator(loop, 'a', 'Known', active=True)
        self.paint(widget)
        self.assertEqual(loop.timer_count, 1)
        self.assertTrue(all(ord(c) < 128 for c in self.paint(widget)[1]))
        backend.advance(.125)
        loop.handler = widget.handle
        loop.turn()
        self.assertEqual(loop.metrics.timer_events, 1)

    def test_dots_reserve_three_cells_and_content_identity_revision_do_not_tick(self):
        loop, backend = self.setup_loop()
        widget = ActivityIndicator(loop, 'a', '  source\tvalue  ', active=True, kind='dots')
        loop.handler = widget.handle
        first = self.paint(widget)[1]
        canonical = widget.content
        selection = TextSelection(canonical, 0, len(canonical.text))
        for _ in range(5):
            backend.advance(.125)
            loop.turn()
            text = self.paint(widget)[1]
            self.assertEqual(text.index('Loading'), first.index('Loading'))
            self.assertIs(widget.content, canonical)
            self.assertEqual(copy_action(selection).selection.text, canonical.text)

    def test_completion_cancel_hide_dispose_release_deadlines_and_owner(self):
        for action in ('complete', 'cancel', 'hide', 'dispose', 'clip', 'off'):
            widget, loop, _ = self.indicator()
            if action == 'complete':
                widget.update('success', 'Read complete')
            elif action == 'cancel':
                widget.update('canceled', 'Stopped by caller')
            elif action == 'hide':
                widget.set_visible(False)
            elif action == 'dispose':
                widget.close()
            elif action == 'clip':
                self.paint(widget, clip=Rect(0, 3, 10, 1))
            else:
                widget.set_motion(False)
            self.assertEqual(loop.timer_count, 0, action)
            self.assertIsNone(loop.next_deadline, action)
            self.assertEqual(loop.cancel_owner(widget.owner), 0)
            widget.close()
            widget.close()

    def test_global_motion_switch_cancels_and_explicit_repaint_can_resume(self):
        widget, loop, backend = self.indicator()
        old = widget.timer_id
        loop.set_reduced_motion(True)
        self.assertFalse(loop.has_timer(old))
        self.assertFalse(widget.handle(TimerEvent(widget.owner, old, .125, .125)))
        self.paint(widget)
        self.assertEqual(loop.timer_count, 0)
        loop.set_reduced_motion(False)
        self.paint(widget)
        self.assertEqual(loop.timer_count, 1)
        self.assertNotEqual(widget.timer_id, old)
        self.assertFalse(widget.handle(TimerEvent(widget.owner, old, .125, .125)))
        backend.advance(.125)
        loop.turn()

    def test_local_and_low_bandwidth_rates_skip_obsolete_frames(self):
        for low, interval in ((False, .125), (True, .5)):
            widget, loop, backend = self.indicator(low_bandwidth=low)
            self.assertEqual(loop.indicator_interval, interval)
            self.assertEqual(loop.next_deadline, interval)
            backend.advance(interval - .001)
            loop.turn()
            self.assertEqual(loop.metrics.timer_events, 0)
            backend.advance(10)
            loop.turn()
            self.assertEqual(loop.metrics.timer_events, 1)
            self.assertAlmostEqual(loop.next_deadline, backend.clock() + interval)

    def test_hidden_or_static_views_have_zero_periodic_work(self):
        for active in (False, True):
            loop, backend = self.setup_loop()
            widget = ActivityIndicator(loop, 'a', 'Known', active=active)
            loop.handler = widget.handle
            self.paint(widget)
            widget.set_visible(False)
            before = loop.metrics
            for _ in range(20):
                backend.advance(10)
                loop.turn()
            self.assertEqual(loop.metrics.timer_events, before.timer_events)
            self.assertEqual(loop.metrics.renders, before.renders)
            self.assertEqual(loop.metrics.writes, before.writes)
            self.assertEqual(loop.metrics.flushes, before.flushes)

    def test_dead_terminal_cleans_timers_and_disposal_remains_idempotent(self):
        widget, loop, backend = self.indicator()
        backend.inject_input(EOFEvent())
        loop.turn()
        self.assertTrue(loop.stopped)
        self.assertEqual(loop.timer_count, 0)
        widget.close()
        widget.close()

    def test_timer_limit_retains_truthful_static_state_and_retries_on_paint(self):
        loop, _ = self.setup_loop()
        timers = [loop.call_later(100, owner='other') for _ in range(1024)]
        widget = ActivityIndicator(loop, 'a', 'Known', active=True)
        _, text, _ = self.paint(widget)
        self.assertIn('Loading: Known', text)
        self.assertEqual(widget.motion_notice, 'Animation timer capacity unavailable')
        loop.cancel_timer(timers[0])
        self.paint(widget)
        self.assertIsNotNone(widget.timer_id)
        self.assertEqual(widget.motion_notice, '')

    def test_multiple_instances_with_same_content_id_have_distinct_timer_owners(self):
        loop, _ = self.setup_loop()
        a = ActivityIndicator(loop, 'same', 'A', active=True)
        b = ActivityIndicator(loop, 'same', 'B', active=True)
        self.paint(a)
        self.paint(b)
        self.assertNotEqual(a.owner, b.owner)
        a.close()
        self.assertEqual(loop.timer_count, 1)
        b.close()

    def test_aggregate_timers_preserve_ordered_keys_paste_resize_and_coalescing(self):
        loop, backend = self.setup_loop()
        widgets = [ActivityIndicator(loop, str(i), 'Known', active=True) for i in range(130)]
        route = {}
        seen = []
        for w in widgets:
            self.paint(w)
            route[w.owner] = w
        def handle(event):
            if type(event) is TimerEvent:
                route[event.owner].handle(event)
            else:
                seen.append(event)
        loop.handler = handle
        for event in (KeyEvent('a', 'a'), PasteEvent('abc'), KeyEvent('b', 'b'), ResizeEvent(40, 12)):
            backend.inject_input(event)
        loop.post(ProgressEvent('job', 1, 10))
        loop.post(ProgressEvent('job', 2, 10))
        backend.advance(.125)
        loop.turn()
        self.assertEqual(seen, [KeyEvent('a', 'a'), PasteEvent('abc'), KeyEvent('b', 'b'),
                                ResizeEvent(40, 12), ProgressEvent('job', 2, 10)])
        self.assertEqual(loop.metrics.timer_events, 64)
        for _ in range(2):
            loop.turn()
        self.assertEqual(loop.metrics.timer_events, 130)
        for w in widgets:
            w.close()
        self.assertEqual(loop.timer_count, 0)

    def test_ticks_do_not_change_editor_collection_focus_selection_or_scroll(self):
        widget, loop, backend = self.indicator()
        editor = TextInput('composer', '/inspect draft')
        editor.set_selection(1, 4)
        content = TextContent('row', 1, '  source\ttext  \n\n')
        rows = SelectableList('rows', [Row(str(i), (str(i),), content) for i in range(8)])
        rows.select('4')
        rows.set_text_selection('4', 0, len(content.text))
        rows.scroll(2)
        before = (editor.content, editor.selection, rows.selected, rows.text_selection, rows.scroll_y)
        for _ in range(4):
            backend.advance(.125)
            loop.turn()
            self.paint(widget, width=8)
        self.assertEqual(before, (editor.content, editor.selection, rows.selected, rows.text_selection, rows.scroll_y))
        self.assertFalse(widget.handle(KeyEvent('c', modifiers=frozenset({'ctrl'}))))

    def test_clipping_changes_only_region_and_clears_shorter_replacement(self):
        widget = InlineStatus('a', 'error', 'long message')
        frame = CellBuffer(30, 3)
        frame.draw_text(0, 0, 'x' * 30)
        rect = Rect(4, 0, 20, 1)
        widget.paint(frame, rect)
        widget.update('success', 'ok')
        dirty = widget.paint(frame, rect)
        self.assertEqual(dirty, rect)
        text = ''.join(c.text for c in frame.rows[0])
        self.assertEqual(text[:4], 'xxxx')
        self.assertEqual(text[4:24], 'Done: ok' + ' ' * 12)
        self.assertEqual(text[24:], 'xxxxxx')

    def test_ui_thread_mutations_rejected(self):
        widget, _, _ = self.indicator()
        errors = []
        def other():
            for call in (lambda: widget.update('success', 'Done'), lambda: widget.set_visible(False),
                         widget.close, lambda: self.paint(widget)):
                try:
                    call()
                except RuntimeError:
                    errors.append(True)
        thread = threading.Thread(target=other)
        thread.start()
        thread.join()
        self.assertEqual(len(errors), 4)

    def test_real_pending_data_survives_decorative_coalescing_then_motion_off(self):
        loop, backend = self.setup_loop()
        first = CellBuffer(80, 8)
        loop.request_render(first)
        loop.turn()
        real = CellBuffer(80, 8)
        real.draw_text(0, 0, 'Progress: 3/8')
        loop.request_render(real)
        loop.request_render(real, decorative=True)
        loop.set_reduced_motion(True)
        backend.advance(1)
        loop.turn()
        self.assertEqual(loop.metrics.renders, 2)
        self.assertIn('Progress: 3/8', ''.join(c.text for c in backend.cells[0]))

    def test_spinner_padding_visible_but_marker_clipped_needs_no_timer(self):
        widget, loop, _ = self.indicator()
        self.paint(widget, clip=Rect(1, 0, 50, 1))
        self.assertEqual(loop.timer_count, 0)

    def test_rejected_activity_update_preserves_current_timer_and_content(self):
        widget, loop, _ = self.indicator()
        old = widget.content, widget.timer_id
        for call in (lambda: widget.update('success', 'Done', active=True),
                     lambda: widget.update('loading', 'x' * 65537, active=True),
                     lambda: widget.set_motion('yes')):
            with self.assertRaises((ValueError, TypeError)):
                call()
            self.assertEqual((widget.content, widget.timer_id), old)
        self.assertEqual(loop.timer_count, 1)

    def test_real_progress_plain_updates_without_animation_history_or_controls(self):
        loop, backend = self.setup_loop(backend=VirtualBackend(
            input_interactive=False, output_interactive=False))
        activity = ActivityIndicator(loop, 'a', 'Known', active=True)
        progress = ProgressBar('p', 'Measured', completed=3, total=8, reliable_total=True)
        frame = CellBuffer(80, 8)
        activity.paint(frame, Rect(0, 0, 79, 1))
        progress.paint(frame, Rect(0, 1, 79, 1))
        loop.request_render(frame)
        loop.turn()
        writes = loop.metrics.writes
        before = backend.output
        for _ in range(10):
            backend.advance(1)
            loop.turn()
        self.assertEqual(backend.output, before)
        self.assertEqual(loop.timer_count, 0)
        progress.update('Measured', completed=4, total=8, reliable_total=True)
        progress.paint(frame, Rect(0, 1, 79, 1))
        loop.request_render(frame)
        loop.turn()
        self.assertEqual(loop.metrics.writes, writes + 1)
        self.assertIn('4/8 (50%)', backend.output)
        self.assertNotIn('\x1b', backend.output)

    def test_output_loss_or_callback_failure_clears_animation_deadlines(self):
        for fault in ('pipe', 'handler'):
            backend = VirtualBackend(size=(80, 8),
                failures={'write': BrokenPipeError()} if fault == 'pipe' else None)
            loop, backend = self.setup_loop(backend=backend)
            widget = ActivityIndicator(loop, 'a', 'Known', active=True)
            frame, _, _ = self.paint(widget)
            if fault == 'pipe':
                loop.request_render(frame)
                loop.turn()
            else:
                def fail(event):
                    raise RuntimeError('callback failed')
                loop.handler = fail
                backend.advance(.125)
                with self.assertRaisesRegex(RuntimeError, 'callback failed'):
                    loop.turn()
            self.assertTrue(loop.stopped)
            self.assertEqual(loop.timer_count, 0)
            self.assertIsNone(loop.next_deadline)
            widget.close()

    def test_animated_redraw_keeps_editor_cursor_and_focus_owner(self):
        from cereja.ui.focus import FocusManager, FocusScope, FocusTarget
        loop, backend = self.setup_loop()
        editor = TextInput('composer', '/inspect')
        owners = FocusManager(FocusScope('root', (FocusTarget('composer'),)))
        widget = ActivityIndicator(loop, 'a', 'Known', active=True)
        frame = CellBuffer(80, 8)
        widget.paint(frame, Rect(0, 0, 79, 1))
        cursor = editor.paint(frame, Rect(0, 7, 79, 1)).cursor
        loop.request_render(frame, cursor=cursor)
        loop.turn()
        def handle(event):
            if widget.handle(event):
                widget.paint(frame, Rect(0, 0, 79, 1))
                loop.request_render(frame, cursor=cursor, decorative=True)
        loop.handler = handle
        backend.advance(.125)
        loop.turn()
        self.assertEqual(editor.text, '/inspect')
        self.assertEqual(owners.focused, 'composer')
        self.assertEqual(backend.cell_frames[-1][7], backend.cell_frames[0][7])
        self.assertIn('/inspect', ''.join(c.text for c in backend.cells[7]))


if __name__ == '__main__':
    unittest.main()
