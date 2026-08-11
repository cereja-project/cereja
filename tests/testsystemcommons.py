"""
Tests for cereja.system.commons module.

Covers memory_of_this, memory_usage, and run_on_terminal functions.
"""
import importlib
import io
import logging
import subprocess
import sys
import unittest
from contextlib import redirect_stdout

import cereja.system.commons as system_commons
from cereja.system.commons import (
    memory_of_this,
    memory_usage,
    run_on_terminal,
    thread_monitor,
)


class TestMemoryOfThis(unittest.TestCase):
    """Tests for memory_of_this function."""

    def test_returns_int(self):
        """memory_of_this should return an integer (bytes)."""
        result = memory_of_this("hello")
        self.assertIsInstance(result, int)

    def test_positive_size(self):
        """memory_of_this should return a positive value."""
        result = memory_of_this([1, 2, 3])
        self.assertGreater(result, 0)

    def test_larger_objects_use_more_memory(self):
        """A larger list should generally use more memory than a smaller one."""
        small = memory_of_this([1])
        large = memory_of_this(list(range(1000)))
        self.assertGreater(large, small)

    def test_different_types(self):
        """memory_of_this should work with various types."""
        self.assertIsInstance(memory_of_this(42), int)
        self.assertIsInstance(memory_of_this(3.14), int)
        self.assertIsInstance(memory_of_this({"key": "value"}), int)
        self.assertIsInstance(memory_of_this(None), int)


class TestMemoryUsage(unittest.TestCase):
    """Tests for memory_usage function."""

    def test_returns_list(self):
        """memory_usage should return a list."""
        result = memory_usage()
        self.assertIsInstance(result, list)

    def test_default_limit(self):
        """memory_usage should return at most n_most items."""
        result = memory_usage(n_most=5)
        self.assertLessEqual(len(result), 5)

    def test_items_are_tuples(self):
        """Each item should be a tuple of (name, size)."""
        result = memory_usage(n_most=3)
        for item in result:
            self.assertIsInstance(item, tuple)
            self.assertEqual(len(item), 2)

    def test_sorted_descending(self):
        """Results should be sorted by size in descending order."""
        result = memory_usage(n_most=10)
        sizes = [item[1] for item in result]
        self.assertEqual(sizes, sorted(sizes, reverse=True))


class TestRunOnTerminal(unittest.TestCase):
    """Tests for run_on_terminal function."""

    def test_simple_command(self):
        """run_on_terminal should execute a simple command."""
        result = run_on_terminal("echo hello")
        self.assertIsNotNone(result)
        self.assertIn(b"hello", result)

    def test_python_version(self):
        """run_on_terminal should be able to run python --version."""
        result = run_on_terminal(f"{sys.executable} --version")
        self.assertIsNotNone(result)
        self.assertIn(b"Python", result)

    def test_failing_command_raises(self):
        """run_on_terminal should raise Exception for failing commands."""
        with self.assertRaises(Exception):
            run_on_terminal("false")

    def test_failing_command_can_return_stderr(self):
        """Non-raising execution should preserve captured stderr."""
        command = (
            f'"{sys.executable}" -c '
            '"import sys; sys.stderr.write(\'failed\'); sys.exit(2)"'
        )

        result = run_on_terminal(command, raise_errors=False)

        self.assertEqual(result, b"failed")

    def test_failing_command_without_output_returns_none(self):
        """Non-raising execution should honor get_output=False on failure."""
        command = f'"{sys.executable}" -c "import sys; sys.exit(2)"'

        result = run_on_terminal(
            command,
            get_output=False,
            raise_errors=False,
        )

        self.assertIsNone(result)

    def test_returns_bytes(self):
        """run_on_terminal should return bytes output."""
        result = run_on_terminal("echo test")
        self.assertIsInstance(result, bytes)


class TestModuleDiagnostics(unittest.TestCase):
    """Tests for logging ownership and thread diagnostics."""

    def test_reloading_module_does_not_configure_root_logger(self):
        """Library import must not install handlers on the root logger."""
        root_logger = logging.getLogger()
        previous_handlers = root_logger.handlers[:]
        previous_level = root_logger.level
        root_logger.handlers.clear()
        try:
            importlib.reload(system_commons)

            self.assertEqual(root_logger.handlers, [])
            self.assertEqual(root_logger.level, previous_level)
        finally:
            root_logger.handlers[:] = previous_handlers
            root_logger.setLevel(previous_level)

    def test_thread_monitor_without_filter_prints_actual_thread_name(self):
        """Unfiltered diagnostics must identify threads instead of printing None."""
        output = io.StringIO()

        with redirect_stdout(output):
            thread_monitor()

        rendered = output.getvalue()
        self.assertIn("Stack Trace da Thread: MainThread", rendered)
        self.assertNotIn("Stack Trace da Thread: None", rendered)


if __name__ == "__main__":
    unittest.main()
