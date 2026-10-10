"""Real producers + synthetic input, bounded demo and reproducible latency samples."""
import argparse
from dataclasses import asdict
import hashlib
from pathlib import Path
import sys
import threading
import time

from _ui_bench import emit, environment, summary

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cereja.ui.buffer import CellBuffer, Rect
from cereja.ui.editing import TextInput
from cereja.ui.events import (KeyEvent, FocusEvent, ProgressEvent, TimerEvent, WakeEvent,
                             OperationResultEvent, OperationErrorEvent)
from cereja.ui.feedback import ActivityIndicator, InlineStatus, ProgressBar
from cereja.ui.operations import OperationBridge
from cereja.ui.scheduling import EventLoop
from cereja.ui.terminal import CapabilityOptions, TerminalSession
from cereja.ui.testing import VirtualBackend
from cereja.ui.text import TextPolicy


class MemoryBackend(VirtualBackend):
    """Condition-backed real wait and bounded synthetic input, no OS transport.

    Discard rendered frames/bytes after counting them. No benchmark history in
    the sink, unlike VirtualBackend's deliberate test recording.
    """
    def __init__(self, mode):
        self._ready = threading.Condition()
        self._notified = False
        self.utf8_bytes = 0
        super().__init__(size=(80, 6), clock=time.monotonic,
            input_interactive=mode != 'plain', output_interactive=mode != 'plain',
            options=CapabilityOptions(color=0, unicode=False, reduced_motion=mode == 'off'))

    def _step(self, operation, *args):
        return None

    def write(self, text):
        self.utf8_bytes += len(text.encode('utf-8'))
        return len(text)

    def commit_cells(self, cells):
        self.invalidated = False

    def inject_input(self, *events):
        with self._ready:
            if len(self._input) + len(events) > 64:
                raise OverflowError('synthetic input capacity')
            self._input.extend(events)
            self._notified = True
            self._ready.notify()

    def wake(self):
        with self._ready:
            self._notified = True
            self._ready.notify()
        return True

    def wait_events(self, timeout, *, read_input=True):
        with self._ready:
            if not self._input and not self._notified and timeout != 0:
                self._ready.wait(timeout)
            events = []
            if read_input:
                for _ in range(min(64, len(self._input))):
                    events.append(self._input.popleft())
            if self._notified:
                self._notified = False
                events.append(WakeEvent())
            return tuple(events)


