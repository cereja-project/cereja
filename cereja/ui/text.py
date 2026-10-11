"""Pinned grapheme boundaries and safe, logical-order terminal cell metrics.

Import this module explicitly. Segmentation accepts raw text for conformance;
text_metrics normalizes controls before measuring. Offsets refer to its returned
normalized text, which is the editing model's canonical input, not a source map.
"""

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from functools import lru_cache

from . import _unicode17 as _data


UNICODE_VERSION = _data.UNICODE_VERSION
__all__ = ['UNICODE_VERSION', 'TextPolicy', 'TextUnit', 'TextMetrics',
           'grapheme_spans', 'graphemes', 'normalize_text', 'text_metrics', 'clip_text']


def _require_text(text):
    if not isinstance(text, str):
        raise TypeError('text must be str')


def _lookup(table, code, default=None):
    index = bisect_right(table, (code, 0x110000)) - 1
    if index >= 0 and code <= table[index][1]:
        return table[index][2]
    return default


def _contains(table, code):
    index = bisect_right(table, (code, 0x110000)) - 1
    return index >= 0 and code <= table[index][1]


def grapheme_spans(text):
    """Yield raw (start, end) code-point offsets using default extended UAX #29.

    No normalization or tailoring. A forward state machine retains GB9c, GB11
    and RI context without rescanning long Extend/Linker runs.
    """
    _require_text(text)
    start = 0
    previous = None
    ri_run = 0
    indic = 0  # 1: consonant + extenders; 2: at least one linker since consonant
    ep_extend = False
    zwj_after_ep = False
    for index, char in enumerate(text):
        code = ord(char)
        current = _lookup(_data.GCB, code, 'Other')
        incb = _lookup(_data.INCB, code)
        ep = _contains(_data.EXTENDED_PICTOGRAPHIC, code)
        if index:
            if previous == 'CR' and current == 'LF':  # GB3
                boundary = False
            elif previous in ('Control', 'CR', 'LF') or current in ('Control', 'CR', 'LF'):  # GB4/5
                boundary = True
            elif previous == 'L' and current in ('L', 'V', 'LV', 'LVT'):  # GB6
                boundary = False
            elif previous in ('LV', 'V') and current in ('V', 'T'):  # GB7
                boundary = False
            elif previous in ('LVT', 'T') and current == 'T':  # GB8
                boundary = False
            elif current in ('Extend', 'ZWJ', 'SpacingMark') or previous == 'Prepend':  # GB9/9a/9b
                boundary = False
            elif incb == 'Consonant' and indic == 2:  # GB9c
                boundary = False
            elif ep and previous == 'ZWJ' and zwj_after_ep:  # GB11
                boundary = False
            elif previous == current == 'Regional_Indicator' and ri_run % 2:  # GB12/13
                boundary = False
            else:  # GB999
                boundary = True
            if boundary:
                yield start, index
                start = index
        ri_run = ri_run + 1 if current == 'Regional_Indicator' else 0
        if incb == 'Consonant':
            indic = 1
        elif incb == 'Linker' and indic:
            indic = 2
        elif incb not in ('Extend', 'Linker'):
            indic = 0
        zwj_after_ep = current == 'ZWJ' and ep_extend
        ep_extend = ep or (current == 'Extend' and ep_extend)
        previous = current
    if text:
        yield start, len(text)


def graphemes(text):
    """Yield raw whole graphemes; use text_metrics before terminal rendering."""
    for start, end in grapheme_spans(text):
        yield text[start:end]


@dataclass(frozen=True, slots=True)
class TextPolicy:
    """Cell policy; source=True visibly escapes source/path bidi controls."""

    ambiguous_width: int = 1
    ascii_only: bool = False
    source: bool = True

    def __post_init__(self):
        if type(self.ambiguous_width) is not int or self.ambiguous_width not in (1, 2):
            raise ValueError('ambiguous_width must be 1 or 2')
        if type(self.ascii_only) is not bool or type(self.source) is not bool:
            raise TypeError('ascii_only and source must be bool')


_DEFAULT_POLICY = TextPolicy()


def normalize_text(text, *, source=True):
    """Escape ESC/C0/C1/DEL and source bidi controls, replace lone surrogates.

    LF and TAB remain layout tokens. CR is visible, including the CR in CRLF.
    This is security normalization, not NFC/NFD or a bidirectional text engine.
    """
    _require_text(text)
    if type(source) is not bool:
        raise TypeError('source must be bool')
    output = []
    for char in text:
        code = ord(char)
        if char in ('\n', '\t'):
            output.append(char)
        elif code < 32 or 127 <= code <= 159:
            output.append(f'\\x{code:02x}')
        elif 0xD800 <= code <= 0xDFFF:
            output.append('\ufffd')
        elif source and _contains(_data.BIDI_CONTROL, code):
            output.append(f'\\u{code:04x}')
        else:
            output.append(char)
    return ''.join(output)


def _scalar_width(code, policy):
    prop = _lookup(_data.EAW, code, 'N')
    return 2 if prop in ('W', 'F') else policy.ambiguous_width if prop == 'A' else 1


