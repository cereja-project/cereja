"""Opt-in, UI-owned grapheme editing and canonical-text copy requests.

No command parser, clipboard transport, terminal acquisition or worker is owned
here. A consumer routes a key to its current focus owner and handles intents.
"""

from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field, replace
import threading

from .buffer import CellBuffer, Rect, Style
from .events import KeyEvent, PasteEvent
from .layout import Viewport, inset
from .focus import focus_markers
from .rendering import Cursor
from .text import TextMetrics, TextPolicy, text_metrics

__all__ = ['TextContent', 'TextSelection', 'InputAction', 'InputView',
           'TextInput', 'copy_action']


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f'{name} must be an integer >= {minimum}')


@dataclass(frozen=True, slots=True)
class TextContent:
    """Immutable safe canonical text, identified independently of its layout.

    Callers own redaction, revision uniqueness and total retention. Security
    normalization preserves LF/TAB and intentional whitespace, escaping controls.
    ASCII/width fallback affects presentation only, never this copy payload.
    """

    identity: str
    revision: int
    text: str
    metrics: TextMetrics = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        if not isinstance(self.identity, str) or not self.identity:
            raise ValueError('content identity must be nonempty text')
        _integer(self.revision, 'revision')
        metrics = text_metrics(self.text)
        object.__setattr__(self, 'text', metrics.text)
        object.__setattr__(self, 'metrics', metrics)


@dataclass(frozen=True, slots=True)
class TextSelection:
    """Pin one content revision and logical Python-string grapheme offsets."""

    content: TextContent
    anchor: int
    caret: int

    def __post_init__(self):
        if not isinstance(self.content, TextContent):
            raise TypeError('selection needs TextContent')
        for value in (self.anchor, self.caret):
            _integer(value, 'offset')
            index = bisect_left(self.content.metrics.boundaries, value)
            if (index == len(self.content.metrics.boundaries) or
                    self.content.metrics.boundaries[index] != value):
                raise ValueError('offset must be a canonical grapheme boundary')

    @property
    def start(self):
        return min(self.anchor, self.caret)

    @property
    def end(self):
        return max(self.anchor, self.caret)

    @property
    def text(self):
        return self.content.text[self.start:self.end]


@dataclass(frozen=True, slots=True)
class InputAction:
    """Local result or intent: changed/handled/rejected/unhandled/submit/copy/exit.

    Copy is a request, never an acknowledgement. Consumers must retain state on
    unavailable/failed clipboard writes and must never convert copy into exit.
    """

    kind: str
    reason: str = ''
    selection: TextSelection | None = None


def copy_action(selection: TextSelection | None = None) -> InputAction:
    """Apply Ctrl+C priority for the key-owning surface's text selection only."""
    if selection is not None and not isinstance(selection, TextSelection):
        raise TypeError('selection must be TextSelection or None')
    if selection is not None and selection.start != selection.end:
        return InputAction('copy', selection=selection)
    return InputAction('exit')


@dataclass(frozen=True, slots=True)
class InputView:
    viewport: Viewport
    cursor: Cursor
    line_start: int


