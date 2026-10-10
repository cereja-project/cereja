"""Opt-in UI-11 bounded, read-only collections over caller-owned generic data.

Models and paint belong to the UI thread. Loading/inspection/copy are intents.
No terminal, clipboard, filesystem, application, worker or timer is acquired.
"""
from dataclasses import dataclass
import threading

from .buffer import CellBuffer, Rect
from .editing import TextContent, TextSelection, copy_action
from .events import KeyEvent
from .focus import FocusTarget, focus_markers
from .layout import Constraint, Viewport, inset, split_columns
from .text import normalize_text, text_metrics

__all__ = ['Row', 'Column', 'TreeNode', 'CollectionLimits', 'CollectionStatus',
           'CollectionAction', 'CollectionView', 'SelectableList', 'Table', 'TreeView']

_STATES = ('complete', 'incomplete', 'loading', 'error')
_TEXT_BYTES = 16384


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f'{name} must be an integer >= {minimum}')


def _safe(value, *, identity=False):
    if not isinstance(value, str):
        raise TypeError('collection text must be str')
    if len(value) > _TEXT_BYTES:
        raise ValueError('collection field exceeds 16 KiB')
    safe = normalize_text(value)
    if len(safe.encode('utf-8')) > _TEXT_BYTES:
        raise ValueError('safe collection field exceeds 16 KiB')
    if '\n' in safe:
        raise ValueError('collection labels must be single-line')
    if identity and (not value or safe != value or '\t' in value):
        raise ValueError('identity must be nonempty safe single-line text without tabs')
    return safe


def _content(value):
    if value is not None and not isinstance(value, TextContent):
        raise TypeError('canonical content must be TextContent or None')


def _state(value):
    if value not in _STATES:
        raise ValueError('state must be complete, incomplete, loading or error')


@dataclass(frozen=True, slots=True)
class Row:
    """Stable ID, one-line display cells and optional explicit canonical payload.

    No cell-aligned or delimiter-joined copy representation is inferred.
    """
    identity: str
    cells: tuple[str, ...]
    content: TextContent | None = None

    def __post_init__(self):
        _safe(self.identity, identity=True)
        if not isinstance(self.cells, tuple) or not 1 <= len(self.cells) <= 32:
            raise ValueError('row cells must be a tuple with 1..32 entries')
        object.__setattr__(self, 'cells', tuple(_safe(cell) for cell in self.cells))
        _content(self.content)


@dataclass(frozen=True, slots=True)
class Column:
    label: str
    constraint: Constraint = Constraint()

    def __post_init__(self):
        object.__setattr__(self, 'label', _safe(self.label))
        if not isinstance(self.constraint, Constraint):
            raise TypeError('column constraint must be Constraint')


@dataclass(frozen=True, slots=True)
class TreeNode:
    """Generic node; parent must precede its children in each supplied snapshot.

    branch declares children even when not loaded. state/message describe this
    node's child enumeration, not a domain operation or synthetic progress.
    """
    identity: str
    label: str
    parent: str | None = None
    branch: bool = False
    state: str = 'complete'
    message: str = ''
    content: TextContent | None = None

    def __post_init__(self):
        _safe(self.identity, identity=True)
        if self.parent is not None:
            _safe(self.parent, identity=True)
        object.__setattr__(self, 'label', _safe(self.label))
        object.__setattr__(self, 'message', _safe(self.message))
        if type(self.branch) is not bool:
            raise TypeError('branch must be bool')
        _state(self.state)
        _content(self.content)


@dataclass(frozen=True, slots=True)
class CollectionLimits:
    """Per-widget admission limits, not global memory or Ledger calibration.

    max_depth counts edges (a root is depth zero). Payload bytes include IDs,
    parent IDs, labels/cells, node messages and canonical text/identity.
    """
    max_items: int = 4096
    max_bytes: int = 1048576
    max_depth: int = 128

    def __post_init__(self):
        _integer(self.max_items, 'max_items', 1)
        _integer(self.max_bytes, 'max_bytes', 1)
        _integer(self.max_depth, 'max_depth')