def _display_grapheme(text, policy):
    if policy.ascii_only:
        return (text, 1) if all(32 <= ord(char) <= 126 for char in text) else ('?', 1)
    if text in _data.RGI_EMOJI:
        return text, 2
    if text in _data.TEXT_VARIATION:
        return text, _scalar_width(ord(text[0]), policy)
    codes = [ord(char) for char in text]
    if any(code in (0x200C, 0x200D) or 0x1F1E6 <= code <= 0x1F1FF
           or _contains(_data.UNASSIGNED, code)
           or _contains(_data.VARIATION_SELECTOR, code)
           or _contains(_data.EMOJI_MODIFIER, code) for code in codes):
        return '?', 1
    widths = [_scalar_width(code, policy) for code in codes if not _contains(_data.MARK, code)]
    if not widths:
        return '\u25cc' + text, 1
    return text, max(widths)


@dataclass(frozen=True, slots=True)
class TextUnit:
    """One normalized grapheme span and its safe display, or an LF/TAB token.

    Grapheme width is 1/2. Layout token width is 0 until column-aware layout.
    start/end always refer to TextMetrics.text, including fallback clusters.
    """

    start: int
    end: int
    text: str
    width: int
    kind: str = 'grapheme'


def _nonnegative_int(value, name):
    if type(value) is not int:
        raise TypeError(f'{name} must be int')
    if value < 0:
        raise ValueError(f'{name} must be nonnegative')


def _layout_options(start_column, tab_size):
    _nonnegative_int(start_column, 'start_column')
    _nonnegative_int(tab_size, 'tab_size')
    if not tab_size:
        raise ValueError('tab_size must be positive')


def _unit_cells(unit, column, tab_size):
    return tab_size - column % tab_size if unit.kind == 'tab' else unit.width


@dataclass(frozen=True, slots=True)
class TextMetrics:
    """Immutable shared metrics for layout, clipping and grapheme-aware editing."""

    text: str
    policy: TextPolicy
    units: tuple[TextUnit, ...]
    boundaries: tuple[int, ...]

    def _offset(self, offset):
        _nonnegative_int(offset, 'offset')
        if offset > len(self.text):
            raise ValueError('offset beyond normalized text')

    def next_boundary(self, offset):
        """Move right by a whole grapheme (or to its end from within it)."""
        self._offset(offset)
        index = min(bisect_right(self.boundaries, offset), len(self.boundaries) - 1)
        return self.boundaries[index]

    def previous_boundary(self, offset):
        """Move left by a whole grapheme (or to its start from within it)."""
        self._offset(offset)
        return self.boundaries[max(0, bisect_left(self.boundaries, offset) - 1)]

    def cell_position(self, offset, *, start_column=0, tab_size=4):
        """Return (column, row) at a normalized grapheme boundary; never inside it."""
        self._offset(offset)
        _layout_options(start_column, tab_size)
        if offset not in self.boundaries:
            raise ValueError('offset is not a grapheme boundary')
        column, row = start_column, 0
        for unit in self.units:
            if unit.start >= offset:
                break
            if unit.kind == 'newline':
                column, row = 0, row + 1
            else:
                column += _unit_cells(unit, column, tab_size)
        return column, row

    def line_widths(self, *, start_column=0, tab_size=4):
        """Return each line's ending column; LF resets the column to zero."""
        _layout_options(start_column, tab_size)
        widths = []
        column = start_column
        for unit in self.units:
            if unit.kind == 'newline':
                widths.append(column)
                column = 0
            else:
                column += _unit_cells(unit, column, tab_size)
        return tuple(widths + [column])

    def clip(self, cells, *, left=0, tab_size=4):
        """Clip one line to [left, left+cells), blanking partial wide glyphs.

        Tabs are spaces at column-aware stops. No padding beyond actual content.
        Multi-line input is rejected so callers choose the line explicitly.
        """
        _nonnegative_int(cells, 'cells')
        _nonnegative_int(left, 'left')
        _layout_options(0, tab_size)
        if any(unit.kind == 'newline' for unit in self.units):
            raise ValueError('clip requires a single line')
        output = []
        column = 0
        right = left + cells
        for unit in self.units:
            if column >= right:
                break
            width = _unit_cells(unit, column, tab_size)
            end = column + width
            overlap = min(end, right) - max(column, left)
            if overlap > 0:
                if unit.kind == 'tab' or column < left or end > right:
                    output.append(' ' * overlap)
                else:
                    output.append(unit.text)
            column = end
        return ''.join(output)


def _measure(text, policy):
    units = []
    for start, end in grapheme_spans(text):
        cluster = text[start:end]
        if cluster == '\n':
            unit = TextUnit(start, end, '', 0, 'newline')
        elif cluster == '\t':
            unit = TextUnit(start, end, '', 0, 'tab')
        else:
            display, width = _display_grapheme(cluster, policy)
            unit = TextUnit(start, end, display, width)
        units.append(unit)
    return TextMetrics(text, policy, tuple(units), (0,) + tuple(unit.end for unit in units))


@lru_cache(maxsize=128)
def _cached_metrics(text, unicode_version, policy):
    return _measure(text, policy)


def text_metrics(text, policy=_DEFAULT_POLICY):
    """Normalize then measure; cache at most 128 texts of <=1024 code points.

    The shared key includes normalized text, Unicode version and the full policy.
    Larger texts are measured without retaining them in the shared cache.
    """
    if not isinstance(policy, TextPolicy):
        raise TypeError('policy must be TextPolicy')
    text = normalize_text(text, source=policy.source)
    if len(text) <= 1024:
        return _cached_metrics(text, UNICODE_VERSION, policy)
    return _measure(text, policy)


def clip_text(text, cells, *, left=0, tab_size=4, policy=_DEFAULT_POLICY):
    """Normalize, measure and safely clip one line using the shared metrics."""
    return text_metrics(text, policy).clip(cells, left=left, tab_size=tab_size)
