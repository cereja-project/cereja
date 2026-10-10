"""UI-10 opt-in suggestions, forms, help and exact-target review.

All outputs are local intents, never application execution or clipboard writes.
Unicode, edit state, focus scopes, cell geometry and scheduling remain with the
existing toolkit contracts. Callers supply redacted text and validated targets.
"""

from dataclasses import dataclass
import json
import threading
from typing import Callable

from .buffer import CellBuffer, Rect, Style
from .editing import TextContent, TextInput, TextSelection, copy_action
from .events import KeyEvent, PasteEvent
from .focus import FocusManager, FocusScope, FocusTarget, focus_markers
from .layout import Constraint, Viewport, inset, split_rows
from .rendering import Cursor
from .text import normalize_text, text_metrics

__all__ = ['Suggestion', 'Suggestions', 'FormField', 'ParameterForm', 'ReviewTarget',
           'Confirmation', 'HelpOverlay', 'OverlayAction', 'OverlayView',
           'OverlayStack', 'overlay_bounds']

_LIMIT = 65536


def _safe(text, limit=_LIMIT):
    if not isinstance(text, str):
        raise TypeError('widget text must be str')
    if len(text) > limit:
        raise ValueError('widget text exceeds byte limit')
    value = normalize_text(text)
    if len(value.encode('utf-8')) > limit:
        raise ValueError('safe widget text exceeds byte limit')
    return value


def _identity(value):
    if not isinstance(value, str) or not value or value.startswith('@'):
        raise ValueError('identity must be nonempty text without reserved @ prefix')


def _label(value, limit=_LIMIT):
    value = _safe(value, limit)
    if '\n' in value or '\t' in value:
        raise ValueError('label must be a single line without tabs')
    return value


def _owned(value):
    if threading.get_ident() != value._thread:
        raise RuntimeError('overlays belong to the UI thread')


def _bounded(values, count, measure):
    result, used = [], 0
    for value in values:
        if len(result) == count:
            raise ValueError('widget item count limit exceeded')
        used += measure(value)
        if used > _LIMIT:
            raise ValueError('aggregate widget metadata byte limit exceeded')
        result.append(value)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class OverlayAction:
    """An intent, not a job, effect authorization, or clipboard acknowledgement."""
    kind: str
    reason: str = ''
    values: tuple[tuple[str, str], ...] = ()
    selection: TextSelection | None = None
    target: 'ReviewTarget | None' = None


def _input_action(action):
    return OverlayAction(action.kind, action.reason, selection=action.selection)


@dataclass(frozen=True, slots=True)
class Suggestion:
    identity: str
    label: str
    insertion: str
    description: str = ''

    def __post_init__(self):
        _identity(self.identity)
        object.__setattr__(self, 'label', _label(self.label))
        for name in ('insertion', 'description'):
            object.__setattr__(self, name, _safe(getattr(self, name)))
        if not self.insertion:
            raise ValueError('suggestion insertion must be nonempty')