@dataclass(frozen=True, slots=True)
class CollectionStatus:
    source_state: str
    retained_count: int
    retained_bytes: int
    examined_count: int
    limit: str = ''
    message: str = ''
    node_state: str = 'complete'

    @property
    def state(self):
        if self.limit:
            return 'truncated'
        for state in ('error', 'loading', 'incomplete'):
            if state in (self.source_state, self.node_state):
                return state
        return 'complete'

    @property
    def complete(self):
        return self.state == 'complete'


@dataclass(frozen=True, slots=True)
class CollectionAction:
    """An intent only. inspect/load carry stable ID; copy carries canonical range."""
    kind: str
    reason: str = ''
    identity: str | None = None
    content: TextContent | None = None
    selection: TextSelection | None = None


@dataclass(frozen=True, slots=True)
class CollectionView:
    viewport: Viewport
    visible_ids: tuple[str, ...]
    painted_rows: int
    formatted_cells: int
    status: CollectionStatus


def _payload_size(item, bound):
    fields = ((item.identity, *item.cells) if isinstance(item, Row) else
              (item.identity, item.label, item.parent or '', item.message))
    if item.content is not None:
        fields += (item.content.identity, item.content.text)
    # Avoid encoding a caller-owned canonical object already exceeding the cap.
    if sum(len(value) for value in fields) > bound:
        return bound + 1
    return sum(len(value.encode('utf-8')) for value in fields)


def _truncate(text, width, policy):
    """Shared Unicode metrics clip whole clusters; omission is presentation only."""
    if not width:
        return ''
    metrics = text_metrics(text, policy)
    if metrics.line_widths()[0] <= width:
        return metrics.clip(width)
    marker = '...' if policy.ascii_only else '…'
    marker = marker[:width]
    return metrics.clip(max(0, width - len(marker))) + marker


