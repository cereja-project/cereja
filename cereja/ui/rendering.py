"""Cell diff, trusted VT encoding and acknowledged front-buffer transactions.

Import explicitly. Unicode display and occupancy are owned by ui.text/ui.buffer;
this module never measures a grapheme again. Damage is caller-owned scene data.
"""

from dataclasses import dataclass

from .buffer import Cell, CellBuffer, Rect, Style
from .text import normalize_text


__all__ = ['Cursor', 'full_diff', 'dirty_diff', 'Renderer']


@dataclass(frozen=True, slots=True)
class Cursor:
    """Desired zero-based terminal position and visibility (hidden by default)."""

    x: int = 0
    y: int = 0
    visible: bool = False

    def __post_init__(self):
        if type(self.x) is not int or type(self.y) is not int:
            raise TypeError('cursor coordinates must be int')
        if self.x < 0 or self.y < 0:
            raise ValueError('cursor coordinates must be nonnegative')
        if type(self.visible) is not bool:
            raise TypeError('cursor visibility must be bool')


def _buffers(front, back):
    if not isinstance(back, CellBuffer) or (front is not None and not isinstance(front, CellBuffer)):
        raise TypeError('diff requires CellBuffer values (front may be None)')


def _full_rows(back):
    return tuple(Rect(0, y, back.width, 1) for y in range(back.height)) if back.width else ()


def _runs(columns, y):
    if not columns:
        return []
    ordered = sorted(columns)
    start = previous = ordered[0]
    result = []
    for x in ordered[1:]:
        if x != previous + 1:
            result.append(Rect(start, y, previous - start + 1, 1))
            start = x
        previous = x
    result.append(Rect(start, y, previous - start + 1, 1))
    return result


def _changes(front, back, candidates):
    result = []
    for y, intervals in sorted(candidates.items()):
        columns = set()
        base = y * back.width
        for left, right in intervals:
            for x in range(left, right):
                if front._cells[base + x] != back._cells[base + x]:
                    columns.add(x)
        # Close over both old and new whole-glyph footprints. This also handles
        # chains of shifted wide cells and continuation-only style differences.
        pending = list(columns)
        while pending:
            x = pending.pop()
            for frame in (front, back):
                cell = frame._cells[base + x]
                left = x - 1 if cell.width == 0 else x
                right = left + frame._cells[base + left].width
                for neighbor in range(left, right):
                    if neighbor not in columns:
                        columns.add(neighbor)
                        pending.append(neighbor)
        result.extend(_runs(columns, y))
    return tuple(result)


def full_diff(front: CellBuffer | None, back: CellBuffer) -> tuple[Rect, ...]:
    """Reference diff: compare every text/style/occupancy cell, in row order.

    Initial frames, changed dimensions or text policies require a full redraw.
    Returned one-row runs include whole old and new wide-glyph footprints.
    """
    _buffers(front, back)
    if front is None or front.size != back.size or front.policy != back.policy:
        return _full_rows(back)
    return _changes(front, back, {y: [(0, back.width)] for y in range(back.height)})


def dirty_diff(front: CellBuffer | None, back: CellBuffer, damage) -> tuple[Rect, ...]:
    """Compare the union of caller-supplied old/new scene damage plus neighbors.

    Include removed/moved layers' old bounds, their new bounds and affected
    overlap. Each clipped rectangle expands one column on either side before
    comparison; resulting changes close over complete old/new glyphs. Omitting
    real damage is a caller error. Renderer.verify_damage checks that contract.
    Resize/policy changes and an unknown front ignore damage and redraw fully.
    """
    _buffers(front, back)
    damage = tuple(damage)
    if any(not isinstance(rect, Rect) for rect in damage):
        raise TypeError('damage must contain Rect values')
    if front is None or front.size != back.size or front.policy != back.policy:
        return _full_rows(back)
    candidates = {}
    for rect in damage:
        if not rect.width or not rect.height:
            continue
        left, right = max(0, rect.x - 1), min(back.width, rect.x + rect.width + 1)
        if left >= right:
            continue
        for y in range(max(0, rect.y), min(back.height, rect.y + rect.height)):
            candidates.setdefault(y, []).append((left, right))
    # Merge overlapping intervals to bound comparisons by the frame area, even
    # when scene damage contains many duplicate/overlapping rectangles.
    for y, intervals in candidates.items():
        merged = []
        for left, right in sorted(intervals):
            if merged and left <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(right, merged[-1][1]))
            else:
                merged.append((left, right))
        candidates[y] = merged
    return _changes(front, back, candidates)


