"""Shared real-transport pressure probe, used by PTY/console tests and benchmarks."""

from dataclasses import asdict
import threading
import time
from unittest.mock import patch

from cereja.ui.events import FocusEvent, KeyEvent, QuitEvent, ResultEvent
from cereja.ui.scheduling import EventLoop


def exercise_native(session, inject_key):
    """Consume 10,000 ordered worker results, inspect native input, then close.

    Injection is into the real OS input buffer, not a human keyboard or emulator.
    No absolute latency budget is asserted; measured samples are host-specific.
    Worker joins have a test watchdog, not a production interruption guarantee.
    """
    seen = []
    times = {}
    loop = EventLoop(session, seen.append)
    # Synchronize at an indefinite native wait, without a sleep or polling.
    waiting_idle = threading.Event()
    def wake_idle():
        if not waiting_idle.wait(2):
            loop.request_shutdown('idle wait was not entered')
            return
        times['post'] = time.monotonic()
        loop.post(FocusEvent(True))
    real_native_wait = session.backend.wait
    def observe_native_wait(timeout, **kwargs):
        if timeout is None:
            waiting_idle.set()
        return real_native_wait(timeout, **kwargs)
    worker = threading.Thread(target=wake_idle)
    worker.start()
    with patch.object(session.backend, 'wait', side_effect=observe_native_wait):
        while FocusEvent(True) not in seen and not loop.stopped:
            loop.turn(block=True)
    times['delivered'] = time.monotonic()
    worker.join(1)
    if worker.is_alive() or loop.stopped:
        raise AssertionError('idle producer did not exit')
    idle = asdict(loop.metrics)
    if idle['blocking_waits'] != 1 or idle['writes'] or idle['flushes'] or idle['renders']:
        raise AssertionError(f'idle transport counters differed: {idle}')
    request = loop.begin_request('pressure')
    received = []
    injection_turn = inspection_turn = None
    injection_time = inspection_time = None
    def handle(event):
        nonlocal injection_turn, inspection_turn, injection_time, inspection_time
        if type(event) is ResultEvent:
            received.append(event.value)
            if len(received) == 64:
                injection_turn = loop.metrics.turns
                injection_time = time.monotonic()
                inject_key()
        elif event == KeyEvent('x', 'x'):
            inspection_turn = loop.metrics.turns
            inspection_time = time.monotonic()
    loop.handler = handle
    for value in range(1024):
        if not loop.post(ResultEvent('pressure', request.generation, value)):
            raise AssertionError('initial bounded backlog was rejected')
    errors = []
    def produce():
        try:
            for value in range(1024, 10000):
                if not loop.wait_post(ResultEvent('pressure', request.generation, value)):
                    raise AssertionError('sustained result was rejected')
        except BaseException as error:
            errors.append(error)
            loop.request_shutdown('producer failed')
    worker = threading.Thread(target=produce)
    worker.start()
    started = time.monotonic()
    blocked = None
    try:
        while len(received) < 10000 and not loop.stopped:
            loop.turn(block=True)
        # Input may be delivered on the final pressure turn, never via a drain.
        if inspection_turn is None:
            loop.turn()
        worker.join(2)
        if worker.is_alive() or errors or received != list(range(10000)):
            raise AssertionError(f'ordered producer failed: {errors!r}')
        if inspection_turn is None or inspection_turn > injection_turn + 1:
            raise AssertionError('native key was not inspected by the next turn: '
                f'injected={injection_turn}, inspected={inspection_turn}, '
                f'total_turns={loop.metrics.turns}, admission_pauses={loop.metrics.admission_pauses}')
        pressure = asdict(loop.metrics)
        pressure_seconds = time.monotonic() - started
        # Full inbox, capacity-waiting producer and live timer at shutdown.
        for value in range(1024):
            if not loop.post(ResultEvent('pressure', request.generation, value)):
                raise AssertionError('shutdown backlog did not fill')
        loop.call_later(100, owner='pending')
        waiting = threading.Event()
        outcome = []
        real_wait = loop._inbox.condition.wait
        def observe_wait(timeout=None):
            waiting.set()
            return real_wait(timeout)
        with patch.object(loop._inbox.condition, 'wait', side_effect=observe_wait):
            blocked = threading.Thread(target=lambda: outcome.append(loop.wait_post(
                ResultEvent('pressure', request.generation, -1))))
            blocked.start()
            if not waiting.wait(1):
                raise AssertionError('shutdown producer never waited for capacity')
            quit_seen = []
            loop.handler = quit_seen.append
            loop.post(QuitEvent('pressure shutdown'))
            loop.turn()
            blocked.join(1)
        if blocked.is_alive() or outcome != [False] or quit_seen != [QuitEvent('pressure shutdown')]:
            raise AssertionError('shutdown did not release its producer and inspect Quit')
        if not session.closed or loop.queued_count or loop.timer_count:
            raise AssertionError('shutdown retained session, queue or timers')
        return {
            'workload': 10000, 'idle': idle, 'pressure': pressure,
            'idle_post_latency_seconds': times['delivered'] - times['post'],
            'key_latency_seconds': inspection_time - injection_time,
            'key_injection_turn': injection_turn, 'key_inspection_turn': inspection_turn,
            'pressure_seconds': pressure_seconds,
            'shutdown': asdict(loop.metrics), 'worker_joined': True,
        }
    finally:
        loop.close()
        worker.join(2)
        if blocked is not None:
            blocked.join(2)