class Suggestions:
    """Stable prefix filtering over a bounded caller catalogue and edit range.

    start..caret is replaced; the suffix is preserved. Opening/typing trigger no
    parser. Enter/forward Tab consume one event, including repeats. A later key
    goes to the restored owner after the shelf closes.
    """

    def __init__(self, identity, composer, suggestions, *, start=0):
        _identity(identity)
        if not isinstance(composer, TextInput):
            raise TypeError('suggestions need TextInput')
        self._thread = threading.get_ident()
        self.identity, self.composer, self.start = identity, composer, start
        def measure(item):
            if not isinstance(item, Suggestion):
                raise TypeError('catalogue needs Suggestion')
            return sum(len(value.encode('utf-8')) for value in
                       (item.identity, item.label, item.insertion, item.description))
        self.items = _bounded(suggestions, 256, measure)
        if len({item.identity for item in self.items}) != len(self.items):
            raise ValueError('suggestion identities must be unique')
        self._selected = None
        self._matches = ()
        self._scroll_y = 0
        self.refresh()

    def refresh(self):
        _owned(self)
        TextSelection(self.composer.content, self.start, self.composer.caret)
        if self.start > self.composer.caret:
            raise ValueError('suggestion start must precede caret')
        self._binding = self.composer.content.revision, self.composer.caret
        prefix = self.composer.text[self.start:self.composer.caret]
        self._matches = tuple(item for item in self.items if item.insertion.startswith(prefix))
        ids = tuple(item.identity for item in self.matches)
        if self.selected not in ids:
            self._selected = ids[0] if ids else None

    @property
    def selected(self):
        return self._selected

    @property
    def matches(self):
        return self._matches

    @property
    def targets(self):
        return (FocusTarget(self.composer.content.identity),)

    def help_for(self, focused):
        return 'Enter/Tab inserts without execution. Escape keeps the draft.\n' + '\n'.join(
            item.label + ': ' + item.description for item in self.matches)

    def handle(self, event, focused):
        _owned(self)
        if isinstance(event, KeyEvent) and not event.modifiers:
            if event.key in ('up', 'down'):
                if not self.matches:
                    return OverlayAction('handled', 'No matching suggestions')
                ids = tuple(item.identity for item in self.matches)
                index = ids.index(self.selected)
                self._selected = ids[(index + (-event.repeat if event.key == 'up' else event.repeat)) % len(ids)]
                return OverlayAction('changed')
            if event.key in ('enter', 'tab'):
                if self._binding != (self.composer.content.revision, self.composer.caret):
                    self.refresh()
                    return OverlayAction('rejected', 'Draft changed; review suggestions again')
                if not self.matches:
                    return OverlayAction('handled', 'No matching suggestions')
                item = next(item for item in self.matches if item.identity == self.selected)
                caret, selection = self.composer.caret, self.composer.selection
                self.composer.set_selection(self.start, caret)
                result = self.composer.insert(item.insertion)
                if result.kind == 'rejected':
                    if selection is None:
                        self.composer.move(caret)
                    else:
                        self.composer.set_selection(selection.anchor, selection.caret)
                    return _input_action(result)
                return OverlayAction('inserted')
        result = self.composer.handle(event)
        if result.kind == 'changed':
            self.refresh()
        return _input_action(result)


@dataclass(frozen=True, slots=True)
class FormField:
    identity: str
    label: str
    value: str = ''
    required: bool = False
    help: str = ''
    enabled: bool = True
    validator: Callable[[str], str | None] | None = None

    def __post_init__(self):
        _identity(self.identity)
        object.__setattr__(self, 'label', _label(self.label))
        for name in ('value', 'help'):
            object.__setattr__(self, name, _safe(getattr(self, name)))
        if type(self.required) is not bool or type(self.enabled) is not bool:
            raise TypeError('required and enabled must be bool')
        if self.validator is not None and not callable(self.validator):
            raise TypeError('validator must be callable or None')


