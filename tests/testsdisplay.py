"""
Tests for cereja.display module.

Covers _ConsoleBase (via console singleton), Progress, and State classes.
"""
import unittest
import io
import sys
import threading

from cereja.display import console, Progress, State


class TestConsoleBase(unittest.TestCase):
    """Tests for the console singleton and _ConsoleBase."""

    def test_set_prefix(self):
        """set_prefix should change prefix_name."""
        original = console.prefix_name
        try:
            console.set_prefix("TestPrefix")
            self.assertEqual(console.prefix_name, "TestPrefix")
        finally:
            console.set_prefix(original)

    def test_set_prefix_rejects_non_string(self):
        """set_prefix should raise TypeError for non-string values."""
        with self.assertRaises(TypeError):
            console.set_prefix(123)

    def test_text_color_setter(self):
        """text_color should accept valid color names."""
        console.text_color = "red"
        console.text_color = "default"

    def test_text_color_rejects_invalid(self):
        """text_color should raise ValueError for invalid colors."""
        with self.assertRaises(ValueError):
            console.text_color = "nonexistent_color"

    def test_format_basic(self):
        """format should wrap text with ANSI color codes."""
        result = console.format("hello", color="red")
        self.assertIn("hello", result)
        # Should contain ANSI escape codes
        self.assertIn("\033[", result)

    def test_format_invalid_color(self):
        """format should raise ValueError for unknown color."""
        with self.assertRaises(ValueError):
            console.format("hello", color="invisible")

    def test_format_random(self):
        """format with 'random' color should not raise."""
        result = console.format("test", color="random")
        self.assertIn("test", result)

    def test_parse(self):
        """parse should return formatted message with prefix."""
        result = console.parse("test message")
        self.assertIn("test message", result)

    def test_template_format(self):
        """template_format should replace color placeholders."""
        result = console.template_format("{red}error{endred}")
        self.assertIn("\033[", result)

    def test_colorful_words_string(self):
        """colorful_words should accept a string."""
        result = console.colorful_words("hello world")
        self.assertIn("hello", result)
        self.assertIn("world", result)

    def test_colorful_words_list(self):
        """colorful_words should accept a list of strings."""
        result = console.colorful_words(["hello", "world"])
        self.assertIn("hello", result)

    def test_translate_non_bmp(self):
        """translate_non_bmp should handle non-BMP characters without error."""
        result = console.translate_non_bmp("hello \U0001F352 world")
        self.assertIsInstance(result, str)


