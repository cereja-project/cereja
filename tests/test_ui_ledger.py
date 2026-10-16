"""Ledger application contracts (virtual UI, no human acceptance claim)."""
import threading
import time
import unittest
from unittest.mock import patch

from cereja.ui.events import KeyEvent, PasteEvent, ResizeEvent
from cereja.ui.overlays import ParameterForm
from cereja.ui.terminal import TerminalSession
from cereja.ui.testing import VirtualBackend
from cereja.ledger.app import Ledger
from cereja.ledger.catalogue import COMMANDS, parse_command
from cereja.ledger.model import Results


class GrammarTest(unittest.TestCase):
    def test_explicit_registry_and_rejection(self):
        self.assertEqual(tuple(c.name for c in COMMANDS), (
            'home', 'system', 'tree', 'context', 'compress', 'download',
            'examples', 'tools', 'diagnostics', 'help'))
        for text in ('print(1)', '/unknown', '/system; whoami', '/home\n/help',
                     '/download https://user:secret@example.test', '/examples bogus'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_command(text)
        self.assertEqual(parse_command('/examples progress').arguments, ('progress',))


class RetentionTest(unittest.TestCase):
    def test_oldest_completed_eviction_and_active_identity(self):
        results = Results(max_completed=2, max_bytes=1024, block_bytes=256)
        first = results.append('/home', 'one')
        results.select(first.identity)
        active = results.append('/examples', 'working', active=True)
        results.append('/tools', 'two')
        results.append('/help', 'three')
        self.assertNotIn(first, results.blocks)
        self.assertIn(active, results.blocks)
        self.assertEqual(results.selected, active.identity)
        self.assertEqual(results.omitted, 1)
        self.assertFalse(results.follow_latest)

    def test_bytes_and_truncation(self):
        results = Results(max_completed=20, max_bytes=512, block_bytes=256)
        results.append('/home', '界' * 500)
        self.assertTrue(results.blocks[0].truncated)
        for _ in range(10):
            results.append('/home', 'x' * 220)
        self.assertLessEqual(results.retained_bytes, 512)
        self.assertGreater(results.omitted, 0)

    def test_pinned_revision_is_counted_and_removed_with_its_block(self):
        results = Results(max_completed=1, max_bytes=1024, block_bytes=256)
        block = results.append('/examples', '  original\ttext  \n', active=True)
        results.select_text()
        before = results.retained_bytes
        results.finish(block, 'Succeeded', 'new result')
        self.assertEqual(block.selection.text, '  original\ttext  \n')
        self.assertGreater(results.retained_bytes, before)
        results.append('/home', 'next')
        self.assertNotIn(block, results.blocks)
        self.assertEqual(results.current.command, '/home')

    def test_selection_and_scroll_are_not_result_insertion_state(self):
        results = Results()
        first = results.append('/home', 'first')
        results.select(first.identity)
        first.anchor = 3
        results.append('/tools', 'new')
        self.assertIs(results.current, first)
        self.assertEqual(first.anchor, 3)
        results.latest()
        newer = results.append('/help', 'latest')
        self.assertIs(results.current, newer)

    def test_default_count_cap_is_independent_of_byte_cap(self):
        results = Results()
        for _ in range(30):
            results.append('/home', 'small')
        self.assertEqual(len(results.blocks), 20)
        self.assertEqual(results.omitted, 10)
        self.assertLess(results.retained_bytes, results.max_bytes)


class LedgerTest(unittest.TestCase):
    def app(self, size=(80, 24), options=None, **kwargs):
        backend = VirtualBackend(size=size, options=options)
        session = TerminalSession(backend)
        session.__enter__()
        self.addCleanup(session.close)
        app = Ledger(session, **kwargs)
        self.addCleanup(app.close)
        return app, backend

    @staticmethod
    def lines(frame):
        return tuple(''.join(c.text for c in row) for row in frame.rows)

    def finish(self, app):
        deadline = time.monotonic() + 3
        while app.bridge.active and time.monotonic() < deadline:
            app.loop.turn()
            app.refresh()
            time.sleep(.001)
        self.assertFalse(app.bridge.active)
        app.refresh()
        return app.bridge.snapshot

    def set_draft(self, app, text):
        app.composer.set_selection(0, len(app.composer.text))
        app.composer.insert(text)

    def controlled(self, app, *, failure=False, cleanup_failure=False, cancellable=False):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        block = app.results.append('/examples', '  pinned draft  \n', active=True)
        app._operation_block = block
        def worker(context):
            context.running()
            entered.set()
            if not release.wait(2):
                raise RuntimeError('watchdog')
            context.checkpoint()
            if failure:
                raise RuntimeError('secret error that must not appear in the Ledger')
            return 'finished'
        def cleanup():
            if cleanup_failure:
                raise RuntimeError('cleanup secret')
        from cereja.ui.operations import CooperativeCancellation
        app.bridge.start('Synthetic fixture', worker, cleanup=cleanup,
                         cancellation=CooperativeCancellation('test fixture') if cancellable else None)
        self.assertTrue(entered.wait(1))
        app.loop.turn()
        return block, release

    def test_paste_and_suggestion_need_a_later_submit(self):
        app, _ = self.app()
        initial = len(app.results.blocks)
        app.handle(PasteEvent('/examples\nprogress'))
        self.assertEqual(len(app.results.blocks), initial)
        self.assertFalse(app.bridge.active)
        app.composer.set_selection(0, len(app.composer.text))
        app.handle(KeyEvent('slash', text='/'))
        app.handle(KeyEvent('enter'))
        self.assertEqual(app.composer.text, '/home ')
        self.assertEqual(len(app.results.blocks), initial)
        app.handle(KeyEvent('enter'))
        self.assertEqual(len(app.results.blocks), initial + 1)

    def test_help_and_copy_preserve_composer(self):
        app, _ = self.app()
        app.handle(PasteEvent('q text'))
        app.composer.set_selection(0, 1)
        state = app.composer.content, app.composer.selection, app.composer.caret
        app.handle(KeyEvent('f1'))
        app.handle(KeyEvent('escape'))
        self.assertEqual((app.composer.content, app.composer.selection, app.composer.caret), state)
        app.handle(KeyEvent('c', modifiers={'ctrl'}))
        self.assertIn('Copy unavailable', app.notice)
        self.assertFalse(app.loop.stopped)

    def test_unknown_and_form_commands_do_not_echo_secrets_or_start_work(self):
        app, _ = self.app()
        for value in ('q', 'print(1)', '/download https://user:secret@example.test?q=secret', '/tree'):
            self.set_draft(app, value)
            app.submit()
            self.assertFalse(app.bridge.active)
            self.assertFalse(any('secret' in b.content.text for b in app.results.blocks))
        self.assertIs(app.overlays.top, app.tree_form)
        self.assertNotIn('secret', str(app.tree_form.values))

    def test_paste_bound_and_no_match_never_execute(self):
        app, _ = self.app()
        app.handle(PasteEvent('x' * 4097))
        self.assertEqual(app.composer.text, '')
        self.assertIn('limit', app.notice)
        app.handle(PasteEvent('/zzzz'))
        app.handle(KeyEvent('enter', repeat=1000))
        self.assertEqual(len(app.results.blocks), 1)
        self.assertIsNotNone(app.overlays.top)
        app.handle(KeyEvent('escape'))
        self.assertEqual(app.composer.text, '/zzzz')

    def test_compact_form_reveals_second_field_and_error(self):
        app, _ = self.app((40, 12))
        self.set_draft(app, '/examples')
        app.handle(KeyEvent('enter'))
        app.handle(KeyEvent('tab'))
        self.assertEqual(app.focus.focused, 'steps')
        frame = app.render()
        self.assertIn('20', self.lines(frame)[5])
        editor = app.examples_form.input('steps')
        editor.set_selection(0, len(editor.text))
        app.handle(PasteEvent('0'))
        app.handle(KeyEvent('enter'))
        self.assertIn('Use 1..20', '\n'.join(self.lines(app.render())))
        self.assertFalse(app.bridge.active)

    def test_example_form_help_back_and_reopen_keep_values(self):
        app, _ = self.app()
        self.set_draft(app, '/examples')
        app.submit()
        app.handle(KeyEvent('a', modifiers={'ctrl'}))
        app.handle(PasteEvent('input'))
        app.handle(KeyEvent('f1'))
        app.handle(KeyEvent('escape'))
        self.assertEqual(app.focus.focused, 'kind')
        self.assertEqual(app.examples_form.input('kind').text, 'input')
        app.handle(KeyEvent('escape'))
        app.submit()
        self.assertEqual(app.examples_form.input('kind').text, 'input')
        app.handle(KeyEvent('enter'))
        self.assertIsInstance(app.overlays.top, ParameterForm)
        self.assertEqual(app.overlays.top.identity, 'input-example')

    def test_completion_preserves_draft_focus_overlay_and_old_selection(self):
        app, _ = self.app()
        block, release = self.controlled(app)
        app.focus.focus('content')
        app.results.select_text()
        old = block.selection
        self.set_draft(app, 'unsubmitted q')
        app.handle(KeyEvent('f1'))
        state = app.focus.focused, app.overlays.top, app.composer.content
        release.set()
        receipt = self.finish(app)
        self.assertEqual(receipt.state, 'Succeeded')
        self.assertEqual((app.focus.focused, app.overlays.top, app.composer.content), state)
        self.assertIs(block.selection, old)
        self.assertIn('pinned draft', old.text)
        self.assertEqual(block.content.text, 'finished')
        app.handle(KeyEvent('escape'))
        self.assertEqual(app.focus.focused, 'content')

    def test_second_operation_rejected_navigation_and_wait_can_be_undone(self):
        app, _ = self.app()
        _, release = self.controlled(app)
        app._example('progress', 1)
        self.assertIn('Nothing was queued', app.notice)
        app.handle(KeyEvent('c', modifiers={'ctrl'}))
        self.assertTrue(app.exit_open)
        self.assertEqual(app.focus.focused, 'stay')
        self.assertNotIn('cancel', app.focus.scope.eligible)
        app.handle(KeyEvent('tab'))
        app.handle(KeyEvent('enter'))
        self.assertTrue(app.waiting)
        self.assertFalse(app.exit_open)
        app.handle(KeyEvent('c', modifiers={'ctrl'}))
        app.handle(KeyEvent('enter'))
        self.assertFalse(app.waiting)
        release.set()
        self.finish(app)
        app.loop.turn()
        self.assertFalse(app.loop.stopped)

    def test_copy_failure_during_work_does_not_request_exit_or_cancel(self):
        app, _ = self.app()
        _, release = self.controlled(app, cancellable=True)
        app.handle(PasteEvent('select'))
        app.composer.set_selection(0, 6)
        app.handle(KeyEvent('c', modifiers={'ctrl'}))
        self.assertFalse(app.exit_open)
        self.assertNotEqual(app.bridge.snapshot.state, 'CancelRequested')
        self.assertIn('Copy unavailable', '\n'.join(self.lines(app.render())))
        release.set()
        self.finish(app)

    def test_synthetic_cooperation_is_finite_and_only_certifies_fixture(self):
        app, _ = self.app()
        app._example('progress', 20)
        self.assertTrue(app.bridge.cancel())
        result = self.finish(app)
        self.assertEqual(result.state, 'Cancelled')
        self.assertTrue(result.worker_exited)
        self.assertEqual(result.delivery, 'delivered')
        self.assertEqual(app.loop.timer_count, 0)

    def test_synthetic_success_and_no_post_completion_timers(self):
        app, _ = self.app()
        app._example('progress', 2)
        result = self.finish(app)
        self.assertEqual(result.state, 'Succeeded')
        self.assertIn('2 batches', app.results.current.content.text)
        self.assertEqual(app.progress.percent, 100)
        self.assertEqual(app.loop.timer_count, 0)

    def test_failure_and_cleanup_failure_are_distinct_and_sanitized(self):
        for failure, cleanup, state in ((True, False, 'Failed'), (False, True, 'CleanupFailed')):
            app, _ = self.app()
            block, release = self.controlled(app, failure=failure, cleanup_failure=cleanup)
            release.set()
            self.assertEqual(self.finish(app).state, state)
            self.assertEqual(block.state, state)
            self.assertNotIn('secret', block.content.text)

    def test_publication_failure_is_never_success(self):
        app, _ = self.app()
        original = app.loop.wait_post
        from cereja.ui.events import OperationResultEvent
        def broken(event, **kwargs):
            if isinstance(event, OperationResultEvent):
                raise RuntimeError('publication failure')
            return original(event, **kwargs)
        with patch.object(app.loop, 'wait_post', side_effect=broken):
            app._example('progress', 1)
            result = self.finish(app)
        self.assertEqual(result.delivery, 'publication_failed')
        self.assertEqual(app.results.current.state, 'Unavailable')
        self.assertIn('No success', app.results.current.content.text)
        self.assertEqual(app.status.state, 'warning')

    def test_resize_preserves_state_and_hidden_controls_do_not_edit(self):
        size = [80, 24]
        app, _ = self.app(lambda: tuple(size))
        self.set_draft(app, '/examples')
        app.submit()
        app.handle(KeyEvent('tab'))
        state = app.focus.focused, app.examples_form.values, app.composer.content
        size[:] = [32, 10]
        app.handle(ResizeEvent(*size))
        app.handle(PasteEvent('unseen'))
        self.assertEqual((app.focus.focused, app.examples_form.values, app.composer.content), state)
        size[:] = [40, 12]
        app.handle(ResizeEvent(*size))
        self.assertEqual((app.focus.focused, app.examples_form.values, app.composer.content), state)

    def test_modes_unicode_hostile_text_and_exact_dock(self):
        from cereja.ui.terminal import CapabilityOptions
        for size in ((120, 40), (80, 24), (40, 12)):
            for options in (None, CapabilityOptions(color=0, unicode=False, reduced_motion=True)):
                app, _ = self.app(size, options=options)
                app._example('text', 1)
                frame = app.render()
                lines = self.lines(frame)
                self.assertIn('Cereja / Ledger', lines[0])
                self.assertEqual(lines[size[1] - 4][2:6], '----')
                self.assertTrue(all(row[-1] == ' ' for row in lines))
                self.assertNotIn('\x1b', '\n'.join(lines))
                self.assertEqual(app.loop.timer_count, 0)

    def test_diagnostics_allowlist_does_not_collect_environment(self):
        app, _ = self.app()
        with patch.dict('os.environ', {'TOKEN': 'private-value', 'USERPROFILE': 'private-path'}):
            text = app.diagnostics()
        self.assertNotIn('private', text)
        self.assertIn('not collected', text)

    def test_transport_without_delimited_paste_is_not_interactive(self):
        from cereja.ui.terminal import CapabilityOptions
        with TerminalSession(VirtualBackend(options=CapabilityOptions(paste=False))) as session:
            with self.assertRaisesRegex(ValueError, 'delimited paste'):
                Ledger(session)

    def test_wait_exits_only_after_completion_is_consumed(self):
        app, _ = self.app()
        _, release = self.controlled(app)
        app.handle(KeyEvent('c', modifiers={'ctrl'}))
        app.handle(KeyEvent('tab'))
        app.handle(KeyEvent('enter'))
        self.assertTrue(app.waiting)
        self.assertFalse(app.loop.stopped)
        release.set()
        result = self.finish(app)
        self.assertTrue(result.worker_exited)
        self.assertEqual(result.delivery, 'delivered')
        app.loop.turn()
        self.assertTrue(app.loop.stopped)

    def test_minimum_recovery_and_copy_ownership(self):
        size = [40, 12]
        app, _ = self.app(lambda: tuple(size))
        app.focus.focus('content')
        app.results.select_text()
        for w, h in ((32, 10), (1, 1), (0, 0)):
            size[:] = [w, h]
            app.handle(ResizeEvent(w, h))
            app.handle(KeyEvent('c', modifiers={'ctrl'}))
            self.assertIn('Copy unavailable', app.notice)
            self.assertFalse(app.exit_open)

    def test_paste_protocol_events_never_cross_into_execution(self):
        from cereja.ui._input import EscapeParser
        app, _ = self.app()
        parser = EscapeParser()
        events = parser.feed(b'\x1b[200~/examples progress\n/home\x1b[201~', 0.0)
        for event in events:
            app.handle(event)
        self.assertEqual(len(app.results.blocks), 1)
        self.assertFalse(app.bridge.active)
        self.assertIn('\n/home', app.composer.text)

    def test_compact_omission_and_truncation_are_visible_before_payload(self):
        app, _ = self.app((40, 12))
        for _ in range(22):
            app.results.append('/examples', 'x' * 17000)
        pager = self.lines(app.render())[7]
        self.assertIn('Omitted', pager)
        self.assertIn('Truncated', pager)

    def test_cancel_phase_remains_visible_with_progress_and_older_selection(self):
        app, _ = self.app((40, 12))
        _, release = self.controlled(app, cancellable=True)
        app.progress.update('Synthetic', completed=1, total=20, reliable_total=True)
        app.results.select(app.results.blocks[0].identity)
        app.handle(KeyEvent('c', modifiers={'ctrl'}))
        app.handle(KeyEvent('tab'))
        app.handle(KeyEvent('tab'))
        app.handle(KeyEvent('enter'))
        self.assertIn('CancelRequested', self.lines(app.render())[-1])
        release.set()
        self.finish(app)

    def test_final_result_waits_for_ui_consumption(self):
        app, _ = self.app()
        block, release = self.controlled(app)
        release.set()
        deadline = time.monotonic() + 2
        while not app.bridge.snapshot.worker_exited and time.monotonic() < deadline:
            time.sleep(.001)
        self.assertTrue(app.bridge.snapshot.worker_exited)
        self.assertTrue(app.bridge.active)
        app.refresh()
        self.assertEqual(block.state, 'Final pending')
        self.assertTrue(block.active)
        self.assertNotIn('finished', block.content.text)
        self.finish(app)
        self.assertEqual(block.state, 'Succeeded')


if __name__ == '__main__':
    unittest.main()