class TextInput:
    """Bounded edit state independent of focus, navigation and inspection.

    max_bytes bounds canonical UTF-8 text, after safe normalization. Rejection
    is atomic. The default 64 KiB is an input bound, not a Ledger retention or
    performance calibration. All mutations and painting belong to the creating
    UI thread; EventLoop owns scheduling and presentation cadence.
    """

    def __init__(self, identity: str, text: str = '', *, max_bytes: int = 65536):
        _integer(max_bytes, 'max_bytes', 1)
        self._thread = threading.get_ident()
        self._max_bytes = max_bytes
        if not isinstance(text, str):
            raise TypeError('initial value must be text')
        if len(text) > max_bytes:
            raise ValueError('initial text exceeds input byte limit')
        self._content = TextContent(identity, 0, text)
        if len(self._content.text.encode('utf-8')) > max_bytes:
            raise ValueError('initial canonical text exceeds input byte limit')
        self._caret = len(self._content.text)
        self._anchor = None
        self._scroll_x = 0
        self._line_start = 0

    def _check_thread(self):
        if threading.get_ident() != self._thread:
            raise RuntimeError('editing belongs to the UI thread')

    @property
    def content(self):
        return self._content

    @property
    def text(self):
        return self._content.text

    @property
    def caret(self):
        return self._caret

    @property
    def selection(self):
        if self._anchor is None or self._anchor == self._caret:
            return None
        return TextSelection(self._content, self._anchor, self._caret)

    def move(self, offset: int, *, extend: bool = False) -> InputAction:
        """Set a canonical boundary; extending retains the invoking anchor."""
        self._check_thread()
        if type(extend) is not bool:
            raise TypeError('extend must be bool')
        TextSelection(self._content, offset, offset)
        before = (self._caret, self._anchor)
        self._anchor = (self._caret if self._anchor is None else self._anchor) if extend else None
        self._caret = offset
        return InputAction('changed' if before != (self._caret, self._anchor) else 'handled')

    def set_selection(self, anchor: int, caret: int) -> None:
        self._check_thread()
        TextSelection(self._content, anchor, caret)
        self._anchor, self._caret = anchor, caret

    def _replace(self, start, end, inserted):
        candidate = self.text[:start] + inserted + self.text[end:]
        if len(candidate.encode('utf-8')) > self._max_bytes:
            return InputAction('rejected', 'Canonical text exceeds input byte limit')
        content = TextContent(self._content.identity, self._content.revision + 1, candidate)
        # Insertion/removal can join adjacent clusters. Snap to the end of the
        # joined cluster, never leave a caret inside a combining/ZWJ sequence.
        intended = start + len(inserted)
        caret = content.metrics.boundaries[bisect_left(content.metrics.boundaries, intended)]
        changed = candidate != self.text or self.selection is not None or caret != self._caret
        if candidate != self.text:
            self._content = content
        self._caret, self._anchor = caret, None
        return InputAction('changed' if changed else 'handled')

    def insert(self, text: str) -> InputAction:
        """Insert safe text (also suggestions); never submit or parse commands."""
        self._check_thread()
        if not isinstance(text, str):
            raise TypeError('inserted value must be text')
        # Bound work before normalization, including control expansion/surrogates.
        if len(text) > self._max_bytes:
            return InputAction('rejected', 'Inserted text exceeds input byte limit')
        normalized = text_metrics(text).text
        if len(normalized.encode('utf-8')) > self._max_bytes:
            return InputAction('rejected', 'Sanitized text exceeds input byte limit')
        if not normalized:
            return InputAction('handled')
        selected = self.selection
        start, end = (selected.start, selected.end) if selected else (self._caret, self._caret)
        return self._replace(start, end, normalized)

    def _motion(self, direction, count, extend):
        selected = self.selection
        origin = self._caret
        if selected and not extend:
            origin = selected.start if direction < 0 else selected.end
            count -= 1
        boundaries = self._content.metrics.boundaries
        index = bisect_left(boundaries, origin)
        target = max(0, min(len(boundaries) - 1, index + direction * count))
        return self.move(boundaries[target], extend=extend)

    def _delete(self, direction, count):
        selected = self.selection
        if selected:
            return self._replace(selected.start, selected.end, '')
        boundaries = self._content.metrics.boundaries
        index = bisect_left(boundaries, self._caret)
        target = boundaries[max(0, min(len(boundaries) - 1, index + direction * count))]
        return self._replace(min(target, self._caret), max(target, self._caret), '')

    def handle(self, event) -> InputAction:
        """Handle editing keys; all unknown/control-local keys stay caller-owned.

        Enter returns submit; Ctrl+C without text selection returns exit. Neither
        performs an application action. LF/slash in PasteEvent remain literal.
        """
        self._check_thread()
        if isinstance(event, PasteEvent):
            return self.insert(event.text)
        if not isinstance(event, KeyEvent):
            return InputAction('unhandled')
        mods, name = event.modifiers, event.key
        if mods == {'ctrl'} and name == 'c':
            return copy_action(self.selection)
        if mods == {'ctrl'} and name == 'a':
            self.set_selection(0, len(self.text))
            return InputAction('changed')
        altgr = ({'ctrl', 'alt'} <= mods and bool(event.text) and
                 all(ord(char) >= 32 and not 127 <= ord(char) <= 159 for char in event.text))
        if mods - {'shift'} and not altgr:
            return InputAction('unhandled')
        if name in ('left', 'right'):
            return self._motion(-1 if name == 'left' else 1, event.repeat, 'shift' in mods)
        if name in ('home', 'end'):
            return self.move(0 if name == 'home' else len(self.text), extend='shift' in mods)
        if name in ('backspace', 'delete') and not mods:
            return self._delete(-1 if name == 'backspace' else 1, event.repeat)
        if name == 'enter' and not mods:
            return InputAction('submit')
        if event.text:
            if event.repeat > self._max_bytes // max(1, len(event.text)):
                return InputAction('rejected', 'Repeated input exceeds input byte limit')
            return self.insert(event.text * event.repeat)
        return InputAction('unhandled')

    def paint(self, frame: CellBuffer, rect: Rect, *, focused: bool = False,
              clip: Rect | None = None, tab_size: int = 4) -> InputView:
        """Paint the caret's logical line, horizontally scrolled by grapheme.

        Two ASCII marker cells distinguish focus (>) and textual selection (*).
        LF is retained, without soft wrapping; Home/End address the entire draft.
        Narrow/hidden geometry preserves edit state. No timer or output is owned.
        """
        self._check_thread()
        if not isinstance(frame, CellBuffer) or not isinstance(rect, Rect):
            raise TypeError('paint needs CellBuffer and Rect')
        if type(focused) is not bool:
            raise TypeError('focused must be bool')
        _integer(tab_size, 'tab_size', 1)
        if clip is not None and not isinstance(clip, Rect):
            raise TypeError('clip must be Rect or None')
        bounds = Rect(0, 0, frame.width, frame.height)
        row = Rect(rect.x, rect.y, rect.width, min(1, rect.height))
        visible = row.intersection(bounds)
        if clip is not None:
            visible = visible.intersection(clip)
        # A clipped ancestor is the actual scroll window. Using the uncut
        # width would clamp scroll too early and leave the caret off screen.
        area = inset(row, left=2).intersection(visible)
        metrics = (self._content.metrics if frame.policy == TextPolicy()
                   else text_metrics(self.text, frame.policy))
        # Layout uses the same canonical offsets under ASCII/width fallback.
        start = self.text.rfind('\n', 0, self._caret) + 1
        end = self.text.find('\n', self._caret)
        if end < 0:
            end = len(self.text)
        units = []
        column, caret_column = 0, 0
        for unit in metrics.units:
            if unit.start < start:
                continue
            if unit.start >= end:
                break
            width = tab_size - column % tab_size if unit.kind == 'tab' else unit.width
            units.append((unit, column, width))
            column += width
            if unit.end <= self._caret:
                caret_column = column
        scroll = self._scroll_x if start == self._line_start else 0
        view = Viewport(area, column + 1, 1, scroll_x=scroll, clip=visible)
        view = view.ensure_visible(Rect(caret_column, 0, 1, 1))
        # Align the effective left edge to a whole grapheme/tab boundary.
        positions = [col for _, col, _ in units] + [column]
        left = view.offset[0]
        aligned = positions[max(0, bisect_right(positions, left) - 1)]
        if caret_column - aligned >= view.visible.width and view.visible.width:
            aligned = positions[bisect_left(positions, left)]
        view = replace(view, scroll_x=aligned)
        if view.visible.width and view.visible.height:
            self._scroll_x, self._line_start = view.scroll_x, start
        frame.clear(clip=visible)
        frame.draw_text(rect.x, rect.y, focus_markers(focused, self.selection is not None), clip=visible)
        ox, oy = view.origin
        selected = self.selection
        for unit, col, width in units:
            if col + width <= view.visible.x:
                continue
            if col >= view.visible.x + view.visible.width:
                break
            style = Style(reverse=selected is not None and
                          selected.start <= unit.start and unit.end <= selected.end)
            text = ' ' * width if unit.kind == 'tab' else unit.text
            frame.draw_text(ox + col, oy, text, clip=view.clip_rect, style=style)
        cx, cy = ox + caret_column, oy
        cursor_visible = (focused and view.clip_rect.x <= cx < view.clip_rect.x + view.clip_rect.width
                          and view.clip_rect.y <= cy < view.clip_rect.y + view.clip_rect.height)
        return InputView(view, Cursor(cx, cy, visible=True) if cursor_visible else Cursor(), start)
