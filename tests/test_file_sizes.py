"""Metadata-only large-file search, including incomplete filesystem scans."""

import errno
import io
import json
import os
from pathlib import Path
import random
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cereja.system.file_sizes import find_large_files


class FileSizesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def file(self, name, size):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('wb') as stream:
            stream.truncate(size)
        return path

    def test_known_sizes_hidden_binary_and_ignored_paths_without_content_reads(self):
        expected = {
            '.hidden': 31, '.git/objects/data': 30, '__pycache__/large.pyc': 29,
            'nested/data.bin': 28, 'ignored.tmp': 27, 'empty': 0,
        }
        for name, size in expected.items():
            self.file(name, size)
        (self.root / '.gitignore').write_bytes(b'*.tmp\n\x00\xff')
        expected['.gitignore'] = 8
        with patch('builtins.open', side_effect=AssertionError('content read')), \
                patch('io.open', side_effect=AssertionError('content read')), \
                patch('os.open', side_effect=AssertionError('content read')):
            report = find_large_files(self.root)
        self.assertTrue(report.complete)
        self.assertFalse(report.results_truncated)
        self.assertEqual({f.relative_path: f.size_bytes for f in report.files}, expected)
        self.assertEqual(report.scanned_files, len(expected))
        self.assertEqual(report.matched_files, len(expected))
        self.assertEqual(report.error_count, 0)
        for item in report.files:
            self.assertEqual(item.path, str(self.root / item.relative_path))

    def test_threshold_top_k_and_path_ties_match_independent_sort(self):
        sizes = [random.Random(42 + index).randrange(200) for index in range(130)]
        expected = []
        for index, size in enumerate(sizes):
            name = f'd{index % 3}/file-{index:03}.bin'
            self.file(name, size)
            if size >= 90:
                expected.append((name, size))
        for name in ('z-tie', 'a-tie', 'B-tie'):
            self.file(name, 1000)
            expected.append((name, 1000))
        expected.sort(key=lambda row: (-row[1], row[0]))
        report = find_large_files(self.root, min_size_bytes=90, max_results=7)
        self.assertEqual([(f.relative_path, f.size_bytes) for f in report.files], expected[:7])
        self.assertEqual(report.matched_files, len(expected))
        self.assertEqual(report.scanned_files, len(sizes) + 3)
        self.assertTrue(report.complete)
        self.assertTrue(report.results_truncated)

    def test_empty_root_and_no_matches(self):
        self.assertTrue(find_large_files(self.root).complete)
        self.file('one', 3)
        report = find_large_files(self.root, min_size_bytes=4)
        self.assertEqual(report.files, ())
        self.assertTrue(report.complete)
        self.assertEqual(report.scanned_files, 1)
        self.assertEqual(report.matched_files, 0)

    def test_entry_limit_closes_real_iterators_and_reports_partial_top(self):
        for index in range(20):
            self.file(f'file-{index}', index)
        streams = []
        real_scandir = os.scandir

        def track(path):
            stream = real_scandir(path)
            streams.append(stream)
            return stream

        with patch('cereja.system.file_sizes.os.scandir', side_effect=track):
            report = find_large_files(self.root, max_entries=5, max_results=2)
        self.assertFalse(report.complete)
        self.assertIn('max_entries', report.reasons)
        self.assertEqual(report.examined_entries, 5)
        self.assertEqual(report.scanned_files, 5)
        self.assertEqual(len(report.files), 2)
        for stream in streams:
            self.assertEqual(list(stream), [])

    def test_exact_entry_cap_is_conservatively_incomplete(self):
        self.file('one', 1)
        report = find_large_files(self.root, max_entries=1)
        self.assertFalse(report.complete)
        self.assertEqual(report.examined_entries, 1)

    def test_depth_zero_includes_root_files_but_reports_unvisited_directories(self):
        self.file('root', 1)
        self.file('sub/large', 100)
        report = find_large_files(self.root, max_depth=0)
        self.assertEqual([f.relative_path for f in report.files], ['root'])
        self.assertFalse(report.complete)
        self.assertIn('max_depth', report.reasons)
        self.assertEqual([f.relative_path for f in find_large_files(self.root, max_depth=1).files],
                         ['sub/large', 'root'])

    def test_directory_permission_failure_is_partial_and_retained_errors_are_bounded(self):
        for index in range(4):
            (self.root / str(index)).mkdir()
        self.file('good', 8)
        real_scandir = os.scandir

        def denied(path):
            if Path(path) != self.root:
                raise PermissionError(errno.EACCES, 'denied', str(path))
            return real_scandir(path)

        with patch('cereja.system.file_sizes.os.scandir', side_effect=denied):
            report = find_large_files(self.root, max_errors=2)
        self.assertEqual([f.relative_path for f in report.files], ['good'])
        self.assertFalse(report.complete)
        self.assertEqual(report.error_count, 4)
        self.assertEqual(len(report.errors), 2)
        self.assertTrue(all(e.operation == 'scandir' and e.errno == errno.EACCES for e in report.errors))
        self.assertIn('filesystem_error', report.reasons)

    def test_disappeared_file_does_not_abort_remaining_entries(self):
        self.file('good', 10)
        missing = SimpleNamespace(name='gone', path=str(self.root / 'gone'))
        missing.stat = lambda **kwargs: (_ for _ in ()).throw(FileNotFoundError(errno.ENOENT, 'gone'))
        with os.scandir(self.root) as stream:
            entries = [missing, *stream]
        with patch('cereja.system.file_sizes.os.scandir', return_value=FakeScan(entries)):
            report = find_large_files(self.root, max_errors=0)
        self.assertFalse(report.complete)
        self.assertEqual(report.error_count, 1)
        self.assertEqual(report.errors, ())
        self.assertEqual([f.relative_path for f in report.files], ['good'])

    def test_root_enumeration_failure_is_an_incomplete_report(self):
        with patch('cereja.system.file_sizes.os.scandir', side_effect=PermissionError(errno.EACCES, 'denied')):
            report = find_large_files(self.root)
        self.assertFalse(report.complete)
        self.assertEqual(report.examined_entries, 0)
        self.assertEqual(report.error_count, 1)
        self.assertEqual(report.errors[0].operation, 'scandir')

    def test_enumeration_error_keeps_previous_results_and_closes_stream(self):
        self.file('good', 10)
        with os.scandir(self.root) as stream:
            entries = list(stream)
        scan = FakeScan(entries, failure=OSError(errno.EIO, 'enumeration failed'))
        with patch('cereja.system.file_sizes.os.scandir', return_value=scan):
            report = find_large_files(self.root)
        self.assertEqual([f.relative_path for f in report.files], ['good'])
        self.assertFalse(report.complete)
        self.assertEqual(report.errors[0].operation, 'scandir')
        self.assertTrue(scan.closed)

    def test_root_validation_and_strict_limits(self):
        with self.assertRaises(FileNotFoundError):
            find_large_files(self.root / 'missing')
        with self.assertRaises(NotADirectoryError):
            find_large_files(self.file('file', 1))
        for name in ('max_results', 'max_entries'):
            for value in (0, -1, True, 1.5):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    find_large_files(self.root, **{name: value})
        for name in ('min_size_bytes', 'max_depth', 'max_errors'):
            for value in (-1, True, 1.5):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    find_large_files(self.root, **{name: value})

    def test_file_directory_and_broken_symlinks_are_skipped_and_linked_roots_rejected(self):
        target = self.file('target/data', 25)
        try:
            (self.root / 'linked-file').symlink_to(target)
            (self.root / 'linked-dir').symlink_to(target.parent, target_is_directory=True)
            (self.root / 'broken').symlink_to(self.root / 'missing')
        except OSError as error:
            self.skipTest(f'symlink creation unavailable: {error}')
        report = find_large_files(self.root)
        self.assertEqual([f.relative_path for f in report.files], ['target/data'])
        self.assertEqual(report.skipped_links, 3)
        self.assertTrue(report.complete)
        with self.assertRaises(NotADirectoryError):
            find_large_files(self.root / 'linked-dir')
        (target.parent / 'nested').mkdir()
        with self.assertRaises(NotADirectoryError):
            find_large_files(self.root / 'linked-dir' / 'nested')

    @unittest.skipUnless(os.name == 'nt', 'Windows junctions')
    def test_windows_junction_is_skipped_and_rejected_as_root_or_ancestor(self):
        target = self.root / 'target'
        target.mkdir()
        (target / 'nested').mkdir()
        junction = self.root / 'junction'
        result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(target)],
                                capture_output=True, timeout=15)
        if result.returncode:
            self.skipTest('junction creation unavailable')
        self.addCleanup(lambda: junction.rmdir() if junction.exists() else None)
        report = find_large_files(self.root)
        self.assertEqual(report.skipped_links, 1)
        with self.assertRaises(NotADirectoryError):
            find_large_files(junction)
        with self.assertRaises(NotADirectoryError):
            find_large_files(junction / 'nested')

    def test_reparse_and_special_entries_never_become_files_or_directories(self):
        def entry(name, mode, attributes=0):
            item = SimpleNamespace(name=name, path=str(self.root / name))
            metadata = SimpleNamespace(st_mode=mode, st_size=999, st_file_attributes=attributes)

            def metadata_only(*, follow_symlinks):
                self.assertFalse(follow_symlinks)
                return metadata

            item.stat = metadata_only
            return item

        scan = FakeScan([entry('reparse', stat.S_IFDIR, 0x400), entry('symlink', stat.S_IFLNK),
                         entry('fifo', stat.S_IFIFO), entry('socket', stat.S_IFSOCK)])
        with patch('cereja.system.file_sizes.os.scandir', return_value=scan):
            report = find_large_files(self.root)
        self.assertEqual(report.files, ())
        self.assertEqual(report.skipped_links, 2)
        self.assertEqual(report.skipped_special, 2)
        self.assertTrue(report.complete)

    def test_interruption_closes_all_active_directory_streams(self):
        (self.root / 'sub').mkdir()
        with os.scandir(self.root) as stream:
            parent = FakeScan(list(stream))
        child = FakeScan([], failure=KeyboardInterrupt())
        with patch('cereja.system.file_sizes.os.scandir', side_effect=[parent, child]):
            with self.assertRaises(KeyboardInterrupt):
                find_large_files(self.root)
        self.assertTrue(parent.closed)
        self.assertTrue(child.closed)

    @unittest.skipIf(os.name == 'nt', 'POSIX FIFO creation')
    def test_real_fifo_is_not_opened(self):
        os.mkfifo(self.root / 'pipe')
        report = find_large_files(self.root)
        self.assertEqual(report.files, ())
        self.assertEqual(report.skipped_special, 1)