class _Collection:
    """Shared bounded navigation/copy/window policy, with operation-specific data."""

    def __init__(self, identity, limits):
        _safe(identity, identity=True)
        if not isinstance(limits, CollectionLimits):
            raise TypeError('limits must be CollectionLimits')
        self._thread = threading.get_ident()
        self._identity, self._limits = identity, limits
        self._items, self._order, self._indices = {}, (), {}
        self._selected, self._scroll_y, self._reveal = None, 0, False
        self._selection_visible, self._body_height = False, 0
        self._text_selection, self._selection_item, self._selection_notice = None, None, ''
        self._viewport = Viewport(Rect(0, 0, 0, 0), 0, 0)

    def _owned(self):
        if threading.get_ident() != self._thread:
            raise RuntimeError('collections belong to the UI thread')

    @property
    def identity(self):
        return self._identity

    @property
    def limits(self):
        return self._limits

    @property
    def targets(self):
        return (FocusTarget(self.identity),)

    @property
    def selected(self):
        return self._selected

    @property
    def order(self):
        """Current bounded, expanded navigation projection (not just painted rows)."""
        return self._order

    @property
    def scroll_y(self):
        return self._scroll_y

    @property
    def status(self):
        return self._status

    @property
    def text_selection(self):
        return self._text_selection

    @property
    def selection_notice(self):
        return self._selection_notice

    def item(self, identity):
        """Inspect full retained typed data, independently of display truncation."""
        return self._items[identity]

    def _admit(self, values, state, message):
        _state(state)
        message = _safe(message)
        items, depths, used, examined, limit = {}, {}, 0, 0, ''
        for item in values:
            examined += 1
            if len(items) == self.limits.max_items:
                limit = 'items'
                break
            expected = TreeNode if isinstance(self, TreeView) else Row
            if not isinstance(item, expected):
                raise TypeError(f'collection requires {expected.__name__}')
            if item.identity in items:
                raise ValueError('collection identities must be unique')
            if isinstance(item, Row):
                if len(item.cells) != self._columns:
                    raise ValueError('row arity must match columns')
            else:
                if item.parent is not None and item.parent not in items:
                    raise ValueError('a retained parent must precede its children')
                depth = 0 if item.parent is None else depths[item.parent] + 1
                if depth > self.limits.max_depth:
                    limit = 'depth'
                    break
            size = _payload_size(item, self.limits.max_bytes - used)
            if used + size > self.limits.max_bytes:
                limit = 'bytes'
                break
            if isinstance(item, TreeNode):
                depths[item.identity] = depth
            items[item.identity], used = item, used + size
        node_state = 'complete'
        if isinstance(self, TreeView):
            states = {item.state for item in items.values()}
            node_state = next((value for value in ('error', 'loading', 'incomplete') if value in states), 'complete')
        return items, depths, CollectionStatus(state, len(items), used, examined, limit, message, node_state)

    def _set_order(self, order):
        previous, indices, selected = self._order, self._indices, self.selected
        self._order = tuple(order)
        self._indices = {identity: index for index, identity in enumerate(self.order)}
        if selected not in self._indices:
            index = indices.get(selected)
            candidates = () if index is None else previous[index + 1:] + tuple(reversed(previous[:index]))
            self._selected = next((identity for identity in candidates if identity in self._indices),
                                  self.order[0] if self.order else None)
        if self.selected != selected or indices.get(selected) != self._indices.get(self.selected):
            self._reveal = True

    def _reconcile_text(self):
        if self.text_selection is None:
            return
        item = self._items.get(self._selection_item)
        if item is None or item.content != self.text_selection.content:
            self._text_selection, self._selection_item = None, None
            self._selection_notice = 'Text selection cleared: retained content removed or revised'
        elif item.content is not self.text_selection.content:
            self._text_selection = TextSelection(item.content, self.text_selection.anchor, self.text_selection.caret)

    def select(self, identity):
        self._owned()
        if identity not in self._indices:
            raise ValueError('selection must name a visible retained identity')
        self._selected, self._reveal = identity, True

    def scroll(self, dy):
        """Manual scroll keeps navigation/text selections independent."""
        self._owned()
        if type(dy) is not int:
            raise ValueError('dy must be int')
        self._viewport = self._viewport.scrolled(dy=dy)
        self._scroll_y, self._reveal = self._viewport.scroll_y, False
        visible = self._viewport.visible
        if visible.width and visible.height:
            self._selection_visible = (self.selected is not None and
                visible.y <= self._indices[self.selected] < visible.y + visible.height)

    def set_text_selection(self, identity, anchor, caret):
        self._owned()
        item = self._items.get(identity)
        if item is None or item.content is None:
            raise ValueError('text selection needs a retained explicit canonical payload')
        selection = TextSelection(item.content, anchor, caret)
        self._text_selection = selection if selection.start != selection.end else None
        self._selection_item = identity if self._text_selection is not None else None
        self._selection_notice = ''

    def clear_text_selection(self):
        self._owned()
        self._text_selection, self._selection_item, self._selection_notice = None, None, ''

    def handle(self, event, *, focused=True):
        self._owned()
        if type(focused) is not bool:
            raise TypeError('focused must be bool')
        if not focused or not isinstance(event, KeyEvent):
            return CollectionAction('unhandled')
        if event.key.lower() == 'c' and event.modifiers == frozenset({'ctrl'}):
            if self.selection_notice:
                return CollectionAction('rejected', self.selection_notice)
            action = copy_action(self.text_selection)
            return CollectionAction(action.kind, action.reason, selection=action.selection)
        if event.modifiers:
            return CollectionAction('unhandled')
        if event.key == 'enter':
            return (CollectionAction('inspect', identity=self.selected,
                                     content=self.item(self.selected).content) if self.selected is not None
                    else CollectionAction('handled', 'No retained item'))
        steps = {'up': -1, 'down': 1, 'page_up': -max(1, self._viewport.visible.height),
                 'page_down': max(1, self._viewport.visible.height)}
        if event.key not in (*steps, 'home', 'end'):
            return CollectionAction('unhandled')
        if not self.order:
            return CollectionAction('handled', 'No retained item')
        index = self._indices[self.selected]
        target = (0 if event.key == 'home' else len(self.order) - 1 if event.key == 'end'
                  else min(max(0, index + steps[event.key] * event.repeat), len(self.order) - 1))
        self.select(self.order[target])
        return CollectionAction('changed' if index != target else 'handled')

    def _footer(self):
        status = self.status
        if status.state == 'truncated':
            text = f'Truncated ({status.limit}) | {status.retained_count} retained | Source {status.source_state.title()}'
        elif status.complete and not status.retained_count:
            text = 'Empty | Complete'
        else:
            text = f'{status.state.title()} | {status.retained_count}'
        if status.message:
            text += ' | ' + status.message
        if self.selection_notice:
            text += ' | ' + self.selection_notice
        return text

    def paint(self, frame, rect, *, focused=True, clip=None):
        self._owned()
        if not isinstance(frame, CellBuffer) or not isinstance(rect, Rect):
            raise TypeError('paint requires CellBuffer and Rect')
        if type(focused) is not bool:
            raise TypeError('focused must be bool')
        if clip is not None and not isinstance(clip, Rect):
            raise TypeError('clip must be Rect or None')
        area = rect.intersection(Rect(0, 0, frame.width, frame.height))
        clipped = area if clip is None else area.intersection(clip)
        frame.clear(clip=clipped)
        header = min(1, max(0, area.height - 1)) if isinstance(self, Table) else 0
        body = Rect(area.x, area.y + header, area.width, max(0, area.height - header - 1))
        body = body.intersection(clipped)
        viewport = Viewport(body, body.width, len(self.order), scroll_y=self.scroll_y)
        reveal = self._reveal or (self._selection_visible and body.height < self._body_height)
        if reveal and self.selected is not None and body.width and body.height:
            viewport = viewport.ensure_visible(Rect(0, self._indices[self.selected], body.width, 1))
            self._scroll_y, self._reveal = viewport.scroll_y, False
        self._viewport = viewport
        if header:
            self._paint_header(frame, Rect(area.x, area.y, area.width, 1).intersection(clipped))
        visible = viewport.visible
        ids = self.order[visible.y:visible.y + visible.height] if visible.width else ()
        if body.width and body.height:
            self._selection_visible, self._body_height = self.selected in ids, body.height
        formatted = 0
        for row, identity in enumerate(ids):
            destination = Rect(body.x, body.y + row, body.width, 1)
            selected = identity == self.selected
            frame.draw_text(destination.x, destination.y, focus_markers(focused and selected, selected),
                            clip=destination)
            formatted += self._paint_item(frame, inset(destination, left=3), self.item(identity))
        if body.width and body.height and not ids:
            text = focus_markers(focused, False) + ' ' + ('Empty' if self.status.complete else self.status.state.title())
            frame.draw_text(body.x, body.y, _truncate(text, body.width, frame.policy), clip=body)
        if area.width and area.height:
            footer = Rect(area.x, area.y + area.height - 1, area.width, 1).intersection(clipped)
            # Footer clipping keeps the primary state word intact at small widths.
            if footer.width and footer.height:
                frame.draw_text(footer.x, footer.y, text_metrics(self._footer(), frame.policy).clip(footer.width),
                                clip=footer)
        return CollectionView(viewport, ids, len(ids), formatted, self.status)


