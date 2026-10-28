from dataclasses import replace
import unittest

from cereja.ui._capabilities import Capabilities, CapabilityOptions
from cereja.ui.testing import VirtualBackend


class VirtualBackendTests(unittest.TestCase):
    def test_interactive_default_and_redirected_overrides(self):
        backend = VirtualBackend()
        self.assertFalse(backend.capabilities.plain)
        self.assertTrue(backend.capabilities.input_interactive)
        self.assertTrue(backend.capabilities.output_interactive)
        self.assertTrue(backend.capabilities.cursor)
        self.assertTrue(backend.capabilities.paste)
        self.assertEqual(backend.capabilities.color_depth, 256)
        for name in ("input_interactive", "output_interactive"):
            redirected = VirtualBackend(**{name: False}, options=CapabilityOptions(
                color=24, cursor=True, alternate_screen=True, paste=True))
            self.assertTrue(redirected.capabilities.plain)
            self.assertEqual(redirected.capabilities.color_depth, 0)
            self.assertFalse(redirected.capabilities.cursor)
        chosen = replace(backend.capabilities, reduced_motion=True)
        self.assertIs(VirtualBackend(capabilities=chosen).capabilities, chosen)
        with self.assertRaises(ValueError):
            VirtualBackend(capabilities=chosen, options=CapabilityOptions())
        with self.assertRaises(TypeError):
            VirtualBackend(capabilities={})

    def test_identity_is_unique_or_explicit(self):
        self.assertIsNot(VirtualBackend().identity, VirtualBackend().identity)
        terminal = object()
        self.assertIs(VirtualBackend(identity=terminal).identity, terminal)

    def test_dimensions_are_injected_and_allow_zero(self):
        self.assertEqual(VirtualBackend(size=(0, 0)).dimensions(), (0, 0))
        sizes = iter(((10, 4), (0, 4), (10, 0)))
        backend = VirtualBackend(size=lambda: next(sizes))
        self.assertEqual(backend.dimensions(), (10, 4))
        self.assertEqual(backend.dimensions(), (0, 4))
        self.assertEqual(backend.dimensions(), (10, 0))
        for size in ((-1, 2), (True, 2), (1.0, 2)):
            with self.subTest(size=size), self.assertRaises(ValueError):
                VirtualBackend(size=size)
        with self.assertRaises(TypeError):
            VirtualBackend(size=(1,))

    def test_capture_is_owned_and_restoration_is_idempotent(self):
        backend = VirtualBackend()
        snapshot = backend.capture()
        backend.acquire("cursor", snapshot)
        self.assertTrue(backend.resources["cursor"])
        self.assertFalse(snapshot["cursor"])
        backend.restore("cursor", snapshot)
        backend.restore("cursor", snapshot)
        backend.restore("paste", snapshot)
        self.assertFalse(any(backend.resources.values()))
        self.assertEqual(backend.operations, [
            ("capture",), ("acquire", "cursor"), ("restore", "cursor"),
            ("restore", "cursor"), ("restore", "paste")])

    def test_faults_cover_capture_every_acquisition_and_every_restore(self):
        resources = ("output_mode", "input_mode", "alternate_screen", "cursor",
                     "paste", "signal_handlers")
        error = RuntimeError("capture")
        backend = VirtualBackend(failures={"capture": error})
        with self.assertRaises(RuntimeError) as raised:
            backend.capture()
        self.assertIs(raised.exception, error)
        for resource in resources:
            with self.subTest(resource=resource):
                error = KeyboardInterrupt(resource)
                backend = VirtualBackend(failures={f"acquire:{resource}": error})
                snapshot = backend.capture()
                with self.assertRaises(KeyboardInterrupt) as raised:
                    backend.acquire(resource, snapshot)
                self.assertIs(raised.exception, error)
                backend.restore(resource, snapshot)
                self.assertFalse(backend.resources[resource])
                backend.acquire(resource, snapshot)
                backend.failures[f"restore:{resource}"] = error
                with self.assertRaises(KeyboardInterrupt):
                    backend.restore(resource, snapshot)
                self.assertTrue(backend.resources[resource])
                backend.restore(resource, snapshot)
                self.assertFalse(backend.resources[resource])

    def test_write_counts_and_failure_sequence_are_deterministic(self):
        failure = BrokenPipeError("closed")
        backend = VirtualBackend(write_counts=(1, 0),
                                 failures={"write": [2, None, failure]})
        self.assertEqual(backend.write("abcd"), 2)
        self.assertEqual(backend.write("cd"), 1)
        with self.assertRaises(BrokenPipeError) as raised:
            backend.write("d")
        self.assertIs(raised.exception, failure)
        self.assertEqual(backend.write("d"), 0)
        self.assertEqual(backend.write("d"), 1)
        self.assertEqual(backend.output, "abcd")
        self.assertEqual([op[0] for op in backend.operations], ["write"] * 5)
        backend.flush()
        self.assertEqual(backend.flush_count, 1)
        backend.failures["flush"] = OSError("flush")
        with self.assertRaises(OSError):
            backend.flush()
        self.assertEqual(backend.flush_count, 1)

    def test_exception_classes_and_callables_can_be_injected(self):
        backend = VirtualBackend(failures={"flush": RuntimeError,
                                          "capture": lambda: KeyboardInterrupt()})
        with self.assertRaises(RuntimeError):
            backend.flush()
        with self.assertRaises(KeyboardInterrupt):
            backend.capture()

    def test_invalid_write_acknowledgements_reach_session_unchanged(self):
        invalid = [None, True, 1.5, -1, 20]
        backend = VirtualBackend(write_counts=invalid)
        for count in invalid:
            self.assertIs(backend.write("text"), count)
        self.assertEqual(backend.output, "")

    def test_cell_commits_copy_owned_rectangles_and_do_not_parse_output(self):
        backend = VirtualBackend(size=(0, 0))
        cells = [[{"text": "a"}, {"text": "b"}]]
        backend.commit_cells(cells)
        cells[0][0]["text"] = "changed"
        self.assertEqual(backend.cells[0][0]["text"], "a")
        returned = backend.cells
        returned[0][0]["text"] = "changed again"
        self.assertEqual(backend.cells[0][0]["text"], "a")
        backend.write("\x1b[2J")
        self.assertEqual(backend.cells[0][0]["text"], "a")
        with self.assertRaises(ValueError):
            backend.commit_cells([[1, 2], [3]])
        self.assertEqual(len(backend.cell_frames), 1)
        backend.commit_cells([])
        self.assertEqual(backend.cells, ())
        backend.commit_cells([[], []])
        self.assertEqual(backend.cells, ((), ()))
        backend.invalidate()
        self.assertTrue(backend.invalidated)
        backend.commit_cells([[]])
        self.assertFalse(backend.invalidated)

    def test_wait_queue_and_fake_clock_are_deterministic(self):
        external_time = [10.0]
        backend = VirtualBackend(clock=lambda: external_time[0], input_events=("a",))
        self.assertTrue(backend.wait(5))
        self.assertEqual(backend.clock(), 10.0)
        self.assertEqual(backend.read_input(), "a")
        self.assertIsNone(backend.read_input())
        self.assertFalse(backend.wait(0.25))
        self.assertEqual(backend.clock(), 10.25)
        backend.advance(0.5)
        external_time[0] = 11.0
        self.assertEqual(backend.clock(), 11.75)
        backend.inject_input("b", {"resize": (10, 4)})
        self.assertTrue(backend.wait(None))
        self.assertEqual(backend.read_input(), "b")
        self.assertEqual(backend.read_input(), {"resize": (10, 4)})
        self.assertFalse(backend.wait(None))
        self.assertEqual(backend.clock(), 11.75)
        for duration in (-1, float("nan"), float("inf")):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                backend.advance(duration)
        with self.assertRaises(TypeError):
            backend.wait(True)


if __name__ == "__main__":
    unittest.main()
