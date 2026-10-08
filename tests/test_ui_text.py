"""Independent official boundary vectors and the frozen terminal text policy."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from cereja.ui.text import (
    TextPolicy, clip_text, grapheme_spans, graphemes, normalize_text, text_metrics,
)


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'tools' / 'unicode' / '17.0.0'


def records(name):
    for line in (DATA / name).read_text(encoding='utf-8').splitlines():
        content = line.split('#', 1)[0].strip()
        if content:
            yield [field.strip() for field in content.split(';')]


def sequences(name, types):
    for fields in records(name):
        if fields[1] not in types:
            continue
        codes = fields[0]
        if '..' in codes:
            low, high = (int(code, 16) for code in codes.split('..'))
            yield from (chr(code) for code in range(low, high + 1))
        else:
            yield ''.join(chr(int(code, 16)) for code in codes.split())


class OfficialGraphemeTest(unittest.TestCase):
    def test_all_unicode_17_default_extended_boundary_vectors(self):
        count = 0
        for line_number, line in enumerate(
                (DATA / 'GraphemeBreakTest.txt').read_text(encoding='utf-8').splitlines(), 1):
            content = line.split('#', 1)[0].strip()
            if not content:
                continue
            text = ''
            boundaries = []
            for token in content.split():
                if token == '\u00f7':
                    boundaries.append(len(text))
                elif token != '\u00d7':
                    text += chr(int(token, 16))
            expected = list(zip(boundaries, boundaries[1:]))
            with self.subTest(line=line_number):
                self.assertEqual(list(grapheme_spans(text)), expected)
                self.assertEqual(list(graphemes(text)), [text[a:b] for a, b in expected])
            count += 1
        self.assertEqual(count, 766)

    def test_empty_and_context_sensitive_boundaries(self):
        self.assertEqual(list(graphemes('')), [])
        for text, expected in (
            ('\r\n', ['\r\n']),
            ('\u0915\u094d\u0937', ['\u0915\u094d\u0937']),
            ('\U0001f1e6\U0001f1e7\U0001f1e8', ['\U0001f1e6\U0001f1e7', '\U0001f1e8']),
            ('\U0001f469\u0308\u200d\U0001f4bb', ['\U0001f469\u0308\u200d\U0001f4bb']),
            ('\U0001f469\u200d\u0308\U0001f4bb', ['\U0001f469\u200d\u0308', '\U0001f4bb']),
            ('\u1100\u1161\u11a8', ['\u1100\u1161\u11a8']),
        ):
            with self.subTest(text=ascii(text)):
                self.assertEqual(list(graphemes(text)), expected)


class FrozenWidthPolicyTest(unittest.TestCase):
    def assert_unit(self, text, display, width, policy=TextPolicy()):
        measured = text_metrics(text, policy)
        self.assertEqual([(unit.text, unit.width) for unit in measured.units], [(display, width)])

    def test_named_policy_fixtures(self):
        for text, display, width in (
            ('A', 'A', 1), ('\u00e9', '\u00e9', 1), ('e\u0301', 'e\u0301', 1),
            ('\u754c', '\u754c', 2), ('\U0001f600', '\U0001f600', 2),
            ('\u2764\ufe0f', '\u2764\ufe0f', 2), ('\u2764\ufe0e', '\u2764\ufe0e', 1),
            ('\u2764', '\u2764', 1), ('\u00a9', '\u00a9', 1), ('1', '1', 1),
            ('1\ufe0f\u20e3', '1\ufe0f\u20e3', 2),
            ('\U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466',
             '\U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466', 2),
            ('\U0001f1e7\U0001f1f7', '\U0001f1e7\U0001f1f7', 2),
            ('\u0301\u0308', '\u25cc\u0301\u0308', 1),
            ('\u093e', '\u25cc\u093e', 1), ('\u20dd', '\u25cc\u20dd', 1),
            ('\ufe0f', '?', 1), ('\ufe0e', '?', 1), ('\U000e0100', '?', 1),
            ('a\ufe0e', '?', 1), ('\u2764\ufe0f\u0301', '?', 1),
            # Basic_Emoji explicitly includes bare modifiers; exact RGI wins.
            ('\U0001f3fb', '\U0001f3fb', 2), ('a\U0001f3fb', '?', 1),
            ('\U0001f3fb\U0001f3fc', '?', 1), ('\U0001f1e6', '?', 1),
            ('\U0001f1ff\U0001f1ff', '?', 1), ('a\u200d', '?', 1), ('a\u200c', '?', 1),
            ('\u0378\u0301', '?', 1), ('\U0010ffff', '?', 1),
            ('\ud800', '\ufffd', 1), ('\udfff', '\ufffd', 1),
            ('\U0001f6d8', '\U0001f6d8', 2), ('\U0001e6e3', '\u25cc\U0001e6e3', 1),
        ):
            with self.subTest(text=ascii(text)):
                self.assert_unit(text, display, width)

    def test_ambiguous_and_text_variation_use_base_text_width(self):
        self.assert_unit('\u00b7', '\u00b7', 1)
        self.assert_unit('\u00b7', '\u00b7', 2, TextPolicy(ambiguous_width=2))
        self.assert_unit('\u263a\ufe0e', '\u263a\ufe0e', 1)
        self.assert_unit('\u263a\ufe0e', '\u263a\ufe0e', 1, TextPolicy(ambiguous_width=2))
        self.assert_unit('\u231a\ufe0e', '\u231a\ufe0e', 2)
        self.assert_unit('\u0301', '\u25cc\u0301', 1, TextPolicy(ambiguous_width=2))
        self.assert_unit('\u2764\ufe0f', '\u2764\ufe0f', 2, TextPolicy(ambiguous_width=2))

    def test_every_official_rgi_sequence_is_one_two_cell_unit(self):
        types = {'Basic_Emoji', 'Emoji_Keycap_Sequence', 'RGI_Emoji_Flag_Sequence',
                 'RGI_Emoji_Tag_Sequence', 'RGI_Emoji_Modifier_Sequence', 'RGI_Emoji_ZWJ_Sequence'}
        count = 0
        for name in ('emoji-sequences.txt', 'emoji-zwj-sequences.txt'):
            for text in sequences(name, types):
                with self.subTest(text=ascii(text)):
                    self.assertEqual(list(graphemes(text)), [text])
                    self.assert_unit(text, text, 2)
                count += 1
        self.assertEqual(count, 3953)

    def test_every_official_text_variation_uses_pinned_eaw(self):
        eaw = {}
        for codes, prop in records('EastAsianWidth.txt'):
            bounds = codes.split('..')
            eaw.update((cp, prop) for cp in range(int(bounds[0], 16), int(bounds[-1], 16) + 1))
        count = 0
        for text in sequences('emoji-variation-sequences.txt', {'text style'}):
            for ambiguous in (1, 2):
                prop = eaw.get(ord(text[0]), 'N')
                expected = 2 if prop in ('W', 'F') else ambiguous if prop == 'A' else 1
                self.assert_unit(text, text, expected, TextPolicy(ambiguous_width=ambiguous))
            count += 1
        self.assertEqual(count, 371)

    def test_ascii_replaces_whole_clusters_after_sanitizing(self):
        policy = TextPolicy(ascii_only=True)
        for text in ('e\u0301', '\u754c', '\u0301', '\u2764\ufe0f', '\ud800',
                     '\U0001f469\u200d\U0001f4bb'):
            with self.subTest(text=ascii(text)):
                self.assert_unit(text, '?', 1, policy)
        measured = text_metrics('Az09!?\x1b', policy)
        self.assertEqual(''.join(unit.text for unit in measured.units), 'Az09!?\\x1b')


class TextSafetyAndLayoutTest(unittest.TestCase):
    def test_all_terminal_controls_are_visible_except_layout_tokens(self):
        for code in (*range(32), *range(127, 160)):
            text = chr(code)
            expected = text if text in '\t\n' else f'\\x{code:02x}'
            self.assertEqual(normalize_text(text), expected)
        attack = '\x1b]52;c;payload\x07\x9b31m\r\x1b[2J'
        measured = text_metrics(attack)
        rendered = ''.join(unit.text for unit in measured.units)
        self.assertEqual(rendered, '\\x1b]52;c;payload\\x07\\x9b31m\\x0d\\x1b[2J')
        self.assertEqual(measured.line_widths(), (len(rendered),))
        self.assertFalse(any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in rendered))

    def test_bidi_controls_are_visible_in_source_and_path_mode(self):
        codes = (0x061c, 0x200e, 0x200f, 0x202a, 0x202b, 0x202c, 0x202d, 0x202e,
                 0x2066, 0x2067, 0x2068, 0x2069)
        text = ''.join(chr(code) for code in codes)
        self.assertEqual(normalize_text(text), ''.join(f'\\u{code:04x}' for code in codes))
        self.assertEqual(normalize_text(text, source=False), text)
        self.assertEqual(normalize_text(normalize_text(text)), normalize_text(text))

    def test_tabs_and_newlines_are_layout_tokens_and_cursor_positions(self):
        measured = text_metrics('A\t\u754c\ne\u0301\t!')
        self.assertEqual([unit.kind for unit in measured.units],
                         ['grapheme', 'tab', 'grapheme', 'newline', 'grapheme', 'tab', 'grapheme'])
        self.assertEqual(measured.line_widths(), (6, 5))
        self.assertEqual(measured.line_widths(start_column=2, tab_size=8), (10, 9))
        self.assertEqual(measured.cell_position(3), (6, 0))
        self.assertEqual(measured.cell_position(4), (0, 1))
        self.assertEqual(measured.cell_position(6), (1, 1))
        with self.assertRaises(ValueError):
            measured.cell_position(5)
        self.assertEqual(text_metrics('').line_widths(), (0,))

    def test_cursor_motion_uses_grapheme_boundaries_even_on_fallback(self):
        measured = text_metrics('e\u0301\u2764\ufe0fX')
        self.assertEqual(measured.boundaries, (0, 2, 4, 5))
        self.assertEqual(measured.next_boundary(0), 2)
        self.assertEqual(measured.next_boundary(1), 2)
        self.assertEqual(measured.previous_boundary(4), 2)
        self.assertEqual(measured.previous_boundary(3), 2)
        self.assertEqual(measured.previous_boundary(0), 0)
        self.assertEqual(measured.next_boundary(5), 5)
        self.assertEqual(text_metrics('a\u200d').boundaries, (0, 2))
        self.assertEqual(text_metrics('a\u200d').cell_position(2), (1, 0))

    def test_clipping_never_splits_graphemes_or_wide_cells(self):
        for text, cells, left, expected in (
            ('A\u754cB', 2, 0, 'A '), ('A\u754cB', 3, 0, 'A\u754c'),
            ('A\u754cB', 2, 2, ' B'), ('\u754c', 1, 0, ' '),
            ('\u754c', 1, 1, ' '), ('e\u0301X', 1, 0, 'e\u0301'),
            ('\u2764\ufe0fX', 1, 0, ' '), ('a\u200dX', 1, 0, '?'),
            ('A\tX', 2, 2, '  '), ('A\tX', 4, 1, '   X'),
            ('abc', 0, 0, ''), ('abc', 3, 9, ''), ('abc', 9, 0, 'abc'),
        ):
            with self.subTest(text=ascii(text), cells=cells, left=left):
                self.assertEqual(clip_text(text, cells, left=left), expected)
        with self.assertRaises(ValueError):
            clip_text('a\nb', 10)

    def test_invalid_arguments_fail_explicitly(self):
        for kwargs in ({'ambiguous_width': 0}, {'ambiguous_width': True},
                       {'ascii_only': 1}, {'source': 'yes'}):
            with self.assertRaises((ValueError, TypeError)):
                TextPolicy(**kwargs)
        for value in (None, b'text', 42):
            with self.assertRaises(TypeError):
                text_metrics(value)
            with self.assertRaises(TypeError):
                list(graphemes(value))
        for value in (-1, 6, True, 1.5):
            with self.assertRaises((ValueError, TypeError)):
                text_metrics('abc').next_boundary(value)
        for kwargs in ({'tab_size': 0}, {'tab_size': True}, {'start_column': -1}):
            with self.assertRaises((ValueError, TypeError)):
                text_metrics('a').line_widths(**kwargs)
        for value in (-1, True, 1.5):
            with self.assertRaises((ValueError, TypeError)):
                clip_text('a', value)

    def test_cache_is_entry_and_input_bounded_and_policy_sensitive(self):
        from cereja.ui.text import _cached_metrics
        _cached_metrics.cache_clear()
        first = text_metrics('\u00b7')
        self.assertIs(text_metrics('\u00b7'), first)
        self.assertNotEqual(text_metrics('\u00b7', TextPolicy(ambiguous_width=2)), first)
        for index in range(300):
            text_metrics(str(index))
        self.assertLessEqual(_cached_metrics.cache_info().currsize, 128)
        before = _cached_metrics.cache_info()
        text_metrics('a' * 1025)
        self.assertEqual(_cached_metrics.cache_info(), before)
        with self.assertRaises(AttributeError):
            first.units = ()


class UnicodeProvenanceTest(unittest.TestCase):
    def test_raw_hashes_and_offline_regeneration(self):
        manifest = json.loads((DATA / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['unicode_version'], '17.0.0')
        self.assertEqual(manifest['emoji_version'], '17.0')
        self.assertEqual(manifest['uax29_revision'], 47)
        for name, source in manifest['sources'].items():
            self.assertEqual(hashlib.sha256((DATA / name).read_bytes()).hexdigest(), source['sha256'], name)
            self.assertTrue(source['url'].startswith('https://www.unicode.org/'))
        result = subprocess.run([sys.executable, '-B', '-S', 'tools/generate_ui_unicode.py', '--check'],
                                cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((ROOT / 'cereja/ui/UNICODE-LICENSE.txt').read_bytes(), (DATA / 'LICENSE.txt').read_bytes())

    def test_regeneration_rejects_changed_source_bytes(self):
        from tools import generate_ui_unicode as generator
        with tempfile.TemporaryDirectory(prefix='cereja-unicode-hash-') as directory:
            fixture = Path(directory)
            manifest = json.loads((DATA / 'manifest.json').read_text(encoding='utf-8'))
            manifest['sources'] = {'LICENSE.txt': manifest['sources']['LICENSE.txt']}
            (fixture / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            (fixture / 'LICENSE.txt').write_bytes(b'changed source')
            with mock.patch.object(generator, 'DATA', fixture):
                with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch: LICENSE.txt'):
                    generator.load_sources()


if __name__ == '__main__':
    unittest.main()