class SelectableList(_Collection):
    """One display cell per row; bounded snapshots and stable selection."""

    def __init__(self, identity, rows, *, limits=CollectionLimits(), state='complete', message=''):
        super().__init__(identity, limits)
        self._columns = 1
        self.update(rows, state=state, message=message)

    def update(self, rows, *, state='complete', message=''):
        """Atomically replace a bounded prefix; iterator failures leave old state."""
        self._owned()
        items, _, status = self._admit(rows, state, message)
        self._items, self._status = items, status
        self._set_order(items)
        self._reconcile_text()

    def _paint_item(self, frame, rect, item):
        if not rect.width:
            return 0
        frame.draw_text(rect.x, rect.y, _truncate(item.cells[0], rect.width, frame.policy), clip=rect)
        return 1


class Table(SelectableList):
    """Read-only one-line rows, fixed/weighted columns and a pinned header."""

    def __init__(self, identity, columns, rows, *, limits=CollectionLimits(), state='complete', message=''):
        _Collection.__init__(self, identity, limits)
        retained = []
        for column in columns:
            if len(retained) == 32:
                raise ValueError('table has at most 32 columns')
            if not isinstance(column, Column):
                raise TypeError('table requires Column')
            retained.append(column)
        if not retained:
            raise ValueError('table requires at least one column')
        self._specs, self._columns = tuple(retained), len(retained)
        self.update(rows, state=state, message=message)

    @property
    def columns(self):
        return self._specs

    def _paint_cells(self, frame, rect, cells):
        tracks = split_columns(rect, (column.constraint for column in self.columns), gap=1)
        painted = 0
        for text, track in zip(cells, tracks):
            if track.width and track.height:
                frame.draw_text(track.x, track.y, _truncate(text, track.width, frame.policy), clip=track)
                painted += 1
        return painted

    def _paint_header(self, frame, rect):
        self._paint_cells(frame, inset(rect, left=3), (column.label for column in self.columns))

    def _paint_item(self, frame, rect, item):
        return self._paint_cells(frame, rect, item.cells)


