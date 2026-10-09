"""Reproducible scheduling counters and OS-injected input latency (stdlib only)."""

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--transport', choices=('virtual', 'windows', 'posix'), default='virtual')
    parser.add_argument('--samples', type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.samples <= 31:
        parser.error('samples must be in 1..31')
    samples = [globals()[args.transport]() for _ in range(args.samples)]
    result = {'python': sys.version, 'platform': platform.platform(),
              'transport': args.transport, 'samples': samples,
              'policies': {'envelopes': 1024, 'bytes': 1048576,
                           'events_per_turn': 64, 'producer_seconds': .004,
                           'local_hz': 30, 'low_bandwidth_hz': 4, 'spinner_hz': 8}}
    if args.transport != 'virtual':
        result['median_key_latency_seconds'] = statistics.median(
            sample['key_latency_seconds'] for sample in samples)
        result['median_idle_post_latency_seconds'] = statistics.median(
            sample['idle_post_latency_seconds'] for sample in samples)
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == '__main__':
    main()