class ParameterForm:
    """Reusable values, labelled bounds/errors and explicit synchronous validation.

    Validator returns None or an error string. It neither normalizes domain
    targets nor executes work. Callback failure is generic, without diagnostics.
    Disabled fields are skipped in focus, validation and submitted values.
    """

    def __init__(self, identity, title, fields, *, primary='Review', max_input_bytes=_LIMIT):
        _identity(identity)
        self._thread = threading.get_ident()
        self.identity, self.title, self.primary = identity, _label(title), _label(primary, 32)
        def measure(spec):
            if not isinstance(spec, FormField):
                raise TypeError('form needs FormField')
            return sum(len(value.encode('utf-8')) for value in (spec.identity, spec.label, spec.value, spec.help))
        self._fields = _bounded(fields, 32, measure)
        if len({spec.identity for spec in self.fields}) != len(self.fields):
            raise ValueError('field identities must be unique')
        if type(max_input_bytes) is not int or max_input_bytes < 1:
            raise ValueError('max_input_bytes must be a positive integer')
        self._max_input_bytes = max_input_bytes
        self._inputs = {spec.identity: TextInput(identity + '/' + spec.identity, spec.value,
                                                 max_bytes=max_input_bytes) for spec in self.fields}
        self._errors, self._error_revisions, self._validation = {}, {}, None
        self._scroll_y = 0

    @property
    def fields(self):
        return self._fields

    @property
    def max_input_bytes(self):
        return self._max_input_bytes

    def input(self, identity):
        return self._inputs[identity]

    @property
    def values(self):
        return tuple((spec.identity, self.input(spec.identity).text) for spec in self.fields if spec.enabled)

    @property
    def snapshot(self):
        return tuple((spec.identity, self.input(spec.identity).content.revision,
                      self.input(spec.identity).text) for spec in self.fields)

    @property
    def validated(self):
        return self._validation is not None and self._validation == self.snapshot

    @property
    def errors(self):
        return {name: error for name, error in self._errors.items()
                if self.input(name).content.revision == self._error_revisions[name]}

    @property
    def targets(self):
        return tuple(FocusTarget(spec.identity, enabled=spec.enabled) for spec in self.fields) + (
            FocusTarget('@primary'), FocusTarget('@back'), FocusTarget('@help'))

    def help_for(self, focused):
        for spec in self.fields:
            if spec.identity == focused:
                return (spec.label + (' (required)' if spec.required else ' (optional)') +
                        '\nDefault: ' + spec.value + f'\nCanonical UTF-8 bound: {self.max_input_bytes} bytes\n' +
                        spec.help)
        return self.title + '\nReview validates values only. Back keeps them. Help restores field focus.'

    def validate(self):
        _owned(self)
        before = self.snapshot
        values = {name: text for name, revision, text in before}
        errors = {}
        for spec in self.fields:
            if not spec.enabled:
                continue
            value = values[spec.identity]
            error = 'Required' if spec.required and not value.strip() else None
            if error is None and spec.validator is not None:
                try:
                    result = spec.validator(value)
                    if result is not None:
                        error = _safe(result)
                except Exception:
                    error = 'Validation unavailable'
            if error:
                errors[spec.identity] = error
        # A callback may edit this or another field. Its successful result
        # applies only to the snapshot it actually saw, never the newer values.
        for old, current in zip(before, self.snapshot):
            if old != current:
                errors[current[0]] = 'Changed during validation'
        self._errors = errors
        self._error_revisions = {name: self.input(name).content.revision for name in errors}
        self._validation = None if errors else self.snapshot
        if errors:
            return OverlayAction('rejected', 'Review the visible field errors')
        return OverlayAction('submit', values=self.values)

    def handle(self, event, focused):
        _owned(self)
        if isinstance(event, KeyEvent) and not event.modifiers and event.key == 'enter':
            if focused == '@back':
                return OverlayAction('back')
            if focused == '@help':
                return OverlayAction('help')
            return self.validate()
        if focused in self._inputs:
            return _input_action(self.input(focused).handle(event))
        if isinstance(event, KeyEvent) and event.modifiers == {'ctrl'} and event.key == 'c':
            return _input_action(copy_action())
        return OverlayAction('unhandled')


@dataclass(frozen=True, slots=True)
class ReviewTarget:
    """Exact caller-normalized action/source/destination/effect/policy/version.

    permitted defaults False. True is a caller policy assertion, never proof of
    atomic publication, safe replacement or domain authorization.
    """
    action: str
    source: str
    destination: str
    output_kind: str
    effects: str
    policy: str
    version: str
    permitted: bool = False

    def __post_init__(self):
        for name in ('action', 'source', 'destination', 'output_kind', 'effects', 'policy', 'version'):
            value = getattr(self, name)
            if not value or _safe(value) != value:
                raise ValueError('review requires nonempty safe caller-normalized values')
        if type(self.permitted) is not bool:
            raise TypeError('permitted must be bool')
        _safe(self.plain_text)

    @property
    def plain_text(self):
        # JSON-quoted values distinguish literal LF/TAB/quotes/backslashes from
        # field delimiters, preserving the exact tuple without a forged label.
        pairs = (('Action', self.action), ('Source', self.source), ('Destination', self.destination),
                 ('Output', self.output_kind), ('Effects', self.effects), ('Policy', self.policy),
                 ('Target version', self.version))
        return '\n'.join(name + ': ' + json.dumps(value, ensure_ascii=False) for name, value in pairs)