class TreeView(_Collection):
    """Generic flat parent-linked snapshots; no recursive caller graph retained.

    Updates admit a parent-before-child prefix. Expand/collapse rebuild a bounded
    preorder projection; paint indexes only its visible slice. Right expands or
    selects a child; Left collapses or selects its parent. load is caller-owned.
    """

    def __init__(self, identity, nodes, *, limits=CollectionLimits(), state='complete', message=''):
        super().__init__(identity, limits)
        self._expanded = set()
        self.update(nodes, state=state, message=message)

    @property
    def expanded(self):
        return frozenset(self._expanded)

    def _branch(self, identity):
        item = self.item(identity)
        return bool(item.branch or item.state != 'complete' or self._children.get(identity))

    def update(self, nodes, *, state='complete', message=''):
        self._owned()
        items, depths, status = self._admit(nodes, state, message)
        children = {None: []}
        for item in items.values():
            children.setdefault(item.parent, []).append(item.identity)
        self._items, self._depths, self._children, self._status = items, depths, children, status
        self._expanded = {identity for identity in self._expanded if identity in items and self._branch(identity)}
        self._project()
        self._reconcile_text()

    def _project(self):
        order, stack = [], list(reversed(self._children[None]))
        while stack:
            identity = stack.pop()
            order.append(identity)
            if identity in self._expanded:
                stack.extend(reversed(self._children.get(identity, ())))
        self._set_order(order)

    def expand(self, identity):
        self._owned()
        if identity not in self._items:
            raise ValueError('node is not retained')
        if self._branch(identity) and identity not in self._expanded:
            self._expanded.add(identity)
            self._project()

    def collapse(self, identity):
        self._owned()
        if identity not in self._items:
            raise ValueError('node is not retained')
        if identity not in self._expanded:
            return
        selected = self.selected
        ancestor = selected
        while ancestor is not None and ancestor != identity:
            ancestor = self.item(ancestor).parent
        self._expanded.remove(identity)
        self._project()
        if selected != identity and ancestor == identity and identity in self._indices:
            self.select(identity)

    def handle(self, event, *, focused=True):
        self._owned()
        if (not focused or not isinstance(event, KeyEvent) or event.modifiers or
                event.key not in ('left', 'right')):
            return super().handle(event, focused=focused)
        if self.selected is None:
            return CollectionAction('handled', 'No retained node')
        item = self.item(self.selected)
        if event.key == 'left':
            if item.identity in self._expanded:
                self.collapse(item.identity)
                return CollectionAction('changed')
            if item.parent in self._indices:
                self.select(item.parent)
                return CollectionAction('changed')
            return CollectionAction('handled')
        if not self._branch(item.identity):
            return CollectionAction('handled')
        if item.identity not in self._expanded:
            self.expand(item.identity)
            return CollectionAction('load' if item.state in ('incomplete', 'error') else 'changed',
                                    identity=item.identity)
        children = self._children.get(item.identity, ())
        if children:
            self.select(children[0])
            return CollectionAction('changed')
        return CollectionAction('load' if item.state in ('incomplete', 'error') else 'handled',
                                identity=item.identity)

    def _paint_item(self, frame, rect, item):
        if not rect.width:
            return 0
        indentation = min(2 * self._depths[item.identity], max(0, rect.width - 5))
        sign = '-' if item.identity in self._expanded else '+' if self._branch(item.identity) else ' '
        prefix = ' ' * indentation + '[' + sign + '] '
        text = (f'{item.state.title()}: ' if item.state != 'complete' else '') + item.label
        frame.draw_text(rect.x, rect.y, prefix, clip=rect)
        label = inset(rect, left=len(prefix))
        if label.width:
            frame.draw_text(label.x, label.y, _truncate(text, label.width, frame.policy), clip=label)
        return 1
