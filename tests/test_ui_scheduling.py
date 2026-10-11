"""Requirement-derived scheduling checks (fake time, pressure and failures)."""

import threading
import unittest
from unittest.mock import patch

from cereja.ui.buffer import CellBuffer
from cereja.ui.events import (
    EOFEvent, FocusEvent, InputErrorEvent, KeyEvent, PasteEvent, ProgressEvent,
    QuitEvent, ResizeEvent, ResultEvent, TimerEvent, WakeEvent,
)
from cereja.ui.scheduling import Cancellation, EventLoop, payload_bytes
from cereja.ui.terminal import StreamBackend, TerminalCleanupError, TerminalSession
from cereja.ui.testing import VirtualBackend


class SchedulingTest(unittest.TestCase):
    def loop(self, **kwargs):
        backend = kwargs.pop('backend', VirtualBackend(size=(8, 2)))
        session = TerminalSession(backend)
        session.__enter__()
        self.addCleanup(session.close)
        seen = []
        handler = kwargs.pop('handler', seen.append)
        loop = EventLoop(session, handler, clock=backend.clock, **kwargs)
        self.addCleanup(loop.close)
        return loop, backend, seen

    def test_posted_limit_and_aggregate_utf8_include_coalesced_slots(self):
        loop, _, seen = self.loop()
        for _ in range(1024):
            self.assertTrue(loop.post(KeyEvent('a', 'a')))
        self.assertFalse(loop.post(KeyEvent('b', 'b')))
        self.assertEqual(loop.queued_count, 1024)
        loop.close()
        loop, _, seen = self.loop()
        self.assertTrue(loop.post(PasteEvent('é' * (1048576 // 2))))
        self.assertEqual(loop.queued_bytes, 1048576)
        self.assertFalse(loop.post(ProgressEvent('job', 1, 2, 'x')))

    def test_only_progress_and_resize_coalesce_by_source_in_place(self):
        loop, _, seen = self.loop(max_bytes=30)
        self.assertTrue(loop.post(ProgressEvent('job', 1, 3, 'old')))
        self.assertTrue(loop.post(KeyEvent('x', 'x')))
        self.assertTrue(loop.post(ProgressEvent('job', 2, 3, 'new')))
        self.assertTrue(loop.post(ResizeEvent(80, 24), source='terminal'))
        self.assertTrue(loop.post(ResizeEvent(90, 25), source='terminal'))
        self.assertFalse(loop.post(ProgressEvent('job', 3, 3, 'x' * 30)))
        self.assertEqual(loop.queued_count, 3)
        loop.turn()
        self.assertEqual(seen, [ProgressEvent('job', 2, 3, 'new'),
                                KeyEvent('x', 'x'), ResizeEvent(90, 25)])

    def test_accounting_rejects_object_graphs_and_event_subclasses(self):
        loop, _, _ = self.loop()
        for value in ([], {}, object(), (1, 2)):
            with self.assertRaises(TypeError):
                loop.post(ResultEvent('job', 1, value))
        class Derived(PasteEvent):
            pass
        with self.assertRaises(TypeError):
            loop.post(Derived('x'))
        self.assertEqual(payload_bytes(ResultEvent('é', 1, b'abc')), 5)
        self.assertEqual(payload_bytes(KeyEvent('enter')), 5)
        self.assertEqual(payload_bytes(ResizeEvent(1, 2)), 0)

    def test_input_and_quit_are_inspected_next_turn_under_10000_posts(self):
        received = []
        produced = [0]
        loop, backend, _ = self.loop(handler=lambda event: received.append(event))
        generation = loop.begin_request('job').generation
        def handler(event):
            received.append(event)
            if isinstance(event, ResultEvent):
                # Sustain the producer without exceeding its bounded backlog.
                if produced[0] < 10000:
                    self.assertTrue(loop.post(ResultEvent('job', generation, produced[0])))
                    produced[0] += 1
        loop.handler = handler
        for _ in range(1024):
            self.assertTrue(loop.post(ResultEvent('job', generation, produced[0])))
            produced[0] += 1
        loop.turn()
        self.assertEqual(loop.metrics.posted_events, 64)
        backend.inject_input(KeyEvent('x', 'x'), QuitEvent())
        loop.turn()
        self.assertIn(KeyEvent('x', 'x'), received)
        self.assertIn(QuitEvent(), received)
        self.assertTrue(loop.stopped)
        self.assertEqual(loop.metrics.turns, 2)

    def test_sustained_10000_events_preserve_all_ordered_actions(self):
        received = []
        next_value = [1024]
        loop, backend, _ = self.loop()
        generation = loop.begin_request('job').generation
        def handle(event):
            received.append(event)
            if type(event) is ResultEvent and next_value[0] < 10000:
                self.assertTrue(loop.post(ResultEvent('job', generation, next_value[0])))
                next_value[0] += 1
        loop.handler = handle
        for value in range(1024):
            loop.post(ResultEvent('job', generation, value))
        loop.turn()
        backend.inject_input(KeyEvent('a', 'a'), PasteEvent('\x03q'), KeyEvent('b', 'b'))
        loop.turn()
        self.assertEqual([e for e in received if type(e) is not ResultEvent],
                         [KeyEvent('a', 'a'), PasteEvent('\x03q'), KeyEvent('b', 'b')])
        while loop.queued_count:
            before = loop.metrics.posted_events
            loop.turn()
            self.assertLessEqual(loop.metrics.posted_events - before, 64)
        self.assertEqual([e.value for e in received if type(e) is ResultEvent], list(range(10000)))

    def test_four_ms_budget_checks_due_timers_and_input(self):
        loop, backend, seen = self.loop()
        def handle(event):
            seen.append(event)
            if type(event) is KeyEvent:
                backend.advance(.002)
        loop.handler = handle
        timer = loop.call_later(.003, owner='operation')
        for _ in range(100):
            loop.post(KeyEvent('p', 'p'))
        loop.turn()
        self.assertEqual(loop.metrics.posted_events, 2)
        self.assertEqual([e.timer_id for e in seen if type(e) is TimerEvent], [timer])

    def test_timers_tie_break_skip_missed_frames_and_release_cancelled_owners(self):
        loop, backend, seen = self.loop()
        first = loop.call_later(1, owner='a', interval=.125, decorative=True)
        second = loop.call_later(1, owner='b')
        backend.advance(10)
        loop.turn()
        self.assertEqual([e.timer_id for e in seen], [first, second])
        self.assertEqual(seen[0].now, 10)
        self.assertEqual(loop.next_deadline, 10.125)
        loop.cancel_owner('a')
        self.assertEqual(loop.timer_count, 0)
        self.assertIsNone(loop.next_deadline)

    def test_reduced_motion_and_plain_cancel_only_decorative_timers(self):
        loop, _, seen = self.loop()
        loop.call_later(1, owner='hidden', decorative=True)
        loop.call_later(1, owner='operation')
        loop.set_reduced_motion(True)
        self.assertEqual(loop.timer_count, 1)
        self.assertIsNone(loop.call_later(1, owner='spinner', interval=.01, decorative=True))
        loop.post(ProgressEvent('job', 1, 2))
        loop.turn()
        self.assertIn(ProgressEvent('job', 1, 2), seen)
        plain = VirtualBackend(input_interactive=False, output_interactive=False)
        loop, _, _ = self.loop(backend=plain)
        self.assertIsNone(loop.call_later(1, owner='spinner', decorative=True))

    def test_result_generation_and_cancellation_are_separate_from_worker_exit(self):
        loop, _, seen = self.loop()
        first = loop.begin_request('job')
        loop.post(ResultEvent('job', first.generation, 'old'))
        second = loop.begin_request('job')
        loop.post(ResultEvent('job', second.generation, 'new'))
        loop.turn()
        self.assertEqual(seen, [ResultEvent('job', second.generation, 'new')])
        self.assertFalse(first.cancellation.cancelled)
        loop.cancel_request('job')
        self.assertFalse(second.cancellation.cancelled)
        loop.post(ResultEvent('job', second.generation, 'cancelled'))
        loop.turn()
        self.assertEqual(len(seen), 1)
        loop.cancel_request('job', cooperative=True)
        self.assertTrue(second.cancellation.cancelled)

    def test_shutdown_full_queue_unblocks_worker_and_clears_timers(self):
        loop, backend, seen = self.loop(max_events=1)
        loop.post(KeyEvent('a', 'a'))
        loop.call_later(100, owner='pending')
        result = []
        entered = threading.Event()
        def producer():
            entered.set()
            result.append(loop.wait_post(KeyEvent('b', 'b')))
        worker = threading.Thread(target=producer)
        worker.start()
        self.assertTrue(entered.wait(1))
        loop.request_shutdown('quit')
        worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result, [False])
        loop.turn()
        self.assertEqual(seen, [QuitEvent('quit')])
        self.assertEqual(loop.queued_count, 0)
        with self.assertRaises(ValueError):
            loop.post(ProgressEvent('job', 1), source='ignored')
        self.assertEqual(loop.timer_count, 0)
        self.assertTrue(loop.session.closed)

    def test_worker_retry_waits_for_capacity_or_cancellation_without_spin(self):
        loop, _, seen = self.loop(max_events=1)
        loop.post(KeyEvent('a', 'a'))
        token = Cancellation()
        result = []
        worker = threading.Thread(target=lambda: result.append(
            loop.wait_post(KeyEvent('b', 'b'), cancellation=token)))
        worker.start()
        token.cancel()
        worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result, [False])
        with self.assertRaises(RuntimeError):
            loop.wait_post(KeyEvent('c', 'c'))

    def test_frame_ceiling_and_unchanged_frame_output(self):
        loop, backend, _ = self.loop()
        frame = CellBuffer(8, 2)
        loop.request_render(frame)
        loop.turn()
        counts = (loop.metrics.writes, loop.metrics.flushes)
        loop.request_render(frame)
        self.assertAlmostEqual(loop.next_deadline, 1 / 30)
        backend.advance(1 / 30)
        loop.turn()
        self.assertEqual((loop.metrics.writes, loop.metrics.flushes), counts)
        self.assertEqual(loop.metrics.renders, 2)

    def test_native_input_admission_pauses_while_retained_and_preserves_order(self):
        loop, backend, seen = self.loop()
        events = [KeyEvent(str(n), str(n)) for n in range(200)]
        backend.inject_input(*events)
        loop.turn()
        self.assertEqual(seen, events[:64])
        self.assertEqual(loop.native_pending, 136)
        loop.turn()
        self.assertEqual(seen, events[:128])
        self.assertIn(('wait_events', 0, False), backend.operations)
        while loop.native_pending:
            loop.turn()
        self.assertEqual(seen, events)

    def test_foreign_ui_mutation_and_render_are_rejected(self):
        loop, _, _ = self.loop()
        errors = []
        def worker():
            for action in (loop.turn, lambda: loop.call_later(1, owner='x'),
                           lambda: loop.request_render(CellBuffer(8, 2))):
                try:
                    action()
                except RuntimeError:
                    errors.append(True)
        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(1)
        self.assertEqual(errors, [True] * 3)

    def test_accounting_for_every_event_and_bounded_scalar_validation(self):
        cases = [(KeyEvent('a', 'é', frozenset({'ctrl'})), 7),
                 (PasteEvent('😀'), 4), (ResizeEvent(4, 5), 0),
                 (FocusEvent(True), 0), (WakeEvent(), 0), (EOFEvent(), 0),
                 (InputErrorEvent('é'), 2), (QuitEvent('quit'), 4),
                 (ProgressEvent('é', 1, 2, '😀'), 6),
                 (ResultEvent('é', 1, '😀'), 6),
                 (ResultEvent('é', 1, b'123'), 5),
                 (ResultEvent('x', 1, None), 1),
                 (ResultEvent('x', 1, True), 1),
                 (ResultEvent('x', 1, 1.25), 1),
                 (TimerEvent('é', 1, 1, 2), 2)]
        for event, cost in cases:
            self.assertEqual(payload_bytes(event), cost)
        for event in (FocusEvent(1), ProgressEvent('x', 3, 2),
                      ProgressEvent('x', -1), ResultEvent('x', 0, 'bad'),
                      ResultEvent('x', 1, 1 << 100), ResultEvent('x', 1, float('nan'))):
            with self.assertRaises((TypeError, ValueError)):
                payload_bytes(event)
        loop, _, _ = self.loop()
        self.assertFalse(loop.post(PasteEvent('é' * 524289)))
        self.assertFalse(loop.post(ResultEvent('x', 1, b'x' * 1048576)))
        self.assertEqual(loop.queued_count, 0)

    def test_coalescing_capacity_rejection_retains_previous_and_separates_sources(self):
        loop, _, seen = self.loop(max_bytes=10)
        loop.post(ProgressEvent('a', 1, 3, '12345'))
        loop.post(ProgressEvent('b', 1, 3, '12'))
        self.assertFalse(loop.post(ProgressEvent('a', 2, 3, '12345678')))
        self.assertEqual(loop.queued_bytes, 9)
        loop.turn()
        self.assertEqual(seen, [ProgressEvent('a', 1, 3, '12345'),
                                ProgressEvent('b', 1, 3, '12')])
        loop.post(ResizeEvent(1, 1), source='a')
        loop.post(ResizeEvent(2, 2), source='b')
        self.assertEqual(loop.queued_count, 2)
        self.assertEqual(loop.queued_bytes, 2)

    def test_worker_capacity_wait_releases_and_delivers_without_dropping(self):
        loop, _, seen = self.loop(max_events=1)
        loop.post(KeyEvent('a', 'a'))
        result = []
        started = threading.Event()
        original_wait = loop._inbox.condition.wait
        def observe_wait(timeout=None):
            started.set()
            return original_wait(timeout)
        with patch.object(loop._inbox.condition, 'wait', side_effect=observe_wait):
            worker = threading.Thread(target=lambda: result.append(loop.wait_post(KeyEvent('b', 'b'))))
            worker.start()
            self.assertTrue(started.wait(1))
            self.assertEqual(loop.metrics.capacity_waits, 1)
            loop.turn()
            worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result, [True])
        loop.turn()
        self.assertEqual(seen, [KeyEvent('a', 'a'), KeyEvent('b', 'b')])

    def test_idle_wait_is_infinite_and_render_deadline_is_earliest(self):
        loop, backend, _ = self.loop()
        loop.turn(block=True)
        self.assertIn(('wait_events', None, True), backend.operations)
        metrics = loop.metrics
        self.assertEqual((metrics.blocking_waits, metrics.posted_events, metrics.renders,
                          metrics.writes, metrics.flushes), (1, 0, 0, 0, 0))
        loop.call_later(1, owner='timer')
        loop.request_render(CellBuffer(8, 2))
        loop.turn()
        loop.request_render(CellBuffer(8, 2))
        self.assertAlmostEqual(loop.next_deadline, 1 / 30)
        loop.turn(block=True)
        self.assertAlmostEqual(backend.clock(), 1 / 30)
        self.assertEqual(loop.metrics.writes, 1)

    def test_plain_stream_waits_for_posted_work_without_native_polling(self):
        import io
        backend = StreamBackend(io.StringIO(), io.StringIO(), environ={})
        session = TerminalSession(backend).__enter__()
        self.addCleanup(session.close)
        seen = []
        loop = EventLoop(session, seen.append)
        self.addCleanup(loop.close)
        ready = threading.Event()
        real_wait = loop._inbox.condition.wait
        def wait(timeout=None):
            self.assertIsNone(timeout)
            ready.set()
            return real_wait(timeout)
        with patch.object(loop._inbox.condition, 'wait', side_effect=wait):
            worker = threading.Thread(target=lambda: (ready.wait(1), loop.post(FocusEvent(True))))
            worker.start()
            loop.turn(block=True)
            worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(seen, [FocusEvent(True)])
        self.assertEqual(loop.metrics.blocking_waits, 1)
        self.assertEqual(loop.metrics.writes, 0)
        self.assertEqual(loop.metrics.flushes, 0)

    def test_low_bandwidth_and_spinner_ceilings(self):
        for bandwidth, ceiling in ((False, 1 / 30), (True, .25)):
            loop, backend, seen = self.loop(low_bandwidth=bandwidth)
            frame = CellBuffer(8, 2)
            loop.request_render(frame)
            loop.turn()
            frame.draw_text(0, 0, 'x')
            loop.request_render(frame)
            self.assertAlmostEqual(loop.next_deadline, ceiling)
            timer = loop.call_later(0, owner='spinner', interval=.001,
                                    decorative=True, spinner=True)
            loop.turn()
            self.assertEqual(seen[-1].timer_id, timer)
            self.assertEqual(loop._timers[timer].deadline, .5 if bandwidth else .125)

    def test_timer_callback_cancels_itself_and_timer_storage_is_finite(self):
        loop, backend, seen = self.loop()
        identity = loop.call_later(0, owner='self', interval=1)
        loop.handler = lambda event: loop.cancel_timer(event.timer_id)
        loop.turn()
        self.assertEqual(loop.timer_count, 0)
        for _ in range(1024):
            loop.call_later(1000, owner='long')
        with self.assertRaises(OverflowError):
            loop.call_later(1000, owner='excess')
        self.assertEqual(loop.cancel_owner('long'), 1024)
        self.assertIsNone(loop.next_deadline)
        self.assertEqual(loop._timer_bytes, 0)
        for _ in range(256):
            loop.call_later(1, owner='x' * 4096)
        with self.assertRaises(OverflowError):
            loop.call_later(1, owner='x')

    def test_request_registry_is_finite_and_forget_does_not_reuse_generations(self):
        loop, _, seen = self.loop()
        first = loop.begin_request('job')
        loop.forget_request('job')
        second = loop.begin_request('job')
        loop.post(ResultEvent('job', first.generation, 'late'))
        loop.post(ResultEvent('job', second.generation, 'current'))
        loop.turn()
        self.assertEqual(seen, [ResultEvent('job', second.generation, 'current')])
        for n in range(1023):
            loop.begin_request(str(n))
        with self.assertRaises(OverflowError):
            loop.begin_request('excess')
        loop.forget_request('0')
        loop.begin_request('next')

    def test_stale_progress_cannot_replace_current_generation(self):
        loop, _, seen = self.loop()
        first = loop.begin_request('job')
        second = loop.begin_request('job')
        loop.post(ProgressEvent('job', 2, 3, generation=second.generation))
        loop.post(ProgressEvent('job', 1, 3, generation=first.generation))
        loop.turn()
        self.assertEqual(seen, [ProgressEvent('job', 2, 3, generation=second.generation)])
        self.assertEqual(loop.metrics.suppressed_results, 1)

    def test_failed_callbacks_and_cleanup_are_observable(self):
        error = ValueError('handler failed')
        loop, backend, _ = self.loop(handler=lambda event: (_ for _ in ()).throw(error))
        loop.post(KeyEvent('a', 'a'))
        loop.call_later(1, owner='pending')
        backend.failures['restore:paste'] = OSError('restoration failed')
        with self.assertRaises(ValueError) as caught:
            loop.turn()
        self.assertIs(caught.exception, error)
        self.assertTrue(loop.stopped)
        self.assertEqual(loop.timer_count, 0)
        self.assertEqual(len(loop.session.cleanup_failures), 1)
        self.assertFalse(loop.post(QuitEvent()))
        self.assertFalse(loop.post(KeyEvent('b', 'b')))

    def test_shutdown_cleanup_failure_is_not_hidden(self):
        loop, backend, _ = self.loop()
        backend.failures['restore:paste'] = OSError('cleanup')
        loop.request_shutdown('quit')
        with self.assertRaises(TerminalCleanupError):
            loop.turn()
        self.assertTrue(loop.stopped)
        self.assertTrue(loop.session.closed)

    def test_quit_callback_failure_survives_cleanup_failure(self):
        error = ValueError('quit handler')
        loop, backend, _ = self.loop(handler=lambda event: (_ for _ in ()).throw(error))
        backend.failures['restore:paste'] = OSError('cleanup')
        loop.request_shutdown('quit')
        with self.assertRaises(ValueError) as caught:
            loop.turn()
        self.assertIs(caught.exception, error)
        self.assertEqual(len(loop.session.cleanup_failures), 1)

    def test_reentrant_turn_fails_and_unwinds_session(self):
        loop, _, _ = self.loop()
        loop.handler = lambda event: loop.turn()
        loop.post(KeyEvent('a', 'a'))
        with self.assertRaises(RuntimeError):
            loop.turn()
        self.assertTrue(loop.stopped)
        self.assertTrue(loop.session.closed)

    def test_render_failure_keeps_previous_front_and_counts_partial_writes(self):
        loop, backend, _ = self.loop()
        frame = CellBuffer(8, 2)
        loop.request_render(frame)
        loop.turn()
        front = loop._renderer.front
        backend.failures['write'] = [1, 1, None]
        backend.failures['flush'] = OSError('flush')
        frame.draw_text(0, 0, 'x')
        loop.request_render(frame)
        backend.advance(1 / 30)
        with self.assertRaises(OSError):
            loop.turn()
        self.assertEqual(loop._renderer.front, front)
        self.assertFalse(loop._renderer.screen_known)
        self.assertEqual(loop.metrics.writes, 4)
        self.assertEqual(loop.metrics.flushes, 2)

    def test_input_deadline_precedes_timer_and_is_not_polled_in_idle(self):
        loop, backend, _ = self.loop()
        backend.input_deadline = .03
        loop.call_later(1, owner='timer')
        loop.turn(block=True)
        self.assertIn(('wait_events', .03, True), backend.operations)
        self.assertAlmostEqual(backend.clock(), .03)

    def test_reduced_motion_drops_pending_decoration_and_preserves_real_frame(self):
        loop, backend, _ = self.loop()
        loop.request_render(CellBuffer(8, 2), decorative=True)
        loop.set_reduced_motion(True)
        self.assertIsNone(loop.next_deadline)
        self.assertTrue(loop.request_render(CellBuffer(8, 2)))
        loop.turn()
        self.assertEqual(loop.metrics.renders, 1)

    def test_wake_failure_keeps_committed_admission_and_observable_error(self):
        loop, backend, seen = self.loop()
        with patch.object(backend, 'wake', side_effect=OSError('native wake failed')):
            self.assertTrue(loop.post(KeyEvent('a', 'a')))
        self.assertIsInstance(loop.wake_error, OSError)
        loop.turn()
        self.assertEqual(seen, [KeyEvent('a', 'a')])


if __name__ == '__main__':
    unittest.main()