class FakeScan:
    def __init__(self, entries, failure=None):
        self.entries = iter(entries)
        self.failure = failure
        self.closed = False

    def __next__(self):
        try:
            return next(self.entries)
        except StopIteration:
            if self.failure is not None:
                raise self.failure
            raise

    def close(self):
        self.closed = True


class FileSizesCliTest(unittest.TestCase):
    def run_cli(self, *args):
        from cereja.entrypoint import main
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch('sys.stdout', stdout), patch('sys.stderr', stderr):
            code = main(['large-files', *map(str, args)])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_actual_root_dispatch_json_and_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / '.binary').write_bytes(b'\x00\xff' * 20)
            (root / 'small').write_bytes(b'x')
            code, output, error = self.run_cli(root, '--min-size-bytes', 2, '--max-results', 1,
                                               '--format', 'json')
            self.assertEqual(code, 0, error)
            data = json.loads(output)
            self.assertTrue(data['complete'])
            self.assertEqual(data['files'][0]['size_bytes'], 40)
            self.assertEqual(data['files'][0]['relative_path'], '.binary')
            self.assertEqual(data['matched_files'], 1)
            code, output, error = self.run_cli(root, '--max-results', 1)
            self.assertEqual(code, 0, error)
            self.assertIn('results_truncated: True', output)
            self.assertIn('40', output)

    def test_partial_results_have_distinct_exit_code_and_json(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'one').touch()
            code, output, error = self.run_cli(directory, '--max-entries', 1, '--format', 'json')
        self.assertEqual(code, 3)
        self.assertEqual(error, '')
        self.assertFalse(json.loads(output)['complete'])
        self.assertIn('max_entries', json.loads(output)['reasons'])

    def test_invalid_root_prints_only_stderr_and_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            code, output, error = self.run_cli(Path(directory) / 'missing')
        self.assertEqual(code, 1)
        self.assertEqual(output, '')
        self.assertIn('Error:', error)

    def test_root_is_required_and_limits_are_usage_errors(self):
        for args in ([], ['.', '--max-results', '0'], ['.', '--min-size-bytes', '-1']):
            with self.subTest(args=args), self.assertRaises(SystemExit) as raised:
                self.run_cli(*args)
            self.assertEqual(raised.exception.code, 2)

    def test_error_paths_are_escaped_too(self):
        code, output, error = self.run_cli('missing\x1b[31m\nroot')
        self.assertEqual(code, 1)
        self.assertEqual(output, '')
        self.assertNotIn('\x1b', error)
        self.assertEqual(len(error.splitlines()), 1)

    def test_command_help_never_scans_or_loads_ledger(self):
        script = '''
import contextlib
import io
import sys
from unittest.mock import patch
from cereja.entrypoint import main
with patch('os.scandir', side_effect=AssertionError('scan during help')):
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            main(['large-files', '--help'])
        except SystemExit as error:
            assert error.code == 0
assert not any(name.startswith(('cereja.tui', 'cereja.ledger', 'cereja.ui', 'cereja.system._context',
                                'cereja.system._repository')) for name in sys.modules)
'''
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipIf(os.name == 'nt', 'POSIX literal control characters in names')
    def test_terminal_controls_in_paths_are_escaped(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'bad\x1b[31m\nname').touch()
            code, output, error = self.run_cli(directory)
        self.assertEqual(code, 0, error)
        self.assertNotIn('\x1b', output)
        self.assertIn('\\u001b', output)
        self.assertIn('\\nname', output)


if __name__ == '__main__':
    unittest.main()
