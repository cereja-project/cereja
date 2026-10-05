"""UI-00 session expectations, independent of native terminal adapters."""

import threading
import unittest
from io import StringIO

from cereja.ui.terminal import StreamBackend, TerminalCleanupError, TerminalSession
from cereja.ui.testing import VirtualBackend


RESOURCES = ('output_mode', 'input_mode', 'alternate_screen', 'cursor',
             'paste', 'signal_handlers')


class SessionTest(unittest.TestCase):
    def test_normal_cleanup_restores_every_resource_in_reverse(self):
        backend = VirtualBackend()
        with TerminalSession(backend):
            self.assertEqual({key for key, value in backend.resources.items() if value}, set(RESOURCES))
        self.assertFalse(any(backend.resources.values()))
        restored = [op[1] for op in backend.operations if op[0] == 'restore']
        self.assertEqual(restored, list(reversed(RESOURCES)))

    def test_every_setup_failure_unwinds_including_attempted_step(self):
        for index, name in enumerate(RESOURCES):
            with self.subTest(name=name):
                failure = OSError(name)
                backend = VirtualBackend(failures={'acquire:' + name: failure})
                session = TerminalSession(backend)
                with self.assertRaises(OSError) as caught:
                    session.__enter__()
                self.assertIs(caught.exception, failure)
                self.assertFalse(any(backend.resources.values()))
                restored = [op[1] for op in backend.operations if op[0] == 'restore']
                self.assertEqual(restored, list(reversed(RESOURCES[:index + 1])))
                self.assertTrue(session.closed)
                with TerminalSession(VirtualBackend(identity=backend.identity)):
                    pass

    def test_capture_failure_releases_owner(self):
        backend = VirtualBackend(failures={'capture': OSError('capture')})
        with self.assertRaises(OSError):
            TerminalSession(backend).__enter__()
        self.assertFalse(any(backend.resources.values()))
        with TerminalSession(VirtualBackend(identity=backend.identity)):
            pass

    def test_exception_and_ctrl_c_preserve_original(self):
        for failure in (ValueError('body'), KeyboardInterrupt(), SystemExit(2)):
            backend = VirtualBackend()
            with self.subTest(failure=type(failure).__name__):
                with self.assertRaises(type(failure)) as caught:
                    with TerminalSession(backend):
                        raise failure
                self.assertIs(caught.exception, failure)
                self.assertFalse(any(backend.resources.values()))

    def test_cleanup_attempts_all_steps_and_attaches_to_initiator(self):
        backend = VirtualBackend(failures={
            'restore:paste': OSError('paste'),
            'restore:cursor': KeyboardInterrupt('cursor'),
        })
        failure = ValueError('initiator')
        session = TerminalSession(backend)
        with self.assertRaises(ValueError) as caught:
            with session:
                raise failure
        self.assertIs(caught.exception, failure)
        self.assertEqual(len(session.cleanup_failures), 2)
        self.assertEqual(len(failure.__notes__), 2)
        restored = [op[1] for op in backend.operations if op[0] == 'restore']
        self.assertEqual(restored, list(reversed(RESOURCES)))

    def test_cleanup_error_without_initiator_is_visible_and_idempotent(self):
        backend = VirtualBackend(failures={'restore:cursor': OSError('cursor')})
        session = TerminalSession(backend)
        with self.assertRaises(TerminalCleanupError) as caught:
            with session:
                pass
        self.assertEqual(len(caught.exception.failures), 1)
        before = list(backend.operations)
        session.close()
        self.assertEqual(backend.operations, before)

    def test_cleanup_diagnostics_cannot_mask_original_exception(self):
        class BadRepr:
            def __repr__(self):
                raise RuntimeError('repr failed')

        class BadNote(ValueError):
            def add_note(self, note):
                raise RuntimeError('note failed')

        for primary, cleanup in ((ValueError('body'), OSError(BadRepr())),
                                 (BadNote('body'), OSError('cleanup'))):
            with self.subTest(primary=type(primary).__name__):
                backend = VirtualBackend(failures={'restore:cursor': cleanup})
                with self.assertRaises(type(primary)) as caught:
                    with TerminalSession(backend) as session:
                        raise primary
                self.assertIs(caught.exception, primary)
                self.assertIs(session.cleanup_failures[0][1], cleanup)

    def test_mutation_before_acquisition_failure_is_restored(self):
        class MutatingBackend(VirtualBackend):
            def acquire(self, resource, snapshot):
                super().acquire(resource, snapshot)
                if resource == 'cursor':
                    raise OSError('mutated before failure')

        backend = MutatingBackend()
        with self.assertRaises(OSError):
            TerminalSession(backend).__enter__()
        self.assertFalse(any(backend.resources.values()))

    def test_nested_and_distinct_backend_alias_owner_rejected(self):
        first = VirtualBackend(identity='terminal')
        with TerminalSession(first):
            with self.assertRaises(RuntimeError):
                TerminalSession(first).__enter__()
            with self.assertRaises(RuntimeError):
                TerminalSession(VirtualBackend(identity='terminal')).__enter__()
            with TerminalSession(VirtualBackend(identity='other')):
                pass

    def test_suspension_restores_reserves_owner_and_reacquires(self):
        backend = VirtualBackend()
        with TerminalSession(backend) as session:
            with session.suspend():
                self.assertFalse(any(backend.resources.values()))
                with self.assertRaises(RuntimeError):
                    TerminalSession(VirtualBackend(identity=backend.identity)).__enter__()
                with self.assertRaises(RuntimeError):
                    session.write_text('suspended')
            self.assertEqual({key for key, value in backend.resources.items() if value}, set(RESOURCES))
            self.assertTrue(session.needs_redraw)
            self.assertIn(('invalidate',), backend.operations)
        self.assertFalse(any(backend.resources.values()))

    def test_failed_reacquisition_ends_session_and_releases_owner(self):
        backend = VirtualBackend()
        with self.assertRaises(OSError):
            with TerminalSession(backend) as session:
                with session.suspend():
                    backend.failures['acquire:cursor'] = OSError('resume')
        self.assertTrue(session.closed)
        self.assertFalse(any(backend.resources.values()))
        with TerminalSession(VirtualBackend(identity=backend.identity)):
            pass

    def test_suspended_body_exception_does_not_reacquire(self):
        backend = VirtualBackend()
        with self.assertRaises(ValueError):
            with TerminalSession(backend) as session:
                with session.suspend():
                    raise ValueError('external')
        acquisitions = [op for op in backend.operations if op[0] == 'acquire']
        self.assertEqual(len(acquisitions), len(RESOURCES))

    def test_plain_mode_never_acquires_modes_or_schedules_animation(self):
        for stdin, stdout in ((False, True), (True, False), (False, False)):
            with self.subTest(stdin=stdin, stdout=stdout):
                backend = VirtualBackend(input_interactive=stdin,
                                         output_interactive=stdout)
                with TerminalSession(backend) as session:
                    session.write_text('a\x1b[31mb\x00\x85\t\n')
                self.assertNotIn('\x1b', backend.output)
                self.assertIn('\\x1b', backend.output)
                self.assertFalse(any(op[0] == 'acquire' for op in backend.operations))
                self.assertFalse(session.animations_enabled)

    def test_short_writes_use_only_unwritten_suffix_and_flush_once(self):
        backend = VirtualBackend(write_counts=[2, 1, 3])
        with TerminalSession(backend) as session:
            self.assertTrue(session._write_frame('abcdef'))
        writes = [op[1] for op in backend.operations if op[0] == 'write']
        self.assertEqual(writes, ['abcdef', 'cdef', 'def'])
        self.assertEqual(backend.output, 'abcdef')
        self.assertEqual(sum(op[0] == 'flush' for op in backend.operations), 1)

    def test_invalid_acknowledgments_and_flush_failure_never_commit_cells(self):
        for count in (0, -1, None, True, 100, 1.5):
            with self.subTest(count=count):
                backend = VirtualBackend(size=(1, 1), write_counts=[count])
                with self.assertRaises(OSError):
                    with TerminalSession(backend) as session:
                        session._write_frame('x', cells=[['x']])
                self.assertNotEqual(backend.cells, (('x',),))
                self.assertTrue(session.needs_redraw)
        backend = VirtualBackend(size=(1, 1), failures={'flush': OSError('flush')})
        with self.assertRaises(OSError):
            with TerminalSession(backend) as session:
                session._write_frame('x', cells=[['x']])
        self.assertNotEqual(backend.cells, (('x',),))

    def test_write_failure_preserves_original_and_unwinds(self):
        failure = OSError('transport')
        backend = VirtualBackend(failures={'write': failure})
        with self.assertRaises(OSError) as caught:
            with TerminalSession(backend) as session:
                session.write_text('hello')
        self.assertIs(caught.exception, failure)
        self.assertFalse(any(backend.resources.values()))

    def test_broken_pipe_stops_cleanly_but_cleanup_failure_is_visible(self):
        backend = VirtualBackend(failures={'write': BrokenPipeError()})
        with TerminalSession(backend) as session:
            self.assertFalse(session.write_text('hello'))
            self.assertTrue(session.closed)
            self.assertTrue(session.broken_pipe)
        backend = VirtualBackend(failures={'write': BrokenPipeError(),
                                          'restore:cursor': OSError('restore')})
        with self.assertRaises(TerminalCleanupError):
            with TerminalSession(backend) as session:
                session.write_text('hello')

    def test_cells_committed_only_after_successful_flush(self):
        backend = VirtualBackend(size=(1, 1))
        with TerminalSession(backend) as session:
            session._write_frame('x', cells=[['x']])
        self.assertEqual(backend.cells, (('x',),))
        names = [op[0] for op in backend.operations]
        self.assertLess(names.index('flush'), names.index('commit_cells'))

    def test_empty_frame_has_zero_writes_and_flushes(self):
        backend = VirtualBackend()
        with TerminalSession(backend) as session:
            session._write_frame('')
        self.assertFalse(any(op[0] in ('write', 'flush') for op in backend.operations))

    def test_session_is_bound_to_owner_thread(self):
        backend = VirtualBackend()
        failures = []
        with TerminalSession(backend) as session:
            def worker():
                for action in (lambda: session.write_text('worker'), session.close):
                    try:
                        action()
                    except RuntimeError as error:
                        failures.append(error)
            thread = threading.Thread(target=worker)
            thread.start()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(len(failures), 2)
        self.assertFalse(any(backend.resources.values()))

    def test_real_redirected_streams_emit_useful_plain_output(self):
        output = StringIO()
        backend = StreamBackend(StringIO('input'), output,
                                environ={'TERM': 'xterm-256color'})
        with TerminalSession(backend) as session:
            session.write_text('result\x1b[31m\n')
        self.assertEqual(output.getvalue(), 'result\\x1b[31m\n')
        self.assertTrue(backend.capabilities.plain)

    def test_unavailable_output_ends_plain_session_with_original_error(self):
        output = StringIO()
        output.close()
        backend = StreamBackend(StringIO(), output)
        with self.assertRaises(ValueError):
            with TerminalSession(backend) as session:
                session.write_text('unavailable')
        self.assertTrue(session.closed)
        with TerminalSession(backend):
            pass

    def test_suspension_recaptures_external_resource_changes(self):
        backend = VirtualBackend()
        with TerminalSession(backend) as session:
            with session.suspend():
                backend.resources['cursor'] = True
        self.assertTrue(backend.resources['cursor'])
        self.assertFalse(any(value for key, value in backend.resources.items()
                             if key != 'cursor'))


if __name__ == '__main__':
    unittest.main()
