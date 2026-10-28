"""Native VT probes must be acquired and unwound under session ownership."""

from dataclasses import replace
import unittest

from cereja.ui.terminal import TerminalSession
from cereja.ui.testing import VirtualBackend


class ProbeBackend(VirtualBackend):
    needs_output_probe = True

    def __init__(self, *, supported=True, failures=None):
        super().__init__(failures=failures)
        self.interactive_caps = self.capabilities
        self.capabilities = replace(self.capabilities, plain=True, cursor=False,
                                    color_depth=0, alternate_screen=False, paste=False)
        self.supported = supported

    def acquire(self, resource, snapshot):
        super().acquire(resource, snapshot)
        if resource == 'output_mode' and self.supported:
            self.capabilities = self.interactive_caps


class NativeSessionProbeTest(unittest.TestCase):
    def test_successful_probe_gates_raw_input_and_is_not_duplicated(self):
        backend = ProbeBackend()
        with TerminalSession(backend) as session:
            self.assertFalse(session.capabilities.plain)
            acquired = [o[1] for o in backend.operations if o[0] == 'acquire']
            self.assertEqual(acquired.count('output_mode'), 1)
            self.assertEqual(acquired[:2], ['output_mode', 'input_mode'])
        self.assertFalse(any(backend.resources.values()))

    def test_unsupported_probe_stays_plain_and_still_restores_output(self):
        backend = ProbeBackend(supported=False)
        with TerminalSession(backend) as session:
            self.assertTrue(session.capabilities.plain)
            session.write_text('plain\x1b[31m')
        acquired = [o[1] for o in backend.operations if o[0] == 'acquire']
        restored = [o[1] for o in backend.operations if o[0] == 'restore']
        self.assertEqual(acquired, ['output_mode'])
        self.assertEqual(restored, ['output_mode'])
        self.assertNotIn('\x1b', ''.join(backend.writes))

    def test_failed_probe_is_journaled_before_mutation(self):
        error = OSError('probe failed')
        backend = ProbeBackend(failures={'acquire:output_mode': error})
        session = TerminalSession(backend)
        with self.assertRaises(OSError) as caught:
            session.__enter__()
        self.assertIs(caught.exception, error)
        self.assertEqual([o[1] for o in backend.operations if o[0] == 'restore'],
                         ['output_mode'])
        self.assertTrue(session.closed)


if __name__ == '__main__':
    unittest.main()
