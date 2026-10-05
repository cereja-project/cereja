import io
from contextlib import ExitStack
import os
from dataclasses import FrozenInstanceError
import tempfile
import unittest
from unittest.mock import patch

from cereja.ui._capabilities import (
    Capabilities, CapabilityOptions, StreamBackend, detect_capabilities,
)
from cereja.ui.terminal import TerminalSession


class FakeStream(io.StringIO):
    def __init__(self, interactive=True, encoding="utf-8"):
        super().__init__()
        self.interactive = interactive
        self._encoding = encoding

    @property
    def encoding(self):
        return self._encoding

    def isatty(self):
        return self.interactive


class CapabilityTests(unittest.TestCase):
    def detect(self, *, input_interactive=True, output_interactive=True,
               options=None, env=None, acquisition=True, encoding="utf-8",
               platform="linux"):
        return detect_capabilities(
            FakeStream(input_interactive), FakeStream(output_interactive, encoding),
            options, {"TERM": "xterm-256color"} if env is None else env,
            supports_acquisition=acquisition, platform=platform)

    def test_input_and_output_interactivity_are_independent(self):
        options = CapabilityOptions(color=24, cursor=True, alternate_screen=True,
                                    paste=True)
        for input_tty in (False, True):
            for output_tty in (False, True):
                with self.subTest(input=input_tty, output=output_tty):
                    caps = self.detect(input_interactive=input_tty,
                                       output_interactive=output_tty, options=options)
                    self.assertEqual(caps.input_interactive, input_tty)
                    self.assertEqual(caps.output_interactive, output_tty)
                    self.assertEqual(caps.plain, not (input_tty and output_tty))
                    self.assertEqual(caps.color_depth, 24 if not caps.plain else 0)
                    self.assertEqual(caps.cursor, not caps.plain)
                    self.assertEqual(caps.alternate_screen, not caps.plain)
                    self.assertEqual(caps.paste, not caps.plain)

    def test_unknown_and_dumb_term_require_explicit_cursor_and_acquisition(self):
        for term in ("", "dumb", "mystery-256color", "xtermish"):
            with self.subTest(term=term):
                self.assertTrue(self.detect(env={"TERM": term}).plain)
                color_only = self.detect(env={"TERM": term},
                                         options=CapabilityOptions(color=24))
                self.assertTrue(color_only.plain)
                self.assertEqual(color_only.color_depth, 0)
                asserted = self.detect(env={"TERM": term}, options=CapabilityOptions(
                    color=16, cursor=True, alternate_screen=True, paste=True))
                self.assertFalse(asserted.plain)
                self.assertEqual(asserted.color_depth, 16)
                self.assertTrue(asserted.alternate_screen)
                unavailable = self.detect(env={"TERM": term}, acquisition=False,
                                          options=CapabilityOptions(cursor=True))
                self.assertTrue(unavailable.plain)
                self.assertFalse(unavailable.cursor)

    def test_no_color_nonempty_and_explicit_precedence(self):
        for no_color, expected in (("", 256), ("1", 0), ("0", 0)):
            caps = self.detect(env={"TERM": "xterm-256color", "NO_COLOR": no_color})
            self.assertEqual(caps.color_depth, expected)
            self.assertFalse(caps.plain)
            self.assertTrue(caps.cursor)
        for color in (0, 16, 256, 24):
            caps = self.detect(env={"TERM": "xterm", "NO_COLOR": "1"},
                               options=CapabilityOptions(color=color))
            self.assertEqual(caps.color_depth, color)
            self.assertEqual(caps.sources["color_depth"], "option")

    def test_other_environment_variables_are_hints_not_overrides(self):
        caps = self.detect(env={"TERM": "unknown", "COLORTERM": "truecolor",
                                "FORCE_COLOR": "1", "CLICOLOR_FORCE": "1"})
        self.assertTrue(caps.plain)
        self.assertEqual(caps.color_depth, 0)
        known = self.detect(env={"TERM": "xterm", "COLORTERM": "truecolor"})
        self.assertEqual(known.color_depth, 24)
        self.assertFalse(known.paste)

    def test_windows_environment_does_not_assert_console_vt(self):
        self.assertTrue(self.detect(platform="win32").plain)
        caps = self.detect(platform="win32", options=CapabilityOptions(cursor=True))
        self.assertFalse(caps.plain)

    def test_palette_is_independent_from_cursor_and_monochrome_hints(self):
        for term in ("linux-m", "xterm-mono", "vt100", "vt102", "vt220"):
            for colorterm in ("", "truecolor"):
                with self.subTest(term=term, colorterm=colorterm):
                    env = {"TERM": term, "COLORTERM": colorterm}
                    caps = self.detect(env=env)
                    self.assertTrue(caps.cursor)
                    self.assertFalse(caps.plain)
                    self.assertEqual(caps.color_depth, 0)
                    env["NO_COLOR"] = "1"
                    asserted = self.detect(env=env, options=CapabilityOptions(color=16))
                    self.assertTrue(asserted.cursor)
                    self.assertEqual(asserted.color_depth, 16)
                    self.assertEqual(asserted.sources["color_depth"], "option")

    def test_alternate_screen_is_independent_from_cursor(self):
        for term in ("vt100", "vt102", "vt220", "linux", "linux-m", "ansi"):
            with self.subTest(term=term):
                caps = self.detect(env={"TERM": term})
                self.assertTrue(caps.cursor)
                self.assertFalse(caps.alternate_screen)
                asserted = self.detect(env={"TERM": term}, options=CapabilityOptions(
                    alternate_screen=True))
                self.assertTrue(asserted.alternate_screen)
                self.assertEqual(asserted.sources["alternate_screen"], "option")
        for term in ("xterm", "xterm-256color", "xterm-mono", "screen", "tmux", "rxvt"):
            with self.subTest(term=term):
                self.assertTrue(self.detect(env={"TERM": term}).alternate_screen)
                self.assertFalse(self.detect(env={"TERM": term}, options=CapabilityOptions(
                    alternate_screen=False)).alternate_screen)

    def test_unicode_motion_and_navigation_are_independent(self):
        ascii_caps = self.detect(options=CapabilityOptions(unicode=False))
        self.assertFalse(ascii_caps.unicode)
        self.assertTrue(ascii_caps.cursor)
        self.assertFalse(ascii_caps.reduced_motion)
        motion_caps = self.detect(options=CapabilityOptions(reduced_motion=True))
        self.assertTrue(motion_caps.unicode)
        self.assertTrue(motion_caps.reduced_motion)
        self.assertTrue(motion_caps.cursor)
        plain = self.detect(output_interactive=False,
                            options=CapabilityOptions(unicode=True, reduced_motion=True))
        self.assertTrue(plain.unicode)
        self.assertTrue(plain.reduced_motion)
        for encoding in (None, "ascii", "latin-1", "missing-codec"):
            self.assertFalse(self.detect(encoding=encoding).unicode)
        self.assertTrue(self.detect(encoding="UTF8").unicode)

    def test_unusable_stream_is_safe_and_detection_does_not_write(self):
        class Unknown:
            def isatty(self):
                raise OSError("closed")

        caps = detect_capabilities(Unknown(), Unknown(), environ={})
        self.assertTrue(caps.plain)
        self.assertFalse(caps.input_interactive)
        self.assertFalse(caps.output_interactive)
        self.assertFalse(caps.unicode)
        stream = FakeStream()
        detect_capabilities(stream, stream, environ={"TERM": "xterm"})
        self.assertEqual(stream.getvalue(), "")

    def test_options_and_capabilities_validate_and_copy_sources(self):
        for color in (True, "truecolor", -1, 8, 32):
            with self.subTest(color=color), self.assertRaises(ValueError):
                CapabilityOptions(color=color)
        for name in ("unicode", "cursor", "alternate_screen", "paste",
                     "reduced_motion"):
            with self.subTest(name=name), self.assertRaises(TypeError):
                CapabilityOptions(**{name: 1})
        with self.assertRaises(TypeError):
            self.detect(options={"cursor": True})
        sources = {"cursor": "option"}
        caps = Capabilities(sources=sources)
        sources["cursor"] = "changed"
        self.assertEqual(caps.sources["cursor"], "option")
        with self.assertRaises(TypeError):
            caps.sources["cursor"] = "changed"
        with self.assertRaises(FrozenInstanceError):
            caps.cursor = True
        for values in ({"plain": False}, {"cursor": True}, {"color_depth": 16},
                       {"paste": True}, {"alternate_screen": True},
                       {"input_interactive": True, "cursor": True, "plain": False}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                Capabilities(**values)
        self.assertEqual(set(self.detect().sources), {
            "input_interactive", "output_interactive", "color_depth", "unicode",
            "cursor", "alternate_screen", "paste", "reduced_motion", "plain"})


class StreamBackendTests(unittest.TestCase):
    def test_plain_transport_dimensions_and_object_identity(self):
        stream = FakeStream()
        first = StreamBackend(stream, stream, environ={"TERM": "xterm"},
                              options=CapabilityOptions(cursor=True, color=24))
        second = StreamBackend(stream, stream)
        self.assertEqual(first.identity, second.identity)
        self.assertNotEqual(first.identity, StreamBackend(FakeStream(), FakeStream()).identity)
        self.assertTrue(first.capabilities.plain)
        self.assertFalse(first.capabilities.cursor)
        self.assertEqual(first.dimensions(), (80, 24))
        self.assertEqual(first.capture(), {})
        self.assertEqual(first.write("plain"), 5)
        first.flush()
        self.assertEqual(stream.getvalue(), "plain")
        first.restore("cursor", {})
        first.invalidate()
        self.assertTrue(first.invalidated)
        with self.assertRaises(RuntimeError):
            first.acquire("cursor", {})

    def test_descriptor_aliases_share_identity(self):
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stream:
            with os.fdopen(os.dup(stream.fileno()), "w", encoding="utf-8") as alias:
                first = StreamBackend(stream, stream)
                second = StreamBackend(stream, alias)
                self.assertEqual(first.identity, second.identity)
                with patch("cereja.ui._capabilities.os.get_terminal_size",
                           return_value=os.terminal_size((0, 0))):
                    self.assertEqual(first.dimensions(), (0, 0))

    def test_independent_pipes_have_distinct_owners_and_can_open_concurrently(self):
        with ExitStack() as stack:
            backends = []
            for _ in range(2):
                read_fd, write_fd = os.pipe()
                input_stream = stack.enter_context(os.fdopen(read_fd, "r", encoding="utf-8"))
                output_stream = stack.enter_context(os.fdopen(write_fd, "w", encoding="utf-8"))
                backends.append(StreamBackend(input_stream, output_stream))
            self.assertNotEqual(backends[0].identity, backends[1].identity)
            with TerminalSession(backends[0]) as first, TerminalSession(backends[1]) as second:
                first.write_text("first")
                second.write_text("second")

    def test_missing_descriptor_identity_uses_fd_except_windows_console(self):
        class Descriptor(FakeStream):
            def __init__(self, fd):
                super().__init__(interactive=False)
                self.fd = fd

            def fileno(self):
                return self.fd

        with patch("cereja.ui._capabilities.os.fstat", return_value=os.stat_result((0,) * 10)), \
                patch("cereja.ui._capabilities.os.ttyname", side_effect=OSError, create=True), \
                patch("cereja.ui._capabilities.sys.platform", "win32"), \
                patch("cereja.ui._capabilities.os.isatty", return_value=False):
            first = StreamBackend(FakeStream(False), Descriptor(100))
            alias = StreamBackend(FakeStream(False), Descriptor(100))
            other = StreamBackend(FakeStream(False), Descriptor(101))
            self.assertEqual(first.identity, alias.identity)
            self.assertNotEqual(first.identity, other.identity)
            with patch("cereja.ui._capabilities.os.isatty", return_value=True):
                console = StreamBackend(FakeStream(False), Descriptor(100))
                console_alias = StreamBackend(FakeStream(False), Descriptor(101))
                self.assertEqual(console.identity, console_alias.identity)


if __name__ == "__main__":
    unittest.main()
