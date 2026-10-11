"""Reproducible scheduling counters and OS-injected input latency (stdlib only)."""

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
from time import perf_counter_ns

from _ui_bench import emit, environment, summaries, traced

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def virtual():
    from cereja.ui.events import KeyEvent, QuitEvent, ResultEvent
    from cereja.ui.scheduling import EventLoop
    from cereja.ui.terminal import TerminalSession
    from cereja.ui.testing import VirtualBackend
    backend = VirtualBackend()
    with TerminalSession(backend) as session:
        loop = EventLoop(session, lambda event: None, clock=backend.clock)
        loop.turn(block=True)
        idle = asdict(loop.metrics)
        request = loop.begin_request('pressure')
        received = []
        turns = {}
        next_value = 1024
        def handle(event):
            nonlocal next_value
            if type(event) is ResultEvent:
                received.append(event.value)
                backend.advance(.000002)
                if next_value < 10000:
                    assert loop.post(ResultEvent('pressure', request.generation, next_value))
                    next_value += 1
                if len(received) == 64:
                    turns['injection'] = loop.metrics.turns
                    backend.inject_input(KeyEvent('x', 'x'))
            elif type(event) is KeyEvent:
                turns['inspection'] = loop.metrics.turns
        loop.handler = handle
        for value in range(1024):
            assert loop.post(ResultEvent('pressure', request.generation, value))
        while loop.queued_count:
            loop.turn()
        assert received == list(range(10000))
        assert turns['inspection'] <= turns['injection'] + 1
        pressure = asdict(loop.metrics)
        for value in range(1024):
            assert loop.post(ResultEvent('pressure', request.generation, value))
        loop.call_later(100, owner='pending')
        loop.post(QuitEvent())
        loop.turn()
        assert loop.stopped and session.closed and not loop.timer_count
        return {'workload': 10000, 'idle': idle, 'pressure': pressure,
                'key_injection_turn': turns['injection'], 'key_inspection_turn': turns['inspection'],
                'shutdown': asdict(loop.metrics), 'fake_clock': True}


def windows():
    if os.name != 'nt':
        raise RuntimeError('Windows console transport requires Windows')
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    completed = subprocess.run(
        [sys.executable, '-B', '-S', str(ROOT / 'tests/ui_windows_console_probe.py')],
        cwd=ROOT, startupinfo=startup, creationflags=subprocess.CREATE_NEW_CONSOLE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', timeout=15)
    if completed.returncode:
        raise RuntimeError(completed.stdout + completed.stderr)
    return json.loads(completed.stdout)['scheduling']


def posix():
    if os.name != 'posix':
        raise RuntimeError('PTY transport requires POSIX')
    import pty
    from cereja.ui.posix import PosixBackend
    from cereja.ui.terminal import TerminalSession
    from tests.ui_scheduling_probe import exercise_native
    master, slave = pty.openpty()
    try:
        with os.fdopen(os.dup(slave), 'r', encoding='utf-8') as input_stream, \
                os.fdopen(os.dup(slave), 'w', encoding='utf-8') as output_stream:
            backend = PosixBackend(input_stream, output_stream, environ={'TERM': 'xterm'})
            try:
                with TerminalSession(backend) as session:
                    return exercise_native(session, lambda: os.write(master, b'x'))
            finally:
                backend.close()
    finally:
        os.close(master)
        os.close(slave)


def timers(width, height, count):
    """Real elapsed compute over fake deadlines, with small fixed callbacks."""
    from cereja.ui.buffer import CellBuffer
    from cereja.ui.events import TimerEvent
    from cereja.ui.scheduling import EventLoop
    from cereja.ui.terminal import TerminalSession
    from cereja.ui.testing import VirtualBackend
    backend = VirtualBackend(size=(width, height))
    received = []
    with TerminalSession(backend) as session:
        loop = EventLoop(session, received.append, clock=backend.clock)
        start = perf_counter_ns()
        for index in range(count):
            loop.call_later(.125, owner=f'timer-{index}')
        create_ns = perf_counter_ns() - start
        backend.advance(.125)
        start = perf_counter_ns()
        while loop.timer_count:
            loop.turn()
        dispatch_ns = perf_counter_ns() - start
        assert len(received) == count and all(type(event) is TimerEvent for event in received)
        frame = CellBuffer(width, height)
        frame.draw_text(0, 0, 'Ledger e\u0301 \u754c \U0001f469\u200d\U0001f4bb')
        start = perf_counter_ns()
        loop.request_render(frame)
        loop.turn()
        first_render_ns = perf_counter_ns() - start
        before = (session.write_count, session.flush_count)
        backend.advance(1)
        start = perf_counter_ns()
        loop.request_render(frame)
        loop.turn()
        unchanged_render_ns = perf_counter_ns() - start
        assert (session.write_count, session.flush_count) == before
        counters = asdict(loop.metrics)
        loop.close()
        return {'create_ns': create_ns, 'dispatch_ns': dispatch_ns,
                'first_render_ns': first_render_ns, 'unchanged_render_ns': unchanged_render_ns,
                **counters}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--transport', choices=('virtual', 'windows', 'posix'), default='virtual')
    parser.add_argument('--samples', type=int, default=5)
    parser.add_argument('--warmup', type=int, default=3)
    parser.add_argument('--memory-samples', type=int, default=7)
    parser.add_argument('--output')
    args = parser.parse_args()
    if not 1 <= args.samples <= 31 or min(args.warmup, args.memory_samples) < 1:
        parser.error('samples must be in 1..31; warmup and memory samples positive')
    for _ in range(args.warmup):
        globals()[args.transport]()
    samples = [globals()[args.transport]() for _ in range(args.samples)]
    result = {'environment': environment(),
              'transport': args.transport, 'samples': samples,
              'conditions': {'warmup': args.warmup, 'samples': args.samples,
                             'memory_samples': args.memory_samples, 'seed': None,
                             'callbacks': 'Small append, fixed 10,000 integer results, UTF-8 source names.',
                             'fake_clock': args.transport == 'virtual',
                             'limits': 'Fake time validates scheduling, never native latency; native injection '
                                       'includes worker/thread/instrumentation costs, not emulator or Ledger latency.'},
              'policies': {'envelopes': 1024, 'bytes': 1048576,
                           'events_per_turn': 64, 'producer_seconds': .004,
                           'local_hz': 30, 'low_bandwidth_hz': 4, 'spinner_hz': 8}}
    if args.transport != 'virtual':
        result['median_key_latency_seconds'] = statistics.median(
            sample['key_latency_seconds'] for sample in samples)
        result['median_idle_post_latency_seconds'] = statistics.median(
            sample['idle_post_latency_seconds'] for sample in samples)
        result['summary'] = summaries(samples)
    else:
        result['timer_results'] = []
        for width, height in ((80, 24), (120, 40), (240, 80)):
            for count in (1, 64, 1024):
                for _ in range(args.warmup):
                    timers(width, height, count)
                raw = [timers(width, height, count) for _ in range(args.samples)]
                memory = [traced(lambda: timers(width, height, count)) for _ in range(args.memory_samples)]
                result['timer_results'].append({'width': width, 'height': height, 'timers': count,
                                                'raw': raw, 'summary': summaries(raw),
                                                'memory_raw': memory, 'memory_summary': summaries(memory)})
    emit(result, args.output)


if __name__ == '__main__':
    main()