def _wrap(content, cells, policy):
    """Presentation-only whole-grapheme wrapping; canonical content is untouched."""
    if cells < 1:
        return ()
    rows, row, column, logical_column = [], [], 0, 0
    for unit in text_metrics(content.text, policy).units:
        if unit.kind == 'newline':
            rows.append(''.join(row))
            row, column, logical_column = [], 0, 0
            continue
        parts = [(' ', 1)] * (4 - logical_column % 4) if unit.kind == 'tab' else [(unit.text, unit.width)]
        for text, width in parts:
            if column + width > cells and column:
                rows.append(''.join(row))
                row, column = [], 0
            logical_width = width
            if width > cells:
                text, width = ' ' * cells, cells
            row.append(text)
            column += width
            logical_column += logical_width
    rows.append(''.join(row))
    return tuple(rows)


class HelpOverlay:
    """Bounded immutable canonical inspection with independent paging/selection."""

    def __init__(self, identity, title, text, *, revision=0):
        _identity(identity)
        self._thread = threading.get_ident()
        self.identity, self.title = identity, _label(title)
        self._content = TextContent(identity, revision, _safe(text))
        self._selection = None
        self._scroll_y, self._page, self._end = 0, 1, False

    @property
    def content(self):
        return self._content

    @property
    def selection(self):
        return self._selection

    def select(self, anchor, caret):
        _owned(self)
        selected = TextSelection(self.content, anchor, caret)
        self._selection = selected if selected.start != selected.end else None

    @property
    def targets(self):
        return (FocusTarget('@back'),)

    def help_for(self, focused):
        return self.content.text

    def handle(self, event, focused):
        _owned(self)
        if not isinstance(event, KeyEvent):
            return OverlayAction('unhandled')
        if event.modifiers == {'ctrl'}:
            if event.key == 'a':
                self.select(0, len(self.content.text))
                return OverlayAction('changed')
            if event.key == 'c':
                return _input_action(copy_action(self.selection))
        if not event.modifiers:
            if event.key == 'enter':
                return OverlayAction('back')
            if event.key in ('up', 'down', 'page_up', 'page_down', 'home', 'end'):
                if event.key == 'home':
                    self._scroll_y, self._end = 0, False
                elif event.key == 'end':
                    self._end = True
                else:
                    step = max(1, self._page - 1) if event.key.startswith('page_') else 1
                    direction = -1 if event.key in ('up', 'page_up') else 1
                    self._scroll_y = max(0, self._scroll_y + direction * step * event.repeat)
                    self._end = False
                return OverlayAction('changed')
        return OverlayAction('unhandled')


