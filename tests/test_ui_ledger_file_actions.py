"""File actions use real temporary files and preserve exclusive publication."""
import errno
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cereja.tui.file_actions import capture_selection, execute
from cereja.transfers.sinks import AtomicFileSink


class FileActionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'source.bin'
        self.source.write_bytes(b'selected file')
        self.selection = capture_selection(self.source, expected_size=13)
        self.destination = self.root / 'destination.bin'

    def test_copy_preserves_source_and_publishes_complete_file(self):
        text = execute('copy', self.selection, str(self.destination))
        self.assertEqual(self.destination.read_bytes(), self.source.read_bytes())
        self.assertIn('Copied', text)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['destination.bin', 'source.bin'])

    @unittest.skipUnless(os.name == 'nt', 'Windows stat/fstat ctime compatibility')
    def test_windows_descriptor_ctime_may_differ_from_path_creation_time(self):
        actual_fstat = os.fstat

        def change_time(descriptor):
            actual = actual_fstat(descriptor)
            fields = {name: getattr(actual, name) for name in (
                'st_size', 'st_dev', 'st_ino', 'st_mtime_ns', 'st_mode')}
            return SimpleNamespace(**fields, st_ctime_ns=actual.st_ctime_ns + 1000)

        with patch('os.fstat', change_time):
            execute('copy', self.selection, str(self.destination))
        self.assertEqual(self.destination.read_bytes(), b'selected file')

    def test_delete_revalidates_after_commit_phase_notification(self):
        phases = []

        def committing():
            phases.append('committing')
            self.source.write_bytes(b'replaced while sending phase')

        context = SimpleNamespace(running=lambda: phases.append('running'), committing=committing)
        with self.assertRaisesRegex(ValueError, 'changed'):
            execute('delete', self.selection, context=context)
        self.assertEqual(phases, ['running', 'committing'])
        self.assertEqual(self.source.read_bytes(), b'replaced while sending phase')

    def test_move_preserves_file_identity_and_timestamp(self):
        os.utime(self.source, ns=(1_600_000_000_000_000_000, 1_600_000_000_123_456_000))
        self.selection = capture_selection(self.source)
        before = self.source.stat()
        text = execute('move', self.selection, str(self.destination))
        self.assertEqual(self.destination.read_bytes(), b'selected file')
        self.assertFalse(self.source.exists())
        self.assertIn('Moved', text)
        after = self.destination.stat()
        self.assertEqual((after.st_dev, after.st_ino, after.st_mtime_ns),
                         (before.st_dev, before.st_ino, before.st_mtime_ns))

    @unittest.skipUnless(os.name == 'posix', 'POSIX executable permission')
    def test_move_preserves_executable_permission_without_reading_contents(self):
        self.source.chmod(0o750)
        self.selection = capture_selection(self.source)
        with patch('os.open', side_effect=AssertionError('move must not open contents')):
            execute('move', self.selection, str(self.destination))
        self.assertEqual(self.destination.stat().st_mode & 0o777, 0o750)

    @unittest.skipUnless(os.name == 'nt', 'Windows alternate data streams')
    def test_move_preserves_alternate_data_stream(self):
        try:
            Path(str(self.source) + ':cereja-test').write_bytes(b'additional stream')
        except OSError as error:
            self.skipTest(str(error))
        self.selection = capture_selection(self.source)
        execute('move', self.selection, str(self.destination))
        self.assertEqual(Path(str(self.destination) + ':cereja-test').read_bytes(), b'additional stream')

    def test_cross_volume_move_refuses_without_copy_or_source_removal(self):
        operation = 'os.rename' if os.name == 'nt' else 'os.link'
        with patch(operation, side_effect=OSError(errno.EXDEV, 'different device')):
            with self.assertRaisesRegex(ValueError, 'Cross-volume moves are unsupported'):
                execute('move', self.selection, str(self.destination))
        self.assertEqual(self.source.read_bytes(), b'selected file')
        self.assertFalse(self.destination.exists())

    def test_move_destination_race_does_not_replace_competing_file(self):
        operation = 'rename' if os.name == 'nt' else 'link'
        original = getattr(os, operation)

        def race(source, destination, *args, **kwargs):
            self.destination.write_bytes(b'competing file')
            return original(source, destination, *args, **kwargs)

        with patch('os.' + operation, race):
            with self.assertRaises(FileExistsError):
                execute('move', self.selection, str(self.destination))
        self.assertEqual(self.source.read_bytes(), b'selected file')
        self.assertEqual(self.destination.read_bytes(), b'competing file')

    def test_move_revalidates_after_commit_notification(self):
        def committing():
            self.source.write_bytes(b'changed while sending phase')

        context = SimpleNamespace(running=lambda: None, committing=committing)
        with self.assertRaisesRegex(ValueError, 'changed'):
            execute('move', self.selection, str(self.destination), context=context)
        self.assertTrue(self.source.exists())
        self.assertFalse(self.destination.exists())

    def test_delete_only_selected_file(self):
        self.destination.write_bytes(b'other')
        execute('delete', self.selection)
        self.assertFalse(self.source.exists())
        self.assertEqual(self.destination.read_bytes(), b'other')

    def test_existing_destination_is_never_replaced(self):
        for action in ('copy', 'move'):
            with self.subTest(action=action):
                self.destination.write_bytes(b'existing')
                with self.assertRaises(FileExistsError):
                    execute(action, self.selection, str(self.destination))
                self.assertEqual(self.destination.read_bytes(), b'existing')
                self.assertEqual(self.source.read_bytes(), b'selected file')

    def test_source_changed_since_scan_is_refused(self):
        self.source.write_bytes(b'changed')
        for action in ('copy', 'move', 'delete', 'open-directory'):
            with self.subTest(action=action), self.assertRaisesRegex(ValueError, 'changed'):
                execute(action, self.selection, str(self.destination) if action in ('copy', 'move') else None)
        self.assertTrue(self.source.exists())
        self.assertFalse(self.destination.exists())

    def test_capture_checks_observed_scan_size(self):
        with self.assertRaisesRegex(ValueError, 'changed'):
            capture_selection(self.source, expected_size=999)

    def test_publication_failure_cleans_stage_and_keeps_source(self):
        with patch('os.link', side_effect=OSError('unavailable')):
            with self.assertRaises(OSError):
                execute('copy', self.selection, str(self.destination))
        self.assertEqual(list(self.root.iterdir()), [self.source])
        self.assertEqual(self.source.read_bytes(), b'selected file')

    def test_destination_appearing_at_commit_is_preserved(self):
        original = AtomicFileSink.commit

        def race(sink):
            self.destination.write_bytes(b'competing file')
            original(sink)

        with patch.object(AtomicFileSink, 'commit', race):
            with self.assertRaises(FileExistsError):
                execute('copy', self.selection, str(self.destination))
        self.assertEqual(self.destination.read_bytes(), b'competing file')
        self.assertEqual(self.source.read_bytes(), b'selected file')
        self.assertEqual(len(list(self.root.iterdir())), 2)

    def test_source_change_during_copy_prevents_publication(self):
        original = AtomicFileSink.open

        def mutate(sink):
            self.source.write_bytes(b'altered source content')
            return original(sink)

        with patch.object(AtomicFileSink, 'open', mutate):
            with self.assertRaisesRegex(ValueError, 'changed'):
                execute('copy', self.selection, str(self.destination))
        self.assertFalse(self.destination.exists())
        self.assertEqual(len(list(self.root.iterdir())), 1)

    @unittest.skipUnless(os.name == 'posix', 'POSIX link then unlink')
    def test_move_unlink_failure_keeps_both_links(self):
        original = Path.unlink

        def deny_source(path, *args, **kwargs):
            if path == self.source:
                raise PermissionError('denied')
            return original(path, *args, **kwargs)

        with patch.object(Path, 'unlink', deny_source):
            with self.assertRaisesRegex(ValueError, 'linked.*source was not removed'):
                execute('move', self.selection, str(self.destination))
        self.assertEqual(self.source.read_bytes(), self.destination.read_bytes())
        self.assertEqual(self.source.stat().st_ino, self.destination.stat().st_ino)

    @unittest.skipUnless(os.name == 'posix', 'POSIX link then unlink')
    def test_move_change_after_link_keeps_source_and_published_link(self):
        original = os.link

        def change_after_link(source, destination, *args, **kwargs):
            original(source, destination, *args, **kwargs)
            self.source.write_bytes(b'changed after link')

        with patch('os.link', change_after_link):
            with self.assertRaisesRegex(ValueError, 'linked.*source was not removed'):
                execute('move', self.selection, str(self.destination))
        self.assertEqual(self.source.read_bytes(), b'changed after link')
        self.assertEqual(self.destination.read_bytes(), b'changed after link')

    @unittest.skipUnless(os.name == 'posix', 'POSIX link then unlink')
    def test_move_destination_replaced_after_link_is_not_deleted(self):
        original = os.link

        def replace_destination(source, destination, *args, **kwargs):
            original(source, destination, *args, **kwargs)
            self.destination.unlink()
            self.destination.write_bytes(b'competing replacement')

        with patch('os.link', replace_destination):
            with self.assertRaisesRegex(ValueError, 'linked.*source was not removed'):
                execute('move', self.selection, str(self.destination))
        self.assertEqual(self.source.read_bytes(), b'selected file')
        self.assertEqual(self.destination.read_bytes(), b'competing replacement')

    def test_open_directory_uses_argument_array_or_startfile(self):
        if os.name == 'nt':
            with patch('os.startfile') as launch:
                execute('open-directory', self.selection)
            launch.assert_called_once_with(str(self.root))
        else:
            with patch('subprocess.run') as launch:
                execute('open-directory', self.selection)
            self.assertEqual(launch.call_args.args[0][-1], str(self.root))
            self.assertNotIn('shell', launch.call_args.kwargs)

    def test_link_selection_and_link_parent_are_refused(self):
        link = self.root / 'linked.bin'
        parent = self.root / 'linked-dir'
        target = self.root / 'real-dir'
        target.mkdir()
        try:
            link.symlink_to(self.source)
            parent.symlink_to(target, target_is_directory=True)
        except OSError as error:
            self.skipTest(str(error))
        with self.assertRaisesRegex(ValueError, 'Links/reparse'):
            capture_selection(link)
        with self.assertRaisesRegex(ValueError, 'Links/reparse'):
            execute('copy', self.selection, str(parent / 'out.bin'))

    def test_invalid_action_or_missing_destination_has_no_effect(self):
        for action, destination in (('run', None), ('copy', None), ('move', '')):
            with self.subTest(action=action), self.assertRaises(ValueError):
                execute(action, self.selection, destination)
        self.assertEqual(list(self.root.iterdir()), [self.source])


if __name__ == '__main__':
    unittest.main()