class TestProgress(unittest.TestCase):
    """Tests for Progress class."""

    def setUp(self):
        self.default_stdout = sys.stdout
        self.default_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()

    def tearDown(self):
        console.disable()
        sys.stdout = self.default_stdout
        sys.stderr = self.default_stderr

    def test_progress_with_sequence(self):
        """Progress.prog should iterate over a sequence."""
        items = list(range(10))
        result = []
        for i in Progress.prog(items, name="test"):
            result.append(i)
        self.assertEqual(result, items)

    def test_progress_with_empty_sequence(self):
        """Progress.prog should handle empty sequences."""
        result = list(Progress.prog([], name="test_empty"))
        self.assertEqual(result, [])

    def test_progress_iterates_all_items(self):
        """Progress.prog should yield all items."""
        items = list(range(20))
        result = list(Progress.prog(items, name="all_items"))
        self.assertEqual(result, items)

    def test_progress_restores_runtime_std_streams(self):
        """Progress should restore stdout/stderr to the active runtime streams."""
        default_stdout = sys.stdout
        default_stderr = sys.stderr
        runtime_stdout = io.StringIO()
        runtime_stderr = io.StringIO()
        try:
            sys.stdout = runtime_stdout
            sys.stderr = runtime_stderr

            result = list(Progress.prog([1, 2, 3], name="restore_streams"))
            self.assertEqual(result, [1, 2, 3])
            self.assertIs(sys.stdout, runtime_stdout)
            self.assertIs(sys.stderr, runtime_stderr)
        finally:
            sys.stdout = default_stdout
            sys.stderr = default_stderr

    def test_progress_flushes_prints_while_active(self):
        """Progress should keep user prints visible while stdout is managed."""
        default_stdout = sys.stdout
        default_stderr = sys.stderr
        runtime_stdout = io.StringIO()
        runtime_stderr = io.StringIO()
        try:
            sys.stdout = runtime_stdout
            sys.stderr = runtime_stderr

            for item in Progress.prog([1], name="flush_prints"):
                print(f"current: {item}")

            output = runtime_stdout.getvalue()
            self.assertIn("current: 1", output)
            self.assertIn("flush_prints", output)
            self.assertIs(sys.stdout, runtime_stdout)
            self.assertIs(sys.stderr, runtime_stderr)
        finally:
            console.disable()
            sys.stdout = default_stdout
            sys.stderr = default_stderr

    def test_progress_propagates_iteration_errors(self):
        """Progress should not swallow exceptions raised by the iterable."""
        def failing_sequence():
            yield 1
            raise RuntimeError("boom")

        with self.assertRaisesRegex(RuntimeError, "boom"):
            list(Progress.prog(failing_sequence(), name="failing"))

    def test_progress_does_not_start_background_thread(self):
        """Progress rendering should not create a background progress thread."""
        progress = Progress(name="no_thread", max_value=1)
        try:
            with progress:
                progress.show_progress(1)

            self.assertIsNone(progress._th_root)
        finally:
            console.disable()

    def test_show_progress_from_threads_finishes(self):
        """Concurrent show_progress calls should finish without deadlock."""
        progress = Progress(name="threaded_updates", max_value=30)
        workers = [
            threading.Thread(target=progress.show_progress, args=(value,))
            for value in range(1, 6)
        ]

        try:
            with progress:
                for worker in workers:
                    worker.start()
                for worker in workers:
                    worker.join(timeout=1)

            self.assertTrue(all(not worker.is_alive() for worker in workers))
        finally:
            console.disable()

    def test_nested_progress_keeps_outer_stream_capture(self):
        """Disabling an inner progress should not restore streams for the outer one."""
        default_stdout = sys.stdout
        default_stderr = sys.stderr
        runtime_stdout = io.StringIO()
        runtime_stderr = io.StringIO()
        try:
            sys.stdout = runtime_stdout
            sys.stderr = runtime_stderr

            with Progress(name="outer", max_value=2) as outer:
                print("outer-start")
                with Progress(name="inner", max_value=1) as inner:
                    inner.show_progress(1)
                print("outer-after-inner")
                outer.show_progress(2)

            output = runtime_stdout.getvalue()
            self.assertIn("outer-start", output)
            self.assertIn("outer-after-inner", output)
            self.assertIs(sys.stdout, runtime_stdout)
            self.assertIs(sys.stderr, runtime_stderr)
        finally:
            console.disable()
            sys.stdout = default_stdout
            sys.stderr = default_stderr

    def test_context_progress_reuses_instance_for_multiple_sequences(self):
        """A context-managed Progress should reset counters between sequences."""
        default_stdout = sys.stdout
        default_stderr = sys.stderr
        runtime_stdout = io.StringIO()
        runtime_stderr = io.StringIO()
        try:
            sys.stdout = runtime_stdout
            sys.stderr = runtime_stderr

            with Progress(name="reuse", max_value=2) as progress:
                first = list(progress([1, 2]))
                second = list(progress([3]))

            self.assertEqual(first, [1, 2])
            self.assertEqual(second, [3])
            self.assertIn("reuse", runtime_stdout.getvalue())
            self.assertIs(sys.stdout, runtime_stdout)
            self.assertIs(sys.stderr, runtime_stderr)
        finally:
            console.disable()
            sys.stdout = default_stdout
            sys.stderr = default_stderr


class TestState(unittest.TestCase):
    """Tests for State abstract class and concrete implementations."""

    def test_state_is_abstract(self):
        """State should not be instantiable directly."""
        with self.assertRaises(TypeError):
            State()

    def test_concrete_state_has_name(self):
        """Concrete State subclasses should have a name property."""
        from cereja.display._display import _StateLoading
        state = _StateLoading()
        self.assertIsInstance(state.name, str)
        self.assertIn("field", state.name)

    def test_concrete_state_repr(self):
        """Concrete State repr should contain the name."""
        from cereja.display._display import _StateLoading
        state = _StateLoading()
        result = repr(state)
        self.assertIn("field", result)


# if __name__ == "__main__":
#     unittest.main()