class Confirmation:
    """Safe-default review; revisions and the complete tuple invalidate consent.

    authorization(current) must be checked again by the consumer before effects.
    Missing/uninspectable detail disables Run. Editing then reverting stays stale.
    """

    def __init__(self, identity, target, *, form=None):
        _identity(identity)
        if form is not None and not isinstance(form, ParameterForm):
            raise TypeError('form must be ParameterForm or None')
        self._thread = threading.get_ident()
        self.identity, self.title, self._form = identity, 'Exact target review', form
        self._revision = -1
        self.review(target)

    @property
    def target(self):
        return self._target

    @property
    def details(self):
        return self._details

    @property
    def form(self):
        return self._form

    @property
    def stale(self):
        return self._stale

    def review(self, target):
        _owned(self)
        if not isinstance(target, ReviewTarget):
            raise TypeError('target must be ReviewTarget')
        if self.form is not None and not self.form.validated:
            raise ValueError('form must be validated before review')
        details = HelpOverlay(self.identity + '/details', 'Details', target.plain_text,
                              revision=self._revision + 1)
        self._target, self._details = target, details
        self._revision += 1
        self._binding = self.form.snapshot if self.form is not None else None
        self._stale, self._consent, self._inspectable = False, None, False

    def _fresh(self, current):
        if current != self.target or (self.form is not None and
                                      (not self.form.validated or self.form.snapshot != self._binding)):
            self._stale, self._consent = True, None
        return not self.stale

    def authorization(self, current):
        _owned(self)
        return self._consent if self._fresh(current) and self._inspectable and self.target.permitted else None

    @property
    def targets(self):
        return (FocusTarget('@back'), FocusTarget('@primary', enabled=self._inspectable and
                                                self.target.permitted and not self.stale),
                FocusTarget('@help'))

    def help_for(self, focused):
        return self.target.plain_text

    def handle(self, event, focused, current=None):
        _owned(self)
        if isinstance(event, KeyEvent) and not event.modifiers and event.key == 'enter':
            if focused == '@back':
                self._consent = None
                return OverlayAction('back')
            if focused == '@help':
                return OverlayAction('help')
            if (not self._fresh(current) or not self._inspectable or not self.target.permitted):
                return OverlayAction('rejected', 'Target or fields changed, unavailable, or unsupported; review again')
            self._consent = self.target
            return OverlayAction('confirmed', target=self._consent)
        if isinstance(event, KeyEvent) and event.key == 'enter':
            return OverlayAction('unhandled')
        return self.details.handle(event, focused)


@dataclass(frozen=True, slots=True)
class OverlayView:
    rect: Rect
    viewport: Viewport
    cursor: Cursor = Cursor()


def overlay_bounds(bounds: Rect, composer: Rect, *, width=75, height=12):
    """Anchor above the composer, contained in drawable bounds and its width."""
    if not isinstance(bounds, Rect) or not isinstance(composer, Rect):
        raise TypeError('bounds and composer must be Rect')
    if any(type(value) is not int or value < 0 for value in (width, height)):
        raise ValueError('desired dimensions must be nonnegative integers')
    width = min(width, bounds.width, composer.width)
    above = min(max(0, composer.y - bounds.y), bounds.height)
    height = min(height, above)
    x = min(max(bounds.x, composer.x), bounds.x + bounds.width - width)
    return Rect(x, bounds.y + above - height, width, height)


def _footer(frame, rect, choices, focused):
    text = ' '.join(('>' if name == focused else '') + '[' + label + ']' for name, label in choices)
    frame.draw_text(rect.x, rect.y, text, clip=rect)


def _inspect(frame, content, body, owner):
    rows = _wrap(content, body.width, frame.policy)
    scroll = max(0, len(rows) - body.height) if owner._end else owner._scroll_y
    view = Viewport(body, body.width, len(rows), scroll_y=scroll)
    if body.width and body.height:
        owner._scroll_y, owner._page = view.offset[1], body.height
    ox, oy = view.origin
    for index in range(view.visible.y, view.visible.y + view.visible.height):
        frame.draw_text(ox, oy + index, rows[index], clip=view.clip_rect)
    return view


