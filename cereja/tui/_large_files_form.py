"""Private task presentation over the existing path/form/editing contracts."""
import threading

from cereja.ui.buffer import Rect, Style
from cereja.ui.events import KeyEvent
from cereja.ui.focus import FocusTarget
from cereja.ui.layout import Constraint, Viewport, inset, split_rows
from cereja.ui.overlays import FormField, OverlayAction, OverlayView, overlay_bounds
from cereja.ui.rendering import Cursor

from .paths import PathForm


class LargeFilesForm(PathForm):
    def __init__(self):
        from .large_files import LIMITS, _integer, _size_error
        from .workflows import _path_error
        super().__init__('large-files-form', 'Large files / Search', (
            FormField('root', 'Folder', '', required=True, validator=_path_error,
                      help='Enter continues to minimum size. Tab completes directories; arrows choose, Enter accepts. '
                           'Explicit trusted directory. Includes hidden/binary/ignored files; no content reads or links. '
                           'Search starts one worker. No Cancel or whole-scan deadline.'),
            FormField('min_size_bytes', 'Minimum size (e.g. 100 MiB)', '0', required=True, validator=_size_error,
                      help='0 includes all sizes. Bare integers mean bytes. B, KB/MB/GB/TB (1000-based) and '
                           'KiB/MiB/GiB/TiB (1024-based) are accepted. The result must be a whole byte count.'),
            *(FormField(name, label, str(default), required=True,
                        validator=lambda value, minimum=minimum: _integer(value, minimum),
                        help='Same parameter and default as find_large_files. Entry/depth limits bound traversal; '
                             'result/error limits bound retention. Hidden limits still apply and are validated. '
                             'UI text has a separate 12 KiB cap.')
              for name, label, default, minimum in LIMITS[1:]),
        ), primary='Search', max_input_bytes=1024)
        self.advanced = False

    @property
    def visible_fields(self):
        return self.fields if self.advanced else self.fields[:2]

    @property
    def targets(self):
        return tuple(FocusTarget(spec.identity, enabled=spec.enabled) for spec in self.visible_fields) + (
            FocusTarget('@primary'), FocusTarget('@advanced'), FocusTarget('@back'), FocusTarget('@help'))

    @property
    def customized(self):
        return any(self.input(spec.identity).text != spec.value for spec in self.fields[2:])

    def validate(self):
        action = super().validate()
        if any(name not in ('root', 'min_size_bytes') for name in self.errors):
            self.advanced = True
        return action

    def handle(self, event, focused):
        if threading.get_ident() != self._thread:
            raise RuntimeError('overlays belong to the UI thread')
        if isinstance(event, KeyEvent) and not event.modifiers and event.key == 'enter' and focused == '@advanced':
            self.advanced = not self.advanced
            return OverlayAction('focus-field', values=(('field', 'max_results' if self.advanced else 'min_size_bytes'),))
        action = super().handle(event, focused)
        if action.kind == 'submit' and focused == 'root':
            return OverlayAction('focus-field', values=(('field', 'min_size_bytes'),))
        return action

    def help_for(self, focused):
        if focused == '@advanced':
            return ('Advanced search limits\nAll four limits apply even when collapsed. Defaults: 20 retained files, '
                    '1000000 examined entries, depth 64, 32 error details. Editing does not scan. '
                    'Collapse preserves values. Entry/depth caps can make a scan incomplete; '
                    'retention caps can omit matching results. No Cancel or whole-scan deadline.')
        return super().help_for(focused)

    def paint(self, frame, bounds, composer, focused):
        rect = overlay_bounds(bounds, composer, height=bounds.height)
        title, body, footer = split_rows(rect, (Constraint.fixed(1), Constraint(), Constraint.fixed(1)))
        frame.clear(clip=rect)
        label = 'Large files / Advanced' if self.advanced else self.title
        frame.draw_text(title.x, title.y, label, clip=title, style=Style(bold=True))
        body = inset(body, left=1, right=1)
        if body.height >= 8:
            frame.draw_text(body.x, body.y, 'Find files by size. No file content is read.', clip=body)
            summary = 'customized' if self.customized else 'defaults (20 files; depth 64)'
            frame.draw_text(body.x, body.y + 1, 'Advanced limits: ' + summary, clip=body)
            body = Rect(body.x, body.y + 3, body.width, max(0, body.height - 3))
        fields = self.visible_fields
        view = Viewport(body, body.width, len(fields) * 3, scroll_y=self._scroll_y)
        index = next((i for i, spec in enumerate(fields) if spec.identity == focused), None)
        if index is not None and body.height >= 2:
            view = view.ensure_visible(Rect(0, index * 3, min(1, body.width), min(3, body.height)))
        if body.width and body.height:
            self._scroll_y = view.offset[1]
        ox, oy = view.origin
        cursor = Cursor()
        errors = self.errors
        for i, spec in enumerate(fields):
            y = oy + i * 3
            if y + 3 <= body.y or y >= body.y + body.height:
                continue
            label = 'Error: ' + errors[spec.identity] if body.height == 2 and spec.identity in errors else spec.label
            frame.draw_text(ox, y, label, clip=Rect(body.x, y, body.width, 1).intersection(body))
            field = self.input(spec.identity).paint(frame, Rect(ox, y + 1, body.width, 1), clip=body,
                                                    focused=focused == spec.identity)
            if field.cursor.visible:
                cursor = field.cursor
            frame.draw_text(ox, y + 2, errors.get(spec.identity, ''),
                            clip=Rect(body.x, y + 2, body.width, 1).intersection(body))
        toggle = 'Basic' if self.advanced else 'Advanced' + ('*' if self.customized else '')
        actions = (('@primary', self.primary), ('@advanced', toggle), ('@back', 'Back'), ('@help', 'Help'))
        text = ' '.join(('>' if focused == key else '') + '[' + label + ']' for key, label in actions)
        frame.draw_text(footer.x, footer.y, text, clip=footer)
        return OverlayView(rect, view, cursor)
