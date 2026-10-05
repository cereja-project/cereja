"""Requirements for fragmented native input and bounded rejected sequences."""

import unittest

from cereja.ui._input import EscapeParser
from cereja.ui.events import EOFEvent, InputErrorEvent, KeyEvent, PasteEvent


class InputParserTest(unittest.TestCase):
    def test_utf8_at_every_split_and_eof_replacement(self):
        raw = 'é中😀'.encode()
        expected = tuple(KeyEvent(c.lower(), c) for c in 'é中😀')
        for split in range(len(raw) + 1):
            parser = EscapeParser()
            self.assertEqual(parser.feed(raw[:split], 0) +
                             parser.feed(raw[split:], .001), expected)
        parser = EscapeParser()
        self.assertEqual(parser.feed(b'\xe2', 0), ())
        self.assertEqual(parser.eof(), (KeyEvent('\ufffd', '\ufffd'), EOFEvent()))
        self.assertEqual(parser.eof(), ())

    def test_escape_boundaries_and_configured_timeout(self):
        for timeout in (.01, .03, .1):
            parser = EscapeParser(escape_timeout=timeout)
            self.assertEqual(parser.feed(b'\x1b', 0), ())
            self.assertEqual(parser.deadline, timeout)
            self.assertEqual(parser.expire(timeout - .00001), ())
            self.assertEqual(parser.expire(timeout), (KeyEvent('escape'),))
            self.assertIsNone(parser.deadline)
        parser = EscapeParser()
        parser.feed(b'\x1b', 0)
        self.assertEqual(parser.feed(b'x', .03),
                         (KeyEvent('escape'), KeyEvent('x', 'x')))

    def test_navigation_modifiers_and_ss3_at_every_split(self):
        cases = [(b'\x1b[A', KeyEvent('up')),
                 (b'\x1b[1;5D', KeyEvent('left', modifiers=frozenset({'ctrl'}))),
                 (b'\x1b[3;3~', KeyEvent('delete', modifiers=frozenset({'alt'}))),
                 (b'\x1bOP', KeyEvent('f1')),
                 (b'\x1b[Z', KeyEvent('tab', modifiers=frozenset({'shift'})))]
        for data, expected in cases:
            for split in range(len(data) + 1):
                parser = EscapeParser()
                self.assertEqual(parser.feed(data[:split], 0) +
                                 parser.feed(data[split:], .001), (expected,))

    def test_alt_unicode_and_control_keys(self):
        parser = EscapeParser()
        self.assertEqual(parser.feed(b'\x1b\xc3', 0), ())
        self.assertEqual(parser.feed(b'\xa9\x03\x7f\r\t', .001),
                         (KeyEvent('é', 'é', frozenset({'alt'})),
                          KeyEvent('c', modifiers=frozenset({'ctrl'})),
                          KeyEvent('backspace'), KeyEvent('enter'), KeyEvent('tab')))

    def test_paste_at_every_split_is_text_not_shortcuts(self):
        text = 'é\n\x03\x1b[A'
        data = b'\x1b[200~' + text.encode() + b'\x1b[201~'
        for split in range(len(data) + 1):
            parser = EscapeParser()
            self.assertEqual(parser.feed(data[:split], 0) +
                             parser.feed(data[split:], .001), (PasteEvent(text),))

    def test_paste_exact_decoded_byte_limit_and_oversize_discard(self):
        parser = EscapeParser(max_paste_bytes=4)
        self.assertEqual(parser.feed(b'\x1b[200~' + 'éé'.encode() + b'\x1b[201~', 0),
                         (PasteEvent('éé'),))
        parser = EscapeParser(max_paste_bytes=4)
        self.assertEqual(parser.feed(b'\x1b[200~\xff\xff\x03' * 1, 0), ())
        self.assertLessEqual(parser.retained_bytes, 10)
        events = parser.feed(b'x' * 10000 + b'\x1b[201~q', 1)
        self.assertIsInstance(events[0], InputErrorEvent)
        self.assertEqual(events[1:], (KeyEvent('q', 'q'),))
        self.assertEqual(len(events), 2)

    def test_unterminated_paste_eof_never_replays_data(self):
        parser = EscapeParser()
        parser.feed(b'\x1b[200~secret\x03', 0)
        result = parser.eof()
        self.assertIsInstance(result[0], InputErrorEvent)
        self.assertEqual(result[1:], (EOFEvent(),))

    def test_oversized_sequence_discard_bounded_and_no_replay(self):
        parser = EscapeParser(max_sequence_bytes=8)
        result = parser.feed(b'\x1b[' + b'1;' * 10000, 0)
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], InputErrorEvent)
        self.assertLessEqual(parser.retained_bytes, 8)
        self.assertEqual(parser.feed(b'Aq', 1), (KeyEvent('q', 'q'),))

    def test_unsupported_control_strings_do_not_replay_keys(self):
        for sequence in (b'\x1b]52;c;payload\x07', b'\x1bPpayload\x07\x03\x1b\\',
                         b'\x1bXpayload\x03\x1b\\'):
            parser = EscapeParser()
            events = parser.feed(sequence + b'q', 0)
            self.assertEqual(len(events), 2)
            self.assertIsInstance(events[0], InputErrorEvent)
            self.assertEqual(events[1], KeyEvent('q', 'q'))

    def test_invalid_sequence_and_incomplete_eof_report(self):
        parser = EscapeParser()
        parser.feed(b'\x1b[1;', 0)
        self.assertEqual(parser.expire(.03), ())
        self.assertIsNone(parser.deadline)
        self.assertIsInstance(parser.eof()[0], InputErrorEvent)
        self.assertIsInstance(EscapeParser().feed(b'\x1b[9999~', 0)[0], InputErrorEvent)
        for malformed in (b'\x1b[1 A', b'\x1b[+1A'):
            self.assertIsInstance(EscapeParser().feed(malformed, 0)[0], InputErrorEvent)

    def test_recognized_delayed_paste_prefix_never_replays_shortcuts(self):
        parser = EscapeParser()
        self.assertEqual(parser.feed(b'\x1b[', 0), ())
        self.assertEqual(parser.feed(b'200~\x03\x1b[201~', 1), (PasteEvent('\x03'),))

    def test_validates_configuration_and_closed_parser(self):
        for value in (.009, .101, float('nan'), float('inf'), True):
            with self.assertRaises((TypeError, ValueError)):
                EscapeParser(escape_timeout=value)
        parser = EscapeParser()
        parser.eof()
        with self.assertRaises(RuntimeError):
            parser.feed(b'a', 0)

    def test_key_event_owns_immutable_modifiers(self):
        modifiers = {'ctrl'}
        event = KeyEvent('c', modifiers=modifiers)
        modifiers.add('shift')
        self.assertEqual(event.modifiers, frozenset({'ctrl'}))
        with self.assertRaises(ValueError):
            KeyEvent('c', repeat=0)


if __name__ == '__main__':
    unittest.main()