class OverlayStack:
    """Only the top overlay receives keys; focus records use FocusManager.

    Opening/closing preserves caller-owned draft/results and underlying form
    inputs. This is not a shell, overlay queue, worker lifecycle or widget tree.
    """

    def __init__(self, focus):
        if not isinstance(focus, FocusManager):
            raise TypeError('stack needs FocusManager')
        self._thread = threading.get_ident()
        self.focus, self._stack, self._help_id = focus, [], 0

    @property
    def top(self):
        return self._stack[-1] if self._stack else None

    def open(self, overlay):
        _owned(self)
        if not isinstance(overlay, (Suggestions, ParameterForm, HelpOverlay, Confirmation)):
            raise TypeError('unsupported overlay')
        _owned(overlay)
        initial = '@back' if isinstance(overlay, Confirmation) else None
        targets = overlay.targets
        if isinstance(overlay, Confirmation):
            targets = (FocusTarget('@back'), FocusTarget('@primary', enabled=False), FocusTarget('@help'))
        self.focus.push(FocusScope(overlay.identity, targets), initial=initial)
        if isinstance(overlay, Confirmation):
            overlay._consent = None
            overlay._inspectable = False
        self._stack.append(overlay)

    def close(self):
        _owned(self)
        if not self._stack:
            raise ValueError('no overlay to close')
        if self.focus.scope.identity != self.top.identity:
            raise ValueError('another focus scope owns the keys')
        self.focus.pop()
        return self._stack.pop()

    def _help(self):
        overlay = self.top
        self._help_id += 1
        try:
            help_view = HelpOverlay(overlay.identity + '/help-' + str(self._help_id), 'Context help',
                                    overlay.help_for(self.focus.focused))
        except (TypeError, ValueError):
            return OverlayAction('rejected', 'Help exceeds the bounded text limit')
        try:
            self.open(help_view)
        except ValueError:
            return OverlayAction('rejected', 'Help focus scope unavailable')
        return OverlayAction('help')

    def handle(self, event, *, current_target=None):
        _owned(self)
        overlay = self.top
        if overlay is None or self.focus.scope.identity != overlay.identity:
            return OverlayAction('unhandled')
        if isinstance(event, KeyEvent):
            if not event.modifiers and event.key == 'escape':
                self.close()
                return OverlayAction('back')
            if not event.modifiers and event.key == 'f1' and not isinstance(overlay, HelpOverlay):
                return self._help()
            if event.key == 'tab' and event.modifiers <= {'shift'} and (
                    not isinstance(overlay, Suggestions) or 'shift' in event.modifiers):
                self.focus.traverse(backward='shift' in event.modifiers)
                return OverlayAction('changed')
        if isinstance(overlay, Confirmation):
            action = overlay.handle(event, self.focus.focused, current_target)
            if action.kind == 'rejected':
                self.focus.focus('@back')
        else:
            action = overlay.handle(event, self.focus.focused)
        if self.focus.scope.identity != overlay.identity:
            return OverlayAction('rejected', 'Focus scope changed; review again')
        if isinstance(overlay, ParameterForm) and action.kind == 'rejected' and overlay.errors:
            self.focus.focus(next(iter(overlay.errors)))
        if action.kind in ('inserted', 'back', 'confirmed'):
            self.close()
        elif action.kind == 'help':
            return self._help()
        return action

    def paint(self, frame: CellBuffer, bounds: Rect, composer: Rect, *, current_target=None):
        _owned(self)
        if not isinstance(frame, CellBuffer):
            raise TypeError('paint needs CellBuffer')
        bounds = bounds.intersection(Rect(0, 0, frame.width, frame.height))
        overlay = self.top
        if overlay is None:
            empty = overlay_bounds(bounds, composer, height=0)
            return OverlayView(empty, Viewport(empty, 0, 0))
        rect = overlay_bounds(bounds, composer)
        title, body, footer = split_rows(rect, (Constraint.fixed(1), Constraint(), Constraint.fixed(1)))
        body = inset(body, left=1, right=1)
        frame.clear(clip=rect)
        if not isinstance(overlay, Confirmation):
            frame.draw_text(title.x, title.y, 'Suggestions' if isinstance(overlay, Suggestions) else overlay.title,
                            clip=title)
        cursor = Cursor()
        active = self.focus.scope.identity == overlay.identity
        focused = self.focus.focused if active else None
        if isinstance(overlay, ParameterForm):
            view = Viewport(body, body.width, len(overlay.fields) * 3, scroll_y=overlay._scroll_y)
            index = next((index for index, spec in enumerate(overlay.fields)
                          if spec.identity == focused), None)
            if index is not None and body.height >= 3:
                view = view.ensure_visible(Rect(0, index * 3, min(1, body.width), 3))
            if body.width and body.height:
                overlay._scroll_y = view.offset[1]
            ox, oy = view.origin
            errors = overlay.errors
            for index, spec in enumerate(overlay.fields):
                y = oy + index * 3
                if y + 3 <= body.y or y >= body.y + body.height:
                    continue
                label = spec.label + (' *' if spec.required else '') + f' [{overlay.max_input_bytes}B]'
                if not spec.enabled:
                    label += ' disabled'
                frame.draw_text(ox, y, label, clip=Rect(body.x, y, body.width, 1).intersection(body))
                field_view = overlay.input(spec.identity).paint(
                    frame, Rect(ox, y + 1, body.width, 1), clip=body,
                    focused=focused == spec.identity)
                if field_view.cursor.visible:
                    cursor = field_view.cursor
                frame.draw_text(ox, y + 2, errors.get(spec.identity, ''),
                                clip=Rect(body.x, y + 2, body.width, 1).intersection(body))
            _footer(frame, footer, (('@primary', overlay.primary), ('@back', 'Back'), ('@help', 'Help')),
                    focused)
        elif isinstance(overlay, Suggestions):
            view = Viewport(body, body.width, max(1, len(overlay.matches)), scroll_y=overlay._scroll_y)
            selected = next((i for i, item in enumerate(overlay.matches) if item.identity == overlay.selected), 0)
            view = view.ensure_visible(Rect(0, selected, min(1, body.width), 1))
            if body.width and body.height:
                overlay._scroll_y = view.offset[1]
            ox, oy = view.origin
            if not overlay.matches:
                frame.draw_text(ox, oy, 'No matching suggestions', clip=body)
            for index in range(view.visible.y, min(len(overlay.matches), view.visible.y + view.visible.height)):
                item = overlay.matches[index]
                marker = focus_markers(False, item.identity == overlay.selected)
                row_clip = Rect(body.x, oy + index, body.width, 1).intersection(body)
                frame.draw_text(ox, oy + index, marker + item.label + ' ' + item.description, clip=row_clip,
                                style=Style(reverse=item.identity == overlay.selected))
            _footer(frame, footer, (('insert', 'Enter/Tab: insert'), ('back', 'Esc: Back')), None)
        else:
            details = overlay.details if isinstance(overlay, Confirmation) else overlay
            view = _inspect(frame, details.content, body, details)
            if isinstance(overlay, Confirmation):
                overlay._fresh(current_target)
                overlay._inspectable = body.width >= 10 and body.height >= 2 and current_target is not None
                self.focus.update(FocusScope(overlay.identity, overlay.targets))
                if overlay.stale and active:
                    self.focus.focus('@back')
                focused = self.focus.focused if active else None
                destination = json.dumps(overlay.target.destination, ensure_ascii=False)
                prefix = ('Changed | To: ' if overlay.stale else 'Review to: ')
                if details.selection is not None:
                    prefix = '* ' + prefix
                available = max(0, title.width - len(prefix))
                metrics = text_metrics(destination, frame.policy)
                suffix = '...' if metrics.line_widths()[0] > available else ''
                label = prefix + metrics.clip(max(0, available - len(suffix))) + suffix
                frame.draw_text(title.x, title.y, label, clip=title)
                _footer(frame, footer, (('@back', 'Back'), ('@primary', 'Run' if any(target.identity == '@primary' and target.enabled
                        for target in overlay.targets) else 'Run off'), ('@help', 'Help'),
                        ('page', 'PgUp/PgDn')), focused)
            else:
                _footer(frame, footer, (('@back', 'Back'), ('page', 'PgUp/PgDn')), focused)
        return OverlayView(rect, view, cursor)
