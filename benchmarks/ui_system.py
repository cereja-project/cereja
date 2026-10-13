"""Bounded APP-02 measurements. Only timings/counts/fingerprints are persisted."""
import argparse
import hashlib
from pathlib import Path
import platform
import subprocess
import sys
import threading
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _ui_bench import summary, emit
from cereja.system.hardware import info
from cereja.system.hardware.models import HardwareInfo, CPUInfo, OperatingSystemInfo
from cereja.ledger.app import Ledger
from cereja.ui.events import KeyEvent
from cereja.ui.rendering import Renderer
from cereja.ui.terminal import TerminalSession
from cereja.ui.testing import VirtualBackend

FIXTURE = HardwareInfo(cpu=CPUInfo(name='Synthetic CPU', cores=4, logical_processors=8),
                       os=OperatingSystemInfo(name='Synthetic OS'))


def sample(native=False):
    entered = threading.Event()
    durations = []
    def collector(**kwargs):
        started = time.perf_counter_ns()
        entered.set()
        if native:
            value = info(**kwargs)
        else:
            time.sleep(.06)  # controlled blocking fixture, not simulated UI clock
            value = FIXTURE
        durations.append(time.perf_counter_ns() - started)
        return value
    backend = VirtualBackend(size=(80, 24))
    with TerminalSession(backend) as session:
        app = Ledger(session)
        try:
            started = time.perf_counter_ns()
            input_times, turns = [], []
            with patch('cereja.system.hardware.info', side_effect=collector):
                app._system('os,cpu')
                if not entered.wait(2):
                    raise RuntimeError('collector did not enter')
                deadline = time.monotonic() + 30  # measurement watchdog, not service deadline
                while app.bridge.active:
                    tick = time.perf_counter_ns()
                    app.loop.turn()
                    app.refresh()
                    turns.append(time.perf_counter_ns() - tick)
                    if app.bridge.snapshot.state == 'Running' and not app.bridge.snapshot.worker_exited and len(input_times) < 5:
                        tick = time.perf_counter_ns()
                        app.handle(KeyEvent('x', text='x'))
                        input_times.append(time.perf_counter_ns() - tick)
                    if time.monotonic() > deadline:
                        raise RuntimeError('measurement watchdog exceeded; service may still execute')
                    time.sleep(.001)
            total = time.perf_counter_ns() - started
            if app.results.blocks[-1].state != 'Succeeded':
                raise RuntimeError('integration failed')
            tick = time.perf_counter_ns()
            frame = app.render()
            cellbuffer = time.perf_counter_ns() - tick
            renderer = Renderer(session)
            tick = time.perf_counter_ns()
            renderer.render(frame)
            render = time.perf_counter_ns() - tick
            assert app.composer.text == 'x' * len(input_times)
            return dict(facade_ns=durations[0], integration_ns=total,
                        input_handle_ns=input_times, scheduler_turn_ns=turns,
                        final_cellbuffer_ns=cellbuffer, renderer_memory_sink_ns=render,
                        input_count=len(input_times), logical_result_bytes=app.results.retained_bytes)
        finally:
            app.close()


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--samples', type=int, default=31)
    parser.add_argument('--warmup', type=int, default=3)
    parser.add_argument('--native-samples', type=int, default=0)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if not 1 <= args.samples <= 100 or not 0 <= args.warmup <= 5 or not 0 <= args.native_samples <= 31:
        parser.error('bounded samples: 1..100; warmup: 0..5; native: 0..31')
    results = {}
    for name, count, native in (('controlled_fixture', args.samples, False), ('native_host', args.native_samples, True)):
        if not count:
            continue
        for _ in range(args.warmup):
            sample(native)
        raw = [sample(native) for _ in range(count)]
        stats = {key: summary([row[key] for row in raw]) for key in
                 ('facade_ns', 'integration_ns', 'final_cellbuffer_ns', 'renderer_memory_sink_ns', 'input_count')}
        for key in ('input_handle_ns', 'scheduler_turn_ns'):
            values = [value for row in raw for value in row[key]]
            stats[key] = summary(values) if values else None
        results[name] = dict(raw=raw, summary=stats, warmups=args.warmup)
    files = sorted((ROOT / 'cereja/ledger').glob('*.py')) + sorted((ROOT / 'cereja/ui').glob('*.py'))
    files += sorted((ROOT / 'cereja/system/hardware').glob('*.py')) + [Path(__file__), ROOT / 'benchmarks/_ui_bench.py']
    report = dict(schema_version=1, python=platform.python_version(), platform_family=sys.platform,
                  base_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  source_git_lf_sha256={str(p.relative_to(ROOT)).replace('\\', '/'):
                      hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest() for p in files},
                  sections=['os', 'cpu'], detail='basic', include_sensitive=False,
                  conditions='Sequential runs; external load, affinity, power and OS caches uncontrolled. '
                             '80x24 virtual terminal, real monotonic clocks. Fixture blocks 60 ms; five synthetic inputs at most. '
                             'Native facade runs only on this host. No inventory values persisted.',
                  limits='Facade timing excludes projection; integration includes scheduler/publication and 1 ms observation waits. '
                         'Input timing measures synthetic handle including CellBuffer; scheduler turn includes pending renderer. '
                         'Renderer measured separately with a fresh front and memory sink. No real transport/presentation latency, '
                         'human experience, global deadline, peak RSS or cross-host guarantee measured.',
                  scenarios=results)
    emit(report, args.output)


if __name__ == '__main__':
    main()