_ANSI16 = ((0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0),
           (0, 0, 128), (128, 0, 128), (0, 128, 128), (192, 192, 192),
           (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0),
           (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255))
_LEVELS = (0, 95, 135, 175, 215, 255)
_PALETTE = (_ANSI16 + tuple((r, g, b) for r in _LEVELS for g in _LEVELS for b in _LEVELS)
            + tuple((v, v, v) for v in range(8, 239, 10)))


def _effective_color(color, depth):
    if not depth or color is None:
        return None
    if depth == 24 or (type(color) is int and (depth == 256 or color < 16)):
        return color
    rgb = _PALETTE[color] if type(color) is int else color
    palette = _PALETTE if depth == 256 else _ANSI16
    return min(range(len(palette)), key=lambda i: sum((a - b) ** 2 for a, b in zip(rgb, palette[i])))


def _prepare_frame(frame, capabilities):
    if not isinstance(frame, CellBuffer):
        raise TypeError('frame must be CellBuffer')
    if not capabilities.unicode and not frame.policy.ascii_only:
        raise ValueError('non-Unicode output requires a frame built with TextPolicy(ascii_only=True)')
    result = frame.copy()
    styles = {}
    for index, cell in enumerate(result._cells):
        if cell.style not in styles:
            s = cell.style
            styles[s] = Style(_effective_color(s.foreground, capabilities.color_depth),
                              _effective_color(s.background, capabilities.color_depth),
                              s.bold, s.dim, s.italic, s.underline, s.reverse, s.strikethrough)
        result._cells[index] = Cell(cell.text, cell.width, styles[cell.style])
    if not capabilities.plain and result.width:
        # No capability asserts delayed autowrap or DECAWM support. Reserve the
        # final column in every row. Whole-wide-glyph cleanup also blanks a
        # leader immediately to its left. Full ED clears that column; subsequent
        # transactions never print there (including one-column terminals).
        result.clear(clip=Rect(result.width - 1, 0, 1, result.height))
    return result


def _sgr(style):
    codes = ['0']
    for name, code in (('bold', 1), ('dim', 2), ('italic', 3), ('underline', 4),
                       ('reverse', 7), ('strikethrough', 9)):
        if getattr(style, name):
            codes.append(str(code))
    for color, prefix in ((style.foreground, 38), (style.background, 48)):
        if type(color) is int:
            if color < 16:
                codes.append(str((30 if prefix == 38 else 40) + color % 8 + (60 if color >= 8 else 0)))
            else:
                codes.extend((str(prefix), '5', str(color)))
        elif color is not None:
            codes.extend((str(prefix), '2', *(str(component) for component in color)))
    return '\x1b[' + ';'.join(codes) + 'm'


def _cup(x, y):
    return f'\x1b[{y + 1};{x + 1}H'


def _plain_snapshot(frame):
    rows = [''.join(cell.text for cell in row if cell.width) for row in frame.rows]
    return '\n'.join(rows) + ('\n' if rows else '')


