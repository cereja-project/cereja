"""Owned loopback fixtures: progress and callback-abort evidence, not Cancel certification."""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import platform
import sys
from tempfile import TemporaryDirectory
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from cereja.transfers import download

PAYLOAD = b'cereja-loopback-fixture\n' * 64


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        if self.path == '/known':
            self.send_header('Content-Length', str(len(PAYLOAD)))
        self.end_headers()
        self.wfile.write(PAYLOAD)

    def log_message(self, *args):
        pass


class ProbeAbort(Exception):
    pass


def run():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    report = {'python': platform.python_version(), 'os': platform.system(),
              'transport': 'owned loopback HTTP only', 'payload_bytes': len(PAYLOAD),
              'chunk_size': 128, 'cases': [],
              'scope': 'not full cancellation, commit-race, or hostile-network acceptance'}
    try:
        with TemporaryDirectory(prefix='cereja-ui-download-probe-') as directory:
            root = Path(directory)
            for mode in ('known', 'unknown'):
                output = root / (mode + '.bin')
                events = []
                result = download(
                    f'http://127.0.0.1:{server.server_port}/{mode}', output,
                    chunk_size=128, timeout=2,
                    progress=lambda event: events.append({
                        'bytes_transferred': event.bytes_transferred,
                        'total_bytes': event.total_bytes}))
                assert output.read_bytes() == PAYLOAD
                assert result.bytes_transferred == len(PAYLOAD)
                assert events[-1]['bytes_transferred'] == len(PAYLOAD)
                expected = len(PAYLOAD) if mode == 'known' else None
                assert all(event['total_bytes'] == expected for event in events)
                assert all(a['bytes_transferred'] < b['bytes_transferred']
                           for a, b in zip(events, events[1:]))
                report['cases'].append({'mode': mode, 'events': events,
                    'result_bytes': result.bytes_transferred, 'total_bytes': result.total_bytes,
                    'status_code': result.status_code,
                    'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                    'remaining_part_files': len(list(root.glob('*.part')))})
            output = root / 'existing.bin'
            output.write_bytes(b'original')
            events = []
            def abort(event):
                events.append({'bytes_transferred': event.bytes_transferred,
                               'total_bytes': event.total_bytes})
                raise ProbeAbort('owned test interruption')
            try:
                download(f'http://127.0.0.1:{server.server_port}/known', output,
                         progress=abort, chunk_size=128, timeout=2)
            except ProbeAbort:
                pass
            else:
                raise AssertionError('callback abort did not propagate')
            preserved = output.read_bytes() == b'original'
            parts = list(root.glob('*.part'))
            assert preserved and not parts
            report['cases'].append({'mode': 'callback_abort_first_chunk',
                'events': events, 'old_output_preserved': preserved,
                'remaining_part_files': len(parts)})
    finally:
        server.shutdown()
        server.server_close()
        worker.join(2)
    assert not worker.is_alive()
    report['server_stopped'] = True
    report['temporary_directory_cleaned'] = not root.exists()
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(run(), indent=2) + '\n', encoding='utf-8')
