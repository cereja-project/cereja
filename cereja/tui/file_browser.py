"""Bounded, UI-owned file navigation and action intents."""
import json

from cereja.ui.collections import Table, Column, Row, CollectionLimits
from cereja.ui.editing import TextContent
from cereja.ui.events import KeyEvent
from cereja.ui.focus import FocusTarget
from cereja.ui.layout import Constraint
from cereja.ui.overlays import HelpOverlay, OverlayAction

from .large_files import human_size


def _path_label(path):
    escaped = json.dumps(path, ensure_ascii=True)
    return escaped if len(escaped) <= 8192 else escaped[:8192] + '... [display shortened]'


class FileBrowser:
    def __init__(self, attachment):
        payload = json.loads(attachment)
        self.records = payload['files']
        self.omitted = payload['omitted']
        self.changed = payload.get('changed', False)
        self.view = Table('large-file-list', (
            Column('Size', Constraint.fixed(12)), Column('Relative path'),
        ), tuple(Row(str(i), (human_size(item['size']), _path_label(item['relative'])))
                 for i, item in enumerate(self.records)),
            limits=CollectionLimits(max_items=128, max_bytes=48000),
            state='incomplete' if self.omitted else 'complete',
            message=f'{self.omitted} additional retained files omitted from interactive list' if self.omitted else '')

    @property
    def selected(self):
        return self.records[int(self.view.selected)] if self.view.selected is not None else None


class FileMenu(HelpOverlay):
    actions = (('open-directory', 'Open containing directory'), ('copy', 'Copy file...'),
               ('move', 'Move file...'), ('delete', 'Delete file...'), ('details', 'File details'))

    def __init__(self, record):
        super().__init__('file-menu', 'File actions: arrows / Enter', '')
        self.record = record
        self.index = 0

    @property
    def targets(self):
        return (FocusTarget('@choose'),)

    @property
    def content(self):
        return TextContent(self.identity, self.index, '\n'.join(
            ('> ' if i == self.index else '  ') + label for i, (_, label) in enumerate(self.actions)))

    def handle(self, event, focused):
        if isinstance(event, KeyEvent) and not event.modifiers:
            if event.key == 'enter':
                return OverlayAction('file-action', values=(('action', self.actions[self.index][0]),))
            if event.key in ('up', 'down', 'home', 'end'):
                self.index = (0 if event.key == 'home' else len(self.actions) - 1 if event.key == 'end' else
                              max(0, min(len(self.actions) - 1, self.index + (-1 if event.key == 'up' else 1))))
                self._scroll_y = max(0, self.index - max(0, self._page - 1))
                return OverlayAction('changed')
        return super().handle(event, focused)
