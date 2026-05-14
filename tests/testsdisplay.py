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

    def test_console_is_singleton(self):
        """Console should be a singleton instance."""
        from cereja.display._display import _ConsoleBase
        c1 = _ConsoleBase()
        c2 = _ConsoleBase()
        self.assertIs(c1, c2)

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


if __name__ == "__main__":
    unittest.main()
