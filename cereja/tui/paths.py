"""On-demand bounded directory completion for private TUI path forms."""
import json
import os
import stat
from itertools import islice

from cereja.ui.buffer import Rect, Style
from cereja.ui.events import KeyEvent
from cereja.ui.operations import OperationBridge
from cereja.ui.overlays import OverlayAction, ParameterForm


MAX_COMPLETIONS = 32
MAX_ENTRIES = 1024
MAX_COMPLETION_BYTES = 8192


def directory_completions(value):
    """Inspect at most one bounded directory page, without following child links."""
    expanded = os.path.expanduser(value)
    parent, prefix = os.path.split(expanded)
    parent = parent or os.curdir
    matches, used, truncated = [], 0, False
    try:
        with os.scandir(parent) as entries:
            for index, entry in enumerate(islice(entries, MAX_ENTRIES)):
                if index + 1 == MAX_ENTRIES:
                    truncated = True
                if not os.path.normcase(entry.name).startswith(os.path.normcase(prefix)):
                    continue
                if any(ord(c) < 32 or ord(c) == 127 for c in entry.name):
                    continue
                metadata = entry.stat(follow_symlinks=False)
                if (entry.is_symlink() or getattr(metadata, 'st_file_attributes', 0) & 0x400
                        or not stat.S_ISDIR(metadata.st_mode)):
                    continue
                path = os.path.join(os.path.dirname(expanded), entry.name) + os.sep
                size = len(json.dumps(path, ensure_ascii=True).encode('ascii'))
                if (len(matches) >= MAX_COMPLETIONS or used + size > MAX_COMPLETION_BYTES
                        or len(path.encode('utf-8')) > 1024):
                    truncated = True
                    continue
                matches.append(path)
                used += size
    except OSError:
        return (), 'Directory unavailable or permission denied.'
    matches.sort(key=os.path.normcase)
    message = ('Partial directory suggestions; type a longer prefix.' if truncated else
               'No matching directories.' if not matches else '')
    return tuple(matches), message


class PathForm(ParameterForm):
    """ParameterForm with explicit Tab completion; binding/opening performs no I/O.

    The caller routes lifecycle events through consume(), keyboard events through
    handle_completion() before OverlayStack, and closes this form before its loop.
    Filesystem calls can block; close detaches observation without claiming to
    stop those calls. The existing OperationBridge owns worker exit and delivery.
    """

    def __init__(self, *args, path_fields=('root',), **kwargs):
        super().__init__(*args, **kwargs)
        self.path_fields = frozenset(path_fields)
        if not self.path_fields <= {field.identity for field in self.fields}:
            raise ValueError('unknown path completion field')
        self._completion_bridge = None
        self._completion_edit = None
        self._completion_field = None
        self._completion_pending = False
        self._completion_open = False
        self._completion_applied = None
        self.completions = ()
        self.completion_index = 0
        self.completion_message = ''

    def bind(self, loop):
        if self._completion_bridge is not None:
            raise RuntimeError('path form already bound')
        self._completion_bridge = OperationBridge(loop, self.identity + '/paths')

    @property
    def completing(self):
        return self._completion_open

    def close(self):
        if self._completion_bridge is not None:
            self._completion_bridge.close()
        self._completion_open = False

    def _dismiss(self):
        self._completion_open = False
        self.completions = ()
        self.completion_message = ''

    def _unchanged(self):
        if self._completion_field is None:
            return False
        editor = self.input(self._completion_field)
        return (editor.content.revision, editor.text) == self._completion_edit

    def _insert(self, path):
        editor = self.input(self._completion_field)
        editor.set_selection(0, len(editor.text))
        result = editor.insert(path)
        self._completion_applied = (self._completion_field, editor.content.revision)
        self._dismiss()
        return OverlayAction(result.kind, result.reason)

    def consume(self, event):
        bridge = self._completion_bridge
        if bridge is None:
            return False
        handled = bridge.handle(event)
        snapshot = bridge.snapshot
        if not self._completion_pending or snapshot.active:
            return handled
        self._completion_pending = False
        if not self._completion_open or not self._unchanged():
            self._dismiss()
            return handled
        if snapshot.delivery != 'delivered' or snapshot.state != 'Succeeded':
            self.completion_message = 'Directory suggestions unavailable. Escape closes.'
            return handled
        paths, message = json.loads(snapshot.outcome.value)
        self.completions = tuple(paths)
        self.completion_message = message
        self.completion_index = 0
        # A partial listing cannot establish that this is the only candidate.
        if len(paths) == 1 and not message:
            self._insert(paths[0])
        return handled

    def handle_completion(self, event, focused):
        if self._completion_open and (focused != self._completion_field or not self._unchanged()):
            self._dismiss()
        if not isinstance(event, KeyEvent):
            if self._completion_open:
                self._dismiss()
            return None
        key = event.key
        if self._completion_open:
            if not event.modifiers and key == 'escape':
                self._dismiss()
                return OverlayAction('changed')
            if not event.modifiers and key in ('up', 'down') and self.completions:
                self.completion_index = (self.completion_index + (-1 if key == 'up' else 1)) % len(self.completions)
                return OverlayAction('changed')
            if not event.modifiers and key in ('enter', 'tab'):
                if self.completions:
                    return self._insert(self.completions[self.completion_index])
                if self._completion_pending:
                    return OverlayAction('handled')
                self._dismiss()
                # An empty/failed completion must not trap keyboard focus.
                return None if key == 'tab' else OverlayAction('changed')
            self._dismiss()
            return None
        if event.modifiers or key != 'tab' or focused not in self.path_fields:
            return None
        editor = self.input(focused)
        if (not editor.text or editor.caret != len(editor.text) or editor.selection is not None
                or self._completion_applied == (focused, editor.content.revision)):
            self._completion_applied = None
            return None
        bridge = self._completion_bridge
        if bridge is None:
            return None
        if bridge.active:
            return OverlayAction('rejected', 'Directory completion is still running.')
        self._completion_field = focused
        self._completion_edit = (editor.content.revision, editor.text)
        self._completion_open = self._completion_pending = True
        self.completions = ()
        self.completion_message = 'Loading directories... Escape closes.'
        value = editor.text
        def complete(context):
            context.running()
            return json.dumps(directory_completions(value), ensure_ascii=True)
        try:
            bridge.start('Directory completion', complete)
        except Exception:
            self._completion_pending = False
            self.completion_message = 'Directory suggestions unavailable. Escape closes.'
        return OverlayAction('changed')

    def paint_completions(self, frame, bounds):
        if not self._completion_open:
            return False
        bounds = bounds.intersection(Rect(0, 0, frame.width, frame.height))
        if not bounds.width or not bounds.height:
            return True
        frame.clear(clip=bounds)
        frame.draw_text(bounds.x, bounds.y, 'Directories | Up/Down choose | Enter/Tab use | Esc back', clip=bounds)
        room = max(0, bounds.height - 2)
        start = max(0, self.completion_index - room + 1)
        for index, path in enumerate(self.completions[start:start + room], start):
            frame.draw_text(bounds.x, bounds.y + 1 + index - start,
                            ('> ' if index == self.completion_index else '  ') + json.dumps(path, ensure_ascii=True),
                            style=Style(reverse=index == self.completion_index), clip=bounds)
        footer = self.completion_message or f'{self.completion_index + 1}/{len(self.completions)} directories'
        if bounds.height > 1:
            frame.draw_text(bounds.x, bounds.y + bounds.height - 1, footer, clip=bounds)
        return True