def _encode(frame, changes, cursor, *, plain=False, full=False, cursor_changed=False):
    if plain:
        return _plain_snapshot(frame) if full or changes else ''
    if not full and not changes and not cursor_changed:
        return ''
    # CAN cancels a possible incomplete control sequence from an earlier failed
    # transaction. Reset origin/margins on full recovery before absolute CUP.
    parts = ['\x18\x1b[0m\x1b[?6l\x1b[r\x1b[2J'] if full else []
    parts.append('\x1b[?25l')
    previous_style = None
    for rect in changes:
        x, end = rect.x, rect.x + rect.width
        parts.append(_cup(x, rect.y))
        while x < end:
            cell = frame._cells[rect.y * frame.width + x]
            if cell.width == 0:
                raise ValueError('encoded run must start at a whole grapheme')
            if x == frame.width - 1:
                x += 1
                continue
            # Buffer operations already sanitize and measure. Defense at this
            # boundary checks control safety only, never resegments/recalculates
            # the stored width (dotted-circle/fallback display can differ).
            if normalize_text(cell.text, source=False) != cell.text or '\n' in cell.text or '\t' in cell.text:
                raise ValueError('unsafe display cell')
            if cell.style != previous_style:
                parts.append(_sgr(cell.style))
                previous_style = cell.style
            parts.append(cell.text)
            x += cell.width
    parts.append('\x1b[0m')
    if frame.width and frame.height:
        parts.append(_cup(cursor.x, cursor.y))
    parts.append('\x1b[?25h' if cursor.visible else '\x1b[?25l')
    return ''.join(parts)


def _capability_key(capabilities):
    return (capabilities.plain, capabilities.color_depth, capabilities.unicode,
            capabilities.cursor, capabilities.alternate_screen, capabilities.paste,
            capabilities.reduced_motion)


class Renderer:
    """Single-thread session renderer; front commits only after write and flush.

    Full diff is the default. Pass complete old/new damage for the optimized
    path, and verify_damage=True to compare it with the reference before I/O.
    Failure ends the session per its existing contract. Recover by acquiring a
    new session/renderer; its unknown front always causes a complete redraw.
    """

    def __init__(self, session, *, verify_damage=False):
        if type(verify_damage) is not bool:
            raise TypeError('verify_damage must be bool')
        self.session = session
        self.verify_damage = verify_damage
        self._front = None
        self._cursor = None
        self._capabilities = None
        self._generation = None

    @property
    def front(self):
        """Last successfully committed immutable grid, possibly now stale."""
        return None if self._front is None else self._front.rows

    @property
    def screen_known(self):
        """False after failure, suspension, other output or capability change."""
        return (self._front is not None and not self.session.closed and self.session._active
                and not self.session.needs_redraw
                and self._generation == self.session._output_generation
                and self._capabilities == _capability_key(self.session.capabilities))

    def invalidate(self):
        self.session._check_active()
        self.session.needs_redraw = True

    def render(self, frame: CellBuffer, *, damage=None, cursor: Cursor = Cursor()) -> bool:
        """Present a complete frame, returning False only for a clean broken pipe.

        Interactive dimensions must match the backend viewport. Plain snapshots
        accept arbitrary dimensions and ignore cursor-only changes. Input buffers
        must not mutate concurrently. No timeout is promised for a blocked write.
        """
        self.session._check_active()
        if not isinstance(cursor, Cursor):
            raise TypeError('cursor must be Cursor')
        capabilities = self.session.capabilities
        back = _prepare_frame(frame, capabilities)
        if not capabilities.plain:
            if back.size != self.session.backend.dimensions():
                raise ValueError('frame dimensions must match the terminal viewport')
            if back.width and back.height and (cursor.x >= back.width or cursor.y >= back.height):
                raise ValueError('cursor outside frame')
        front = self._front if self.screen_known else None
        full = front is None or front.size != back.size or front.policy != back.policy
        changes = full_diff(front, back) if damage is None else dirty_diff(front, back, damage)
        if damage is not None and self.verify_damage and changes != full_diff(front, back):
            raise ValueError('damage omits changed cells')
        text = _encode(back, changes, cursor, plain=capabilities.plain, full=full,
                       cursor_changed=cursor != self._cursor)
        # Freeze snapshot before transport. Native backends need no test hook.
        rows = back.rows
        if not self.session._write_frame(text, cells=rows):
            return False
        self._front, self._cursor = back, cursor
        self._capabilities = _capability_key(capabilities)
        self._generation = self.session._output_generation
        self.session.needs_redraw = False
        return True