def sample(mode='local', *, output=False, pressure=False, duration=.25):
    """Real monotonic clock, one progress worker, optional noncoalescible producer."""
    if mode not in ('local', 'low-bandwidth', 'off', 'plain') or not .02 <= duration <= 1:
        raise ValueError('unsupported bounded workload')
    backend = MemoryBackend(mode)
    stop = threading.Event()
    ready = threading.Event()
    producing = threading.Event()
    production = {}
    acknowledged = threading.Event()
    injected = {}
    raw_input = []
    navigation = []
    counts = {'attempted_progress': 0, 'accepted_progress': 0, 'served_progress': 0,
              'pressure_events': 0, 'final_events': 0, 'paints': 0}
    dirty = False
    threads = []
    started_ns = time.perf_counter_ns()
    with TerminalSession(backend) as session:
        loop = EventLoop(session, lambda event: None, low_bandwidth=mode == 'low-bandwidth')
        bridge = OperationBridge(loop, 'synthetic')
        activity = ActivityIndicator(loop, 'activity', 'Synthetic operation', motion=mode != 'off')
        status = InlineStatus('status', 'idle', 'Synthetic bounded operation')
        progress = ProgressBar('progress', 'Measured iterations')
        editor = TextInput('composer', 'unchanged draft')
        editor.set_selection(0, 9)
        selection = editor.selection
        canonical = editor.content
        frame = CellBuffer(80, 6, policy=TextPolicy(ascii_only=True))
        screen = 0
        def handle(event):
            nonlocal dirty, screen
            if type(event) is KeyEvent:
                index = int(event.text)
                stamp, turn, under_load = injected.pop(index)
                raw_input.append({'injected_ns': stamp, 'handled_ns': time.perf_counter_ns(),
                    'injected_turn': turn, 'handled_turn': loop.metrics.turns,
                    'during_production': under_load})
                screen = 1 - screen
                navigation.append(screen)
                acknowledged.set()
                dirty = True
                return
            if type(event) is TimerEvent:
                dirty = activity.handle(event) or dirty
                return
            if bridge.handle(event):
                snap = bridge.snapshot
                if type(event) is ProgressEvent:
                    counts['served_progress'] += 1
                    progress.update(event.message, completed=event.completed,
                        total=event.total, reliable_total=event.total is not None)
                final = type(event) in (OperationResultEvent, OperationErrorEvent)
                if final:
                    counts['final_events'] += 1
                label = ('success' if snap.state == 'Succeeded' else
                         'error' if snap.state in ('Failed', 'CleanupFailed') else 'loading')
                activity.update(label, snap.name + ': ' + snap.state,
                                active=not snap.worker_exited and snap.state != 'Validating')
                status.update(label, snap.name + ': ' + snap.state)
                dirty = True
        loop.handler = handle
        def work(ctx):
            ctx.running()
            producing.set()
            production['begin_ns'] = time.perf_counter_ns()
            ready.set()
            end = time.monotonic() + duration
            hard_end = time.monotonic() + 2
            i = 0
            while (not stop.is_set() and i < 1000000 and time.monotonic() < hard_end
                   and (time.monotonic() < end or len(raw_input) < 4)):
                i += 1
                counts['attempted_progress'] += 1
                counts['accepted_progress'] += ctx.progress(i, message='Measured iterations')
            production['end_ns'] = time.perf_counter_ns()
            producing.clear()
            ctx.committing()  # Explicit synthetic publication phase, no domain I/O.
            return i
        def inject():
            if not ready.wait(2):
                loop.request_shutdown('producer did not start')
                return
            for index in range(64):
                if stop.is_set():
                    break
                # Commit input under the same condition used to close injection.
                # Teardown cannot drain and then race a last unacknowledged key.
                with backend._ready:
                    if stop.is_set():
                        break
                    acknowledged.clear()
                    injected[index] = (time.perf_counter_ns(), loop.metrics.turns,
                                       producing.is_set())
                    backend.inject_input(KeyEvent('tab', str(index)))
                if not acknowledged.wait(2):
                    loop.request_shutdown('input watchdog')
                    break
                if stop.wait(.005):
                    break
        def compete():
            if not ready.wait(2):
                return
            while not stop.is_set():
                if not loop.wait_post(FocusEvent(True)):
                    break
                counts['pressure_events'] += 1
        try:
            if pressure:
                for _ in range(1024):
                    loop.post(FocusEvent(True))
            injector = threading.Thread(target=inject, name='synthetic-input')
            threads.append(injector)
            injector.start()
            if pressure:
                competitor = threading.Thread(target=compete, name='synthetic-pressure')
                threads.append(competitor)
                competitor.start()
            bridge.start('Synthetic operation', work)
            peak_count = peak_bytes = 0
            deadline = time.monotonic() + 5
            while bridge.active and not loop.stopped:
                if time.monotonic() > deadline:
                    raise AssertionError('sample watchdog')
                loop.turn(block=True)
                peak_count = max(peak_count, loop.queued_count)
                peak_bytes = max(peak_bytes, loop.queued_bytes)
                if dirty:
                    status.paint(frame, Rect(0, 0, 79, 1))
                    activity.paint(frame, Rect(0, 1, 79, 1))
                    progress.paint(frame, Rect(0, 2, 79, 1))
                    frame.draw_text(0, 3, 'Screen ' + str(screen))
                    editor.paint(frame, Rect(0, 4, 79, 1), focused=True)
                    counts['paints'] += 1
                    if output:
                        loop.request_render(frame)
                    dirty = False
            with backend._ready:
                stop.set()
            # Drain finite remainder, including last injected key and capacity wait.
            for _ in range(32):
                loop.turn()
            for thread in threads:
                thread.join(2)
                if thread.is_alive():
                    raise AssertionError('bounded producer did not exit: ' + thread.name)
            receipt = bridge.snapshot
            assert receipt.state == 'Succeeded' and receipt.delivery == 'delivered', receipt
            assert counts['final_events'] == 1 and navigation
            assert editor.content is canonical and editor.selection == selection
            assert loop.timer_count == 0
            # Flush the last throttled real frame by its actual deadline.
            while loop.next_deadline is not None:
                loop.turn(block=True)
            before = loop.metrics
            for _ in range(3):
                loop.turn()
            after = loop.metrics
            assert (after.renders, after.writes, after.timer_events) == (
                before.renders, before.writes, before.timer_events)
            latencies = [item['handled_ns'] - item['injected_ns'] for item in raw_input
                         if item['during_production']]
            assert latencies and not injected
            return {**counts, 'raw_input': raw_input, 'latency_ns': summary(latencies),
                'elapsed_ns': time.perf_counter_ns() - started_ns, 'production': production,
                'peak_sampled_envelopes': peak_count, 'peak_sampled_payload_bytes': peak_bytes,
                'metrics': asdict(after), 'utf8_bytes': backend.utf8_bytes,
                'outcome': receipt.state, 'worker_exited': receipt.worker_exited,
                'idle_periodic_work': 0, 'editor_selection_preserved': True,
                'rows': [''.join(c.text for c in row).rstrip() for row in frame.rows]}
        finally:
            stop.set()
            activity.close()
            bridge.close()
            loop.close()
            for thread in threads:
                thread.join(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--samples', type=int, default=31)
    parser.add_argument('--warmup', type=int, default=3)
    parser.add_argument('--duration', type=float, default=.25)
    parser.add_argument('--output')
    args = parser.parse_args()
    if not 1 <= args.samples <= 100 or not 1 <= args.warmup <= 10 or not .02 <= args.duration <= 1:
        parser.error('samples 1..100, warmup 1..10, duration .02..1 required')
    if args.demo:
        result = sample(output=True)
        print('\n'.join(result['rows']))
        return
    names = ('cereja/ui/operations.py', 'cereja/ui/_posting.py', 'cereja/ui/events.py',
             'cereja/ui/scheduling.py', 'cereja/ui/feedback.py', 'benchmarks/ui_operations.py')
    report = {'environment': environment(),
        'source_git_lf_sha256': {n: hashlib.sha256((ROOT/n).read_bytes().replace(b'\r\n', b'\n')).hexdigest() for n in names},
        'conditions': {'samples': args.samples, 'warmup': args.warmup,
            'duration_seconds': args.duration, 'geometry': '80x6 ASCII/no-color',
            'producer': 'One real worker, Progress until minimum duration and four serviced input events; hard stop at 2 seconds/1,000,000 iterations. No sleep per progress.',
            'contention': 'Optional second real producer, noncoalescible FocusEvent with wait_post; prefill 1,024 envelopes.',
            'input': 'Separate real thread, one outstanding synthetic Tab, 5 ms after acknowledgement, max 64 keys.',
            'measurement': 'perf_counter_ns immediately before input admission to timestamp after key ID lookup in handler; includes Python/GIL scheduling and memory input admission.',
            'boundaries': ['scheduler/CellBuffer', 'scheduler/CellBuffer/renderer/memory sink'],
            'limits': 'No OS input/output transport, terminal presentation, human task, clipboard, domain I/O, RSS or global memory measurement. '
                      'No fixed latency guarantee. Callbacks and writes remain nonpreemptive. Queue peaks sampled at turn boundaries. '
                      'Candidates remain 30/4 Hz frames and 8/2 Hz indicators.'},
        'results': []}
    for mode in ('local', 'low-bandwidth', 'off', 'plain'):
        for output in (False, True):
            for pressure in (False, True):
                print('Measuring', mode, 'renderer=' + str(output), 'pressure=' + str(pressure), file=sys.stderr, flush=True)
                for _ in range(args.warmup):
                    sample(mode, output=output, pressure=pressure, duration=args.duration)
                raw = [sample(mode, output=output, pressure=pressure, duration=args.duration)
                       for _ in range(args.samples)]
                latencies = [event['handled_ns'] - event['injected_ns']
                             for item in raw for event in item['raw_input'] if event['during_production']]
                report['results'].append({'mode': mode, 'output': output, 'pressure': pressure,
                    'input_latency_ns': summary(latencies),
                    'sample_p95_ns': summary([item['latency_ns']['p95'] for item in raw]),
                    'raw': raw})
    emit(report, args.output)


if __name__ == '__main__':
    main()

