"""Background lifecycle requirements, synchronized workers and bounded delivery."""
import threading
import time
import unittest
from unittest.mock import patch

from cereja.ui.events import (KeyEvent, ProgressEvent, OperationStartedEvent,
    OperationPhaseEvent, OperationResultEvent, OperationErrorEvent)
from cereja.ui.operations import OperationBridge, OperationBusy, CooperativeCancellation
from cereja.ui.scheduling import EventLoop, payload_bytes
from cereja.ui.terminal import TerminalSession
from cereja.ui.testing import VirtualBackend


class OperationTest(unittest.TestCase):
    def setup_bridge(self, **kwargs):
        backend = VirtualBackend(size=(80, 4))
        session = TerminalSession(backend)
        session.__enter__()
        self.addCleanup(session.close)
        seen = []
        loop = EventLoop(session, lambda e: (bridge.handle(e), seen.append(e)), **kwargs)
        self.addCleanup(loop.close)
        bridge = OperationBridge(loop, 'operation')
        self.addCleanup(bridge.close)
        return bridge, loop, backend, seen

    def finish(self, bridge, loop):
        deadline = time.monotonic() + 3
        while bridge.active and time.monotonic() < deadline:
            loop.turn()
            time.sleep(.001)  # test watchdog only, production has no polling timer
        self.assertFalse(bridge.active)
        loop.turn()
        return bridge.snapshot



    def test_cancel_during_validation_cannot_imply_observed_running(self):
        for progress in (False, True):
            bridge, loop, _, _ = self.setup_bridge()
            entered, release = threading.Event(), threading.Event()
            def work(ctx):
                entered.set()
                release.wait(2)
                if progress:
                    ctx.progress(1)
                return 'returned without Running'
            bridge.start('validation', work, cancellation=CooperativeCancellation('fixture'))
            self.assertTrue(entered.wait(1))
            self.assertTrue(bridge.cancel())
            release.set()
            self.assertEqual(self.finish(bridge, loop).state, 'Failed')

    def test_provisional_outcome_is_hidden_until_actual_thread_exit(self):
        bridge, loop, _, _ = self.setup_bridge()
        tail, release = threading.Event(), threading.Event()
        original = bridge._work
        def linger(*args):
            original(*args)
            tail.set()
            release.wait(2)
        def work(ctx):
            ctx.running()
            return 'provisional'
        with patch.object(bridge, '_work', side_effect=linger):
            bridge.start('tail', work)
            self.assertTrue(tail.wait(1))
            self.assertIsNone(bridge.snapshot.outcome)
            self.assertFalse(bridge.snapshot.worker_exited)
            self.assertTrue(bridge.active)
            loop.turn()
            with self.assertRaises(OperationBusy):
                bridge.start('second', work)
            release.set()
            receipt = self.finish(bridge, loop)
        self.assertEqual(receipt.outcome.value, 'provisional')
        self.assertTrue(receipt.worker_exited)

    def test_one_operation_navigation_and_no_automatic_queue(self):
        bridge, loop, backend, seen = self.setup_bridge()
        entered, release = threading.Event(), threading.Event()
        def work(ctx):
            ctx.running()
            entered.set()
            if not release.wait(2):
                raise RuntimeError('test watchdog')
            return 'done'
        bridge.start('Synthetic', work)
        self.assertTrue(entered.wait(1))
        with self.assertRaises(OperationBusy):
            bridge.start('second', work)
        self.assertEqual(bridge.exit_choices, ('return', 'wait'))
        self.assertFalse(bridge.cancel())
        backend.inject_input(KeyEvent('tab'))
        loop.turn()
        self.assertIn(KeyEvent('tab'), seen)
        self.assertTrue(bridge.active)
        release.set()
        receipt = self.finish(bridge, loop)
        self.assertEqual(receipt.state, 'Succeeded')
        self.assertEqual(receipt.delivery, 'delivered')
        self.assertTrue(receipt.worker_exited)
        self.assertEqual(len([e for e in seen if type(e) is OperationResultEvent]), 1)
        self.assertEqual(loop.timer_count, 0)

    def test_progress_coalesces_final_survives_full_inbox(self):
        bridge, loop, _, seen = self.setup_bridge(max_events=2)
        entered, release = threading.Event(), threading.Event()
        def work(ctx):
            ctx.running()
            entered.set()
            release.wait(2)
            for i in range(10000):
                ctx.progress(i, total=10000, reliable_total=True)
            return 10000
        bridge.start('pressure', work)
        # Start/phase publication can backpressure until the UI consumes.
        for _ in range(20):
            loop.turn()
            if entered.wait(.01):
                break
        self.assertTrue(entered.is_set())
        release.set()
        receipt = self.finish(bridge, loop)
        self.assertEqual(receipt.state, 'Succeeded')
        self.assertGreater(loop.metrics.coalesced_posts + loop.metrics.rejected_posts, 0)
        self.assertLessEqual(loop.queued_count, 2)
        self.assertEqual(sum(type(e) is OperationResultEvent for e in seen), 1)

    def test_cancel_request_is_not_stopped_and_commit_excludes_cancel(self):
        bridge, loop, _, seen = self.setup_bridge()
        entered, release = threading.Event(), threading.Event()
        cleaned = []
        def work(ctx):
            ctx.running()
            entered.set()
            release.wait(2)
            ctx.checkpoint()
            return 'unreachable'
        bridge.start('cooperative', work, cleanup=lambda: cleaned.append(True),
                     cancellation=CooperativeCancellation('tests: bounded checkpoint + cleanup'))
        self.assertTrue(entered.wait(1))
        self.assertTrue(bridge.cancel())
        self.assertEqual(bridge.snapshot.state, 'CancelRequested')
        self.assertTrue(bridge.active)
        self.assertFalse(bridge.snapshot.worker_exited)
        release.set()
        receipt = self.finish(bridge, loop)
        self.assertEqual(receipt.state, 'Cancelled')
        self.assertEqual(cleaned, [True])
        entered.clear()
        release.clear()
        def commit(ctx):
            ctx.running()
            ctx.committing()
            entered.set()
            release.wait(2)
            return 'published'
        bridge.start('commit', commit,
                     cancellation=CooperativeCancellation('fixture'))
        self.assertTrue(entered.wait(1))
        self.assertFalse(bridge.cancel())
        release.set()
        self.assertEqual(self.finish(bridge, loop).state, 'Succeeded')

    def test_cleanup_failure_is_distinct_and_retains_observed_result(self):
        bridge, loop, _, seen = self.setup_bridge()
        def work(ctx):
            ctx.running()
            ctx.committing()
            return 'published'
        def cleanup():
            raise OSError('owned cleanup failed')
        bridge.start('cleanup', work, cleanup=cleanup)
        receipt = self.finish(bridge, loop)
        self.assertEqual(receipt.state, 'CleanupFailed')
        self.assertEqual(receipt.outcome.value, 'published')
        self.assertTrue(receipt.outcome.result_available)
        self.assertEqual(sum(type(e) is OperationErrorEvent for e in seen), 1)

    def test_suppression_does_not_release_running_worker(self):
        bridge, loop, _, _ = self.setup_bridge()
        entered, release = threading.Event(), threading.Event()
        def work(ctx):
            ctx.running()
            entered.set()
            release.wait(2)
            return 'done'
        bridge.start('stale', work)
        self.assertTrue(entered.wait(1))
        loop.cancel_request('operation')
        self.assertTrue(bridge.active)
        with self.assertRaises(OperationBusy):
            bridge.start('second', work)
        release.set()
        receipt = self.finish(bridge, loop)
        self.assertEqual(receipt.state, 'Succeeded')
        self.assertEqual(receipt.delivery, 'suppressed')

    def test_loop_close_releases_publication_but_not_domain_work(self):
        bridge, loop, _, _ = self.setup_bridge()
        entered, release = threading.Event(), threading.Event()
        cleaned = []
        def work(ctx):
            ctx.running()
            entered.set()
            release.wait(2)
            return 'done after close'
        bridge.start('noncancelable', work, cleanup=lambda: cleaned.append(True))
        self.assertTrue(entered.wait(1))
        loop.close()
        self.assertTrue(bridge.active)
        self.assertEqual(bridge.snapshot.state, 'Running')
        release.set()
        receipt = self.finish(bridge, loop)
        self.assertEqual(receipt.state, 'Succeeded')
        self.assertEqual(receipt.delivery, 'unavailable')
        self.assertEqual(cleaned, [True])

    def test_payloads_reject_graphs_subclasses_and_oversize(self):
        bridge, loop, _, _ = self.setup_bridge()
        self.assertEqual(payload_bytes(OperationStartedEvent('a', 1, 'b', False)), 2)
        for value in ([], {}, object(), ('x',)):
            with self.assertRaises(TypeError):
                payload_bytes(OperationResultEvent('a', 1, 'Succeeded', value))
        def work(ctx):
            ctx.running()
            return 'x' * 65537
        bridge.start('large', work)
        self.assertEqual(self.finish(bridge, loop).state, 'Failed')

    def test_wait_exit_delivers_final_then_closes_without_join_on_ui(self):
        bridge, loop, _, seen = self.setup_bridge()
        release = threading.Event()
        def work(ctx):
            ctx.running()
            release.wait(2)
            return 'done'
        bridge.start('exit', work)
        self.assertFalse(bridge.request_exit('wait'))
        loop.turn()
        self.assertFalse(loop.stopped)
        self.assertFalse(bridge.request_exit('return'))
        self.assertFalse(bridge.request_exit('wait'))
        release.set()
        self.finish(bridge, loop)
        loop.turn()
        self.assertTrue(loop.stopped)
        self.assertEqual(sum(type(e) is OperationResultEvent for e in seen), 1)


    def test_error_then_cleanup_error_preserves_both_diagnostics(self):
        bridge, loop, _, seen = self.setup_bridge()
        def fail(ctx):
            ctx.running()
            raise ValueError('domain failure')
        def cleanup():
            raise OSError('cleanup failure')
        bridge.start('failures', fail, cleanup=cleanup)
        receipt = self.finish(bridge, loop)
        self.assertEqual(receipt.state, 'CleanupFailed')
        self.assertIn('domain failure', receipt.outcome.primary_error)
        self.assertIn('cleanup failure', receipt.outcome.message)
        self.assertFalse(receipt.outcome.result_available)

    def test_cleanup_holds_slot_and_removes_cancel_affordance(self):
        bridge, loop, _, _ = self.setup_bridge()
        entered, release = threading.Event(), threading.Event()
        def work(ctx):
            ctx.running()
            return 'done'
        def cleanup():
            entered.set()
            release.wait(2)
        bridge.start('settle', work, cleanup=cleanup,
                     cancellation=CooperativeCancellation('fixture'))
        self.assertTrue(entered.wait(1))
        self.assertTrue(bridge.active)
        self.assertFalse(bridge.cancel())
        self.assertNotIn('cancel', bridge.exit_choices)
        with self.assertRaises(OperationBusy):
            bridge.start('next', work)
        release.set()
        self.assertEqual(self.finish(bridge, loop).state, 'Succeeded')

    def test_callback_exception_is_failure_not_cancellation(self):
        bridge, loop, _, _ = self.setup_bridge()
        def work(ctx):
            ctx.running()
            raise RuntimeError('callback aborted')
        bridge.start('callback', work, cancellation=CooperativeCancellation('fixture'))
        self.assertEqual(self.finish(bridge, loop).state, 'Failed')

    def test_cancel_race_can_finish_successfully_without_acknowledgement(self):
        bridge, loop, _, _ = self.setup_bridge()
        entered, release = threading.Event(), threading.Event()
        def work(ctx):
            ctx.running()
            entered.set()
            release.wait(2)
            return 'completed before another safe checkpoint'
        bridge.start('race', work, cancellation=CooperativeCancellation('fixture'))
        self.assertTrue(entered.wait(1))
        self.assertTrue(bridge.cancel())
        release.set()
        self.assertEqual(self.finish(bridge, loop).state, 'Succeeded')

    def test_cancel_checkpoint_then_cleanup_failure_is_not_cancelled(self):
        bridge, loop, _, _ = self.setup_bridge()
        entered, release = threading.Event(), threading.Event()
        def work(ctx):
            ctx.running()
            entered.set()
            release.wait(2)
            ctx.checkpoint()
        def cleanup():
            raise OSError('unresolved resource')
        bridge.start('cancel cleanup', work, cleanup=cleanup,
                     cancellation=CooperativeCancellation('fixture'))
        self.assertTrue(entered.wait(1))
        bridge.cancel()
        release.set()
        self.assertEqual(self.finish(bridge, loop).state, 'CleanupFailed')

    def test_typed_accounting_and_generation_cover_every_lifecycle_event(self):
        bridge, loop, _, seen = self.setup_bridge()
        request = loop.begin_request('old')
        events = (OperationStartedEvent('old', request.generation, 'name'),
                  OperationPhaseEvent('old', request.generation, 'Running'),
                  OperationResultEvent('old', request.generation, 'Succeeded', b'x'),
                  OperationErrorEvent('old', request.generation, 'Failed', 'message'))
        for event in events:
            self.assertTrue(loop.post(event))
        loop.begin_request('old')
        loop.turn()
        self.assertFalse(seen)
        self.assertEqual(loop.metrics.suppressed_results, 4)
        with self.assertRaises(ValueError):
            payload_bytes(OperationPhaseEvent('old', 1, 'Imaginary'))
        with self.assertRaises(TypeError):
            payload_bytes(OperationErrorEvent('old', 1, 'Failed', []))
        class Subclass(OperationResultEvent):
            pass
        with self.assertRaises(TypeError):
            payload_bytes(Subclass('old', 1, 'Succeeded'))

    def test_final_does_not_free_slot_before_delivery_and_duplicate_is_ignored(self):
        bridge, loop, _, seen = self.setup_bridge()
        def work(ctx):
            ctx.running()
            return 'done'
        bridge.start('first', work)
        deadline = time.monotonic() + 2
        while not bridge.snapshot.worker_exited and time.monotonic() < deadline:
            time.sleep(.001)
        self.assertTrue(bridge.snapshot.worker_exited)
        self.assertTrue(bridge.active)
        with self.assertRaises(OperationBusy):
            bridge.start('second', work)
        receipt = self.finish(bridge, loop)
        self.assertFalse(bridge.handle(receipt.outcome))
        observer = bridge._observer
        bridge.start('second', work)
        self.finish(bridge, loop)
        self.assertIs(bridge._observer, observer)
        self.assertEqual(sum(type(e) is OperationResultEvent for e in seen), 2)

    def test_publication_failure_retains_bounded_outcome(self):
        bridge, loop, _, _ = self.setup_bridge()
        original = loop.wait_post
        def publish(event, **kwargs):
            if type(event) is OperationResultEvent:
                raise OSError('publication failed')
            return original(event, **kwargs)
        def work(ctx):
            ctx.running()
            return 'owned result'
        with patch.object(loop, 'wait_post', side_effect=publish):
            bridge.start('publish', work)
            receipt = self.finish(bridge, loop)
        self.assertEqual(receipt.delivery, 'publication_failed')
        self.assertEqual(receipt.outcome.value, 'owned result')
        self.assertTrue(receipt.worker_exited)

    def test_tiny_inbox_reports_unavailable_instead_of_waiting_forever(self):
        bridge, loop, _, _ = self.setup_bridge(max_bytes=1)
        called = []
        bridge.start('cannot fit', lambda ctx: called.append(True))
        receipt = self.finish(bridge, loop)
        self.assertEqual(receipt.state, 'Failed')
        self.assertEqual(receipt.delivery, 'unavailable')
        self.assertFalse(called)

    def test_close_unblocks_capacity_wait_and_releases_request(self):
        bridge, loop, _, _ = self.setup_bridge(max_events=1)
        loop.post(KeyEvent('full'))
        cleaned = threading.Event()
        bridge.start('blocked start', lambda ctx: None, cleanup=cleaned.set)
        bridge.close()
        receipt = self.finish(bridge, loop)
        self.assertTrue(cleaned.is_set())
        self.assertEqual(receipt.delivery, 'unavailable')
        self.assertFalse(loop._requests)
        deadline = time.monotonic() + 1
        while bridge._observer is not None and time.monotonic() < deadline:
            time.sleep(.001)
        self.assertIsNone(bridge._observer)

    def test_consumer_failure_and_terminal_loss_leave_no_false_cancel(self):
        from cereja.ui.events import EOFEvent
        for failure in ('handler', 'eof', 'write'):
            bridge, loop, backend, _ = self.setup_bridge()
            entered, release = threading.Event(), threading.Event()
            def work(ctx):
                ctx.running()
                entered.set()
                release.wait(2)
                return 'settled'
            bridge.start(failure, work)
            self.assertTrue(entered.wait(1))
            if failure == 'handler':
                loop.handler = lambda event: (_ for _ in ()).throw(ValueError('handler'))
                with self.assertRaises(ValueError):
                    loop.turn()
            elif failure == 'eof':
                backend.inject_input(EOFEvent())
                loop.turn()
            else:
                from cereja.ui.buffer import CellBuffer
                backend.failures['write'] = BrokenPipeError()
                loop.request_render(CellBuffer(80, 4))
                loop.turn()
            self.assertTrue(loop.stopped)
            self.assertTrue(bridge.active)
            release.set()
            receipt = self.finish(bridge, loop)
            self.assertEqual(receipt.state, 'Succeeded')
            self.assertEqual(receipt.delivery, 'unavailable')

    def test_worker_context_rejects_foreign_thread_and_unobserved_phases(self):
        bridge, loop, _, _ = self.setup_bridge()
        captured = []
        def work(ctx):
            captured.append(ctx)
            return 'no Running'
        bridge.start('phase', work)
        self.assertEqual(self.finish(bridge, loop).state, 'Failed')
        with self.assertRaises(RuntimeError):
            captured[0].running()

    def test_observer_start_failure_starts_no_domain_worker(self):
        bridge, loop, _, _ = self.setup_bridge()
        called = []
        with patch.object(threading.Thread, 'start', side_effect=RuntimeError('start')):
            with self.assertRaises(RuntimeError):
                bridge.start('start', lambda ctx: called.append(True))
        self.assertFalse(bridge.active)
        self.assertFalse(called)
        self.assertFalse(loop._requests)


    def test_thread_construction_failure_does_not_orphan_admission(self):
        bridge, loop, _, _ = self.setup_bridge()
        with patch('cereja.ui.operations.threading.Thread', side_effect=RuntimeError('construct')):
            with self.assertRaises(RuntimeError):
                bridge.start('constructor', lambda ctx: None)
        self.assertFalse(bridge.active)
        self.assertFalse(loop._requests)

    def test_worker_start_failure_is_a_delivered_error(self):
        bridge, loop, _, seen = self.setup_bridge()
        start = threading.Thread.start
        def checked(thread):
            if thread.name == 'cereja-operation-worker':
                raise RuntimeError('cannot create worker')
            start(thread)
        with patch.object(threading.Thread, 'start', checked):
            bridge.start('worker', lambda ctx: None)
            receipt = self.finish(bridge, loop)
        self.assertEqual(receipt.state, 'Failed')
        self.assertEqual(receipt.delivery, 'delivered')

    def test_progress_does_not_assert_untrusted_total(self):
        bridge, loop, _, seen = self.setup_bridge()
        def work(ctx):
            ctx.running()
            ctx.progress(3, total=10, message='real count')
            return 3
        bridge.start('unknown total', work)
        self.finish(bridge, loop)
        progress = [e for e in seen if type(e) is ProgressEvent]
        self.assertEqual(len(progress), 1)
        self.assertIsNone(progress[0].total)


    def test_fake_clock_fairness_and_feedback_leave_interaction_state_owned(self):
        from cereja.ui.buffer import CellBuffer, Rect
        from cereja.ui.collections import Row, SelectableList
        from cereja.ui.editing import TextContent, TextInput
        from cereja.ui.events import ResizeEvent, TimerEvent
        from cereja.ui.feedback import ActivityIndicator, ProgressBar
        bridge, loop, backend, _ = self.setup_bridge()
        editor = TextInput('composer', '/inspect draft')
        editor.set_selection(1, 4)
        canonical = TextContent('row', 1, '  source\ttext  \n\n')
        rows = SelectableList('rows', [Row(str(i), (str(i),), canonical) for i in range(8)])
        rows.select('4')
        rows.set_text_selection('4', 0, len(canonical.text))
        rows.scroll(2)
        before = (editor.content, editor.selection, rows.selected, rows.text_selection, rows.scroll_y)
        activity = ActivityIndicator(loop, 'active', 'Known', active=True)
        progress = ProgressBar('progress', 'Real iterations')
        frame = CellBuffer(80, 4)
        entered, release = threading.Event(), threading.Event()
        def work(ctx):
            ctx.running()
            entered.set()
            release.wait(2)
            ctx.progress(100, total=100, reliable_total=True)
            return 'complete'
        seen = []
        def handle(event):
            seen.append(event)
            if bridge.handle(event):
                if type(event) is ProgressEvent:
                    progress.update(event.message, completed=event.completed,
                                    total=event.total, reliable_total=True)
                if type(event) is OperationResultEvent:
                    activity.update('success', 'Complete')
            activity.handle(event)
        loop.handler = handle
        bridge.start('UI state', work)
        self.assertTrue(entered.wait(1))
        loop.turn()
        for _ in range(4):
            activity.paint(frame, Rect(0, 0, 79, 1))
            revision = activity.content
            backend.advance(.125)
            for i in range(1024):
                loop.post(KeyEvent('pressure'))
            backend.inject_input(KeyEvent('tab'), ResizeEvent(40, 3))
            loop.turn()
            self.assertIs(activity.content, revision)
        self.assertIn(KeyEvent('tab'), seen)
        self.assertIn(ResizeEvent(40, 3), seen)
        self.assertFalse(bridge.handle(KeyEvent('c', modifiers=frozenset({'ctrl'}))))
        copy = rows.handle(KeyEvent('c', modifiers=frozenset({'ctrl'})))
        self.assertEqual(copy.selection.text, canonical.text)
        self.assertTrue(bridge.active)
        release.set()
        self.finish(bridge, loop)
        self.assertEqual(progress.percent, 100)
        self.assertEqual(before, (editor.content, editor.selection, rows.selected,
                                 rows.text_selection, rows.scroll_y))
        self.assertEqual(loop.timer_count, 0)
        count = loop.metrics
        backend.advance(100)
        loop.turn()
        self.assertEqual((count.timer_events, count.writes),
                         (loop.metrics.timer_events, loop.metrics.writes))
        activity.close()

    def test_replacement_generation_and_close_preserve_new_request_owner(self):
        bridge, loop, _, _ = self.setup_bridge()
        entered, release = threading.Event(), threading.Event()
        def work(ctx):
            ctx.running()
            entered.set()
            release.wait(2)
            return 'old result'
        bridge.start('old', work)
        self.assertTrue(entered.wait(1))
        newer = loop.begin_request('operation')
        self.assertTrue(bridge.active)
        release.set()
        self.assertEqual(self.finish(bridge, loop).delivery, 'suppressed')
        bridge.close()
        self.assertTrue(loop.request_active(newer))


    def test_operation_events_share_aggregate_byte_budget(self):
        bridge, loop, _, _ = self.setup_bridge()
        event = OperationResultEvent('a', 1, 'Succeeded', b'x' * 65535)
        self.assertEqual(payload_bytes(event), 65536)
        for _ in range(16):
            self.assertTrue(loop.post(event))
        self.assertEqual(loop.queued_bytes, 1048576)
        self.assertFalse(loop.post(event))
        self.assertEqual(loop.queued_count, 16)

    def test_error_final_survives_one_envelope_backpressure(self):
        bridge, loop, _, seen = self.setup_bridge(max_events=1)
        loop.post(KeyEvent('full'))
        def work(ctx):
            ctx.running()
            raise ValueError('real failure')
        bridge.start('error pressure', work)
        receipt = self.finish(bridge, loop)
        self.assertEqual(receipt.state, 'Failed')
        self.assertEqual(receipt.delivery, 'delivered')
        self.assertEqual(sum(type(e) is OperationErrorEvent for e in seen), 1)

    def test_loop_close_wakes_idle_observer_without_bridge_polling(self):
        bridge, loop, _, _ = self.setup_bridge()
        def work(ctx):
            ctx.running()
            return None
        bridge.start('idle observer', work)
        self.finish(bridge, loop)
        observer = bridge._observer
        loop.close()
        observer.join(1)  # test watchdog, never used by a production UI callback
        self.assertFalse(observer.is_alive())


    def test_failed_final_publication_wakes_blocking_plain_consumer(self):
        from io import StringIO
        from cereja.ui.terminal import StreamBackend
        session = TerminalSession(StreamBackend(StringIO(), StringIO()))
        session.__enter__()
        loop = EventLoop(session, lambda event: bridge.handle(event), max_bytes=1)
        bridge = OperationBridge(loop, 'source')
        self.addCleanup(session.close)
        self.addCleanup(loop.close)
        self.addCleanup(bridge.close)
        bridge.start('too large', lambda ctx: None)
        deadline = time.monotonic() + 2
        while bridge.active and time.monotonic() < deadline:
            time.sleep(.001)
        self.assertFalse(bridge.active)
        watchdog = threading.Timer(.5, lambda: loop.request_shutdown('watchdog'))
        watchdog.start()
        try:
            loop.turn(block=True)
            self.assertFalse(loop.stopped, 'publication failure lost the consumer wake')
        finally:
            watchdog.cancel()
            watchdog.join(1)


if __name__ == '__main__':
    unittest.main()

