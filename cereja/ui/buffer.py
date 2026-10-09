"""Owned cell buffers and deterministic opaque composition, without terminal I/O.

Unicode normalization and measurement belong exclusively to ui.text. Import this
module explicitly; the UI namespace and terminal transports do not import it.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

from .text import TextPolicy, text_metrics


__all__ = ['Style', 'Cell', 'Rect', 'CellBuffer', 'Layer', 'compose']


def _integer(value, name, *, nonnegative=False):
    if type(value) is not int:
        raise TypeError(f'{name} must be int')
    if nonnegative and value < 0:
        raise ValueError(f'{name} must be nonnegative')


def _color(value, name):
    if value is None:
        return
    if type(value) is int:
        if not 0 <= value <= 255:
            raise ValueError(f'{name} palette index must be in 0..255')
    elif isinstance(value, tuple) and len(value) == 3:
        if any(type(component) is not int for component in value):
            raise TypeError(f'{name} RGB components must be int')
        if any(not 0 <= component <= 255 for component in value):
            raise ValueError(f'{name} RGB components must be in 0..255')
    else:
        raise TypeError(f'{name} must be None, a palette index or an RGB tuple')


@dataclass(frozen=True, slots=True)
class Style:
    """Fully resolved attributes; None selects the terminal's default color.

    Values are semantic colors/flags, never ANSI strings. Composition replaces
    the complete style; it performs no inheritance, blending or theme lookup.
    Encoding and capability fallback belong to the subsequent renderer stage.
    """

    foreground: int | tuple[int, int, int] | None = None
    background: int | tuple[int, int, int] | None = None
    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    reverse: bool = False
    strikethrough: bool = False

    def __post_init__(self):
        _color(self.foreground, 'foreground')
        _color(self.background, 'background')
        for name in ('bold', 'dim', 'italic', 'underline', 'reverse', 'strikethrough'):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f'{name} must be bool')


_DEFAULT_STYLE = Style()
_DEFAULT_POLICY = TextPolicy()


@lru_cache(maxsize=256)
def _intern_style(style):
    return style


def _style(style):
    if not isinstance(style, Style):
        raise TypeError('style must be Style')
    return _intern_style(style)


@dataclass(frozen=True, slots=True)
class Cell:
    """Read-only cell value: a width-1/2 leader or an empty width-0 continuation.

    A blank is (' ', 1, style). Continuations carry their leader's effective
    style and are never printable. Buffers construct cells from shared metrics;
    arbitrary Cell values cannot be inserted through their public operations.
    """

    text: str = ' '
    width: int = 1
    style: Style = _DEFAULT_STYLE


@lru_cache(maxsize=256)
def _blank(style):
    return Cell(' ', 1, style)


@dataclass(frozen=True, slots=True)
class Rect:
    """Half-open cell rectangle; origin may be negative, dimensions may be zero."""

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self):
        _integer(self.x, 'x')
        _integer(self.y, 'y')
        _integer(self.width, 'width', nonnegative=True)
        _integer(self.height, 'height', nonnegative=True)

    def intersection(self, other: 'Rect') -> 'Rect':
        if not isinstance(other, Rect):
            raise TypeError('other must be Rect')
        x, y = max(self.x, other.x), max(self.y, other.y)
        return Rect(x, y, max(0, min(self.x + self.width, other.x + other.width) - x),
                    max(0, min(self.y + self.height, other.y + other.height) - y))


class CellBuffer:
    """Mutable owned row-major storage, exposed only through immutable snapshots.

    Every operation maintains whole-wide-glyph occupancy. Overwriting a leader
    or continuation first blanks the old entire footprint using its old style,
    even when that extends outside the requested clip. Incoming partial wide
    glyphs become styled blanks only in their visible cells. Blanks are opaque.
    """

    __slots__ = ('_width', '_height', '_policy', '_cells')

    def __init__(self, width: int, height: int, *, policy: TextPolicy = _DEFAULT_POLICY,
                 style: Style = _DEFAULT_STYLE):
        _integer(width, 'width', nonnegative=True)
        _integer(height, 'height', nonnegative=True)
        if not isinstance(policy, TextPolicy):
            raise TypeError('policy must be TextPolicy')
        style = _style(style)
        self._width, self._height, self._policy = width, height, policy
        self._cells = [_blank(style)] * (width * height)

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def policy(self) -> TextPolicy:
        return self._policy

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height

    @property
    def rows(self) -> tuple[tuple[Cell, ...], ...]:
        """Immutable full-frame snapshot, including height rows when width is zero."""
        return tuple(tuple(self._cells[y * self.width:(y + 1) * self.width])
                     for y in range(self.height))

    def cell(self, x: int, y: int) -> Cell:
        _integer(x, 'x')
        _integer(y, 'y')
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError('cell outside buffer')
        return self._cells[y * self.width + x]

    def copy(self) -> 'CellBuffer':
        result = CellBuffer(self.width, self.height, policy=self.policy)
        result._cells = self._cells.copy()
        return result

    def _clip(self, clip):
        bounds = Rect(0, 0, self.width, self.height)
        if clip is None:
            return bounds
        if not isinstance(clip, Rect):
            raise TypeError('clip must be Rect or None')
        return bounds.intersection(clip)

    def _erase(self, index):
        previous = self._cells[index]
        lead = index - 1 if previous.width == 0 else index
        blank = _blank(previous.style)
        for position in range(lead, lead + self._cells[lead].width):
            self._cells[position] = blank

    def _put(self, x, y, cell):
        index = y * self.width + x
        for position in range(index, index + cell.width):
            self._erase(position)
        self._cells[index] = cell
        if cell.width == 2:
            self._cells[index + 1] = Cell('', 0, cell.style)

    def _paint(self, x, y, cell, clip):
        if not clip.y <= y < clip.y + clip.height:
            return
        left, right = max(x, clip.x), min(x + cell.width, clip.x + clip.width)
        if left >= right:
            return
        if left == x and right == x + cell.width:
            self._put(x, y, cell)
        else:
            for column in range(left, right):
                self._put(column, y, _blank(cell.style))

    def clear(self, *, clip: Rect | None = None, style: Style = _DEFAULT_STYLE) -> None:
        """Fill the clipped region with opaque blanks, clearing touched wide glyphs."""
        clip, blank = self._clip(clip), _blank(_style(style))
        for y in range(clip.y, clip.y + clip.height):
            for x in range(clip.x, clip.x + clip.width):
                self._put(x, y, blank)

    def draw_text(self, x: int, y: int, text: str, *, style: Style = _DEFAULT_STYLE,
                  clip: Rect | None = None, tab_size: int = 4) -> None:
        """Paint shared safe metrics at an origin, without automatic wrapping.

        TAB stops are relative to each text line's column zero; LF resets to x
        on the next row. Coordinates and clip use destination cells. Validation
        and normalization complete before mutation. No raw LF/TAB is stored.
        """
        _integer(x, 'x')
        _integer(y, 'y')
        _integer(tab_size, 'tab_size', nonnegative=True)
        if not tab_size:
            raise ValueError('tab_size must be positive')
        clip, style = self._clip(clip), _style(style)
        measured = text_metrics(text, self.policy)
        column, line = 0, 0
        for unit in measured.units:
            if unit.kind == 'newline':
                column, line = 0, line + 1
            elif unit.kind == 'tab':
                end = column + tab_size - column % tab_size
                if clip.y <= y + line < clip.y + clip.height:
                    for cx in range(max(x + column, clip.x), min(x + end, clip.x + clip.width)):
                        self._put(cx, y + line, _blank(style))
                column = end
            else:
                self._paint(x + column, y + line, Cell(unit.text, unit.width, style), clip)
                column += unit.width

    def blit(self, source: 'CellBuffer', x: int = 0, y: int = 0, *,
             clip: Rect | None = None) -> None:
        """Opaque copy with destination clipping; self-copy reads a stable snapshot.

        Policies must match. Widths/styles are copied as measured, never inferred
        again from display text (which may already be a fallback or dotted mark).
        """
        if not isinstance(source, CellBuffer):
            raise TypeError('source must be CellBuffer')
        if source.policy != self.policy:
            raise ValueError('source and destination text policies must match')
        _integer(x, 'x')
        _integer(y, 'y')
        clip = self._clip(clip)
        cells = source._cells.copy() if source is self else source._cells
        for sy in range(max(0, clip.y - y), min(source.height, clip.y + clip.height - y)):
            for sx in range(source.width):
                cell = cells[sy * source.width + sx]
                if cell.width:
                    self._paint(x + sx, y + sy, cell, clip)

    def resized(self, width: int, height: int, *, style: Style = _DEFAULT_STYLE) -> 'CellBuffer':
        """Return an owned resized copy; new area is blank, clipped wide cells vanish."""
        result = CellBuffer(width, height, policy=self.policy, style=style)
        result.blit(self)
        return result


@dataclass(frozen=True, slots=True)
class Layer:
    """Opaque buffer at destination x/y, with an optional destination-space clip."""

    buffer: CellBuffer
    x: int = 0
    y: int = 0
    z: int = 0
    clip: Rect | None = None

    def __post_init__(self):
        if not isinstance(self.buffer, CellBuffer):
            raise TypeError('buffer must be CellBuffer')
        for name in ('x', 'y', 'z'):
            _integer(getattr(self, name), name)
        if self.clip is not None and not isinstance(self.clip, Rect):
            raise TypeError('clip must be Rect or None')


def compose(width: int, height: int, layers: Iterable[Layer] = (), *,
            policy: TextPolicy = _DEFAULT_POLICY, style: Style = _DEFAULT_STYLE) -> CellBuffer:
    """Rebuild a complete frame in ascending z, breaking ties by iterable order.

    Later layers overwrite earlier ones, including blanks. Each call starts from
    a fresh background so moving/removing layers cannot retain previous pixels.
    The caller owns scene state; no dirty geometry, I/O or front-buffer commit is
    implied. Layer buffers are read at call time and must not mutate concurrently.
    """
    layers = tuple(layers)
    if any(not isinstance(layer, Layer) for layer in layers):
        raise TypeError('layers must contain Layer values')
    if any(layer.buffer.policy != policy for layer in layers):
        raise ValueError('all layers must use the frame text policy')
    frame = CellBuffer(width, height, policy=policy, style=style)
    for layer in sorted(layers, key=lambda item: item.z):
        frame.blit(layer.buffer, layer.x, layer.y, clip=layer.clip)
    return frame
