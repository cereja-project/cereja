"""Cereja TUI composition using public toolkit APIs; UI-thread-owned application state."""
import sys
import time

from cereja._version import __version__
from cereja.ui.buffer import CellBuffer, Rect, Style
from cereja.ui.editing import TextInput, copy_action
from cereja.ui.events import (KeyEvent, PasteEvent, ResizeEvent, TimerEvent, EOFEvent,
                              QuitEvent, InputErrorEvent, ProgressEvent)
from cereja.ui.feedback import InlineStatus, ProgressBar, ActivityIndicator
from cereja.ui.focus import FocusManager, FocusScope, FocusTarget
from cereja.ui.operations import OperationBridge, CooperativeCancellation, OperationBusy
from cereja.ui.overlays import (Suggestion, Suggestions, FormField, ParameterForm,
                               HelpOverlay, OverlayStack, Confirmation)
from cereja.ui.rendering import Cursor
from cereja.ui.scheduling import EventLoop
from cereja.ui.text import TextPolicy, text_metrics

from .catalogue import COMMANDS, REFERENCES, BY_NAME, parse_command
from .model import Results
from .system import DEFAULT_SECTIONS, validate_sections, parse_sections, failure_text


HELP = ('Cereja TUI keyboard\n\n'
        '/ discovers registered commands. Enter/Tab inserts a suggestion; a later Enter submits.\n'
        'Paste is literal text, including newlines. q remains text.\n'
        'Tab/Shift+Tab: composer, block, content, Copy, Latest, Help, Exit.\n'
        'Block: Left/Right select prior/next; Home/End select oldest/newest.\n'
        'Content: PageUp/PageDown scroll; Home/End reach boundaries; Ctrl+A selects text.\n'
        'Copy requests canonical text. Clipboard transport is unavailable.\n'
        'Ctrl+C copies an active text selection in its owning surface; otherwise requests exit.\n'
        'F1 opens help. Escape closes the top overlay or returns to the composer.\n'
        'Forms: Tab visits fields, Run, Back, Help. Enter validates.\n'
        'Only one operation runs. Navigation and help remain available.\n'
        'Exit during work defaults to Stay; Wait then exit is reversible.\n'
        'Cancel is offered only for the tested synthetic example at a safe checkpoint.\n'
        'Results are ephemeral: 20 completed, 16 KiB per block, 256 KiB aggregate safe payload.\n'
        'No disk history or automatic collection/export. System requires Run/Refresh.\n'
        'System: explicit basic non-sensitive Run/Refresh; no Cancel. Tree, Large files, Context, Archives and Download require explicit forms.\n\n' +
        '\n'.join('/' + c.name + ': ' + c.purpose for c in COMMANDS))


def _kind(value):
    return None if value in ('text', 'input', 'progress') else 'Use text, input or progress'


def _steps(value):
    return None if value.isascii() and value.isdecimal() and 1 <= int(value) <= 20 else 'Use 1..20'


def _rows(content, width, policy):
    """Application text layout with logical anchors, leaving canonical text unchanged."""
    rows, row, cells, start, logical = [], [], 0, 0, 0
    for unit in text_metrics(content.text, policy).units:
        if unit.kind == 'newline':
            rows.append((start, ''.join(row)))
            row, cells, logical, start = [], 0, 0, unit.end
            continue
        parts = [(' ', 1)] * (4 - logical % 4) if unit.kind == 'tab' else [(unit.text, unit.width)]
        for text, size in parts:
            if cells + size > width and cells:
                rows.append((start, ''.join(row)))
                row, cells, start = [], 0, unit.start
            row.append(text if size <= width else ' ' * width)
            cells += min(size, width)
            logical += size
    rows.append((start, ''.join(row)))
    return tuple(rows)


class TUI:
    """Construct inside an active TerminalSession; close before releasing that session.

    Commands are fixed application handlers. No API/function/shell invocation from input.
    An embedding caller owns session transport and may drive loop.turn itself.
    """

    def __init__(self, session, *, low_bandwidth=False, results=None):
        if session.capabilities.plain or not session.capabilities.paste:
            raise ValueError('Interactive Cereja TUI requires delimited paste; use the plain reference')
        self.session = session
        self.results = Results() if results is None else results
        self.composer = TextInput('composer', max_bytes=4096)
        self.focus = FocusManager(FocusScope('ledger', (FocusTarget('composer'),)))
        self.overlays = OverlayStack(self.focus)
        self.loop = EventLoop(session, self.handle, low_bandwidth=low_bandwidth)
        self.bridge = OperationBridge(self.loop, 'ledger-operation')
        self.status = InlineStatus('ledger-status', 'idle', 'Ready; / commands, F1 help')
        self.progress = ProgressBar('ledger-progress', 'Synthetic batches')
        self.activity = ActivityIndicator(self.loop, 'ledger-activity', 'Synthetic work')
        self.notice = ''
        self.exit_open = False
        self.waiting = False
        self.closed = False
        self._operation_block = None
        self._system_started = None
        self._tree_result = None
        self._tree_block = None
        self._context_block = None
        self._context_terms = ()
        self._review = None
        self._workflow_values = None
        from .workflows import forms
        self.workflow_forms = forms()
        self._receipt = None
        self._layout_cache = None
        self._page = 1
        self._scroll_rows = ()
        self._input_example = None
        self.examples_form = ParameterForm('examples-form', 'Synthetic examples', (
            FormField('kind', 'Kind', 'text', required=True, validator=_kind,
                      help='text: layout; input: selection; progress: finite in-memory worker'),
            FormField('steps', 'Batches (1..20)', '20', required=True, validator=_steps,
                      help='Only progress uses steps. No filesystem or network effects.'),
        ), primary='Run', max_input_bytes=64)
        self.system_form = ParameterForm('system-form', 'System: basic, identifiers excluded', (
            FormField('sections', 'Sections (comma-separated)', DEFAULT_SECTIONS, required=True,
                      validator=validate_sections,
                      help='system,os,cpu,memory,gpu,motherboard,bios. Explicit Run/Refresh only. '
                           'No Cancel, polling or global deadline. Missing fields are Unavailable.'),
        ), primary='Run/Refresh', max_input_bytes=128)
        self.tree_form = ParameterForm('tree-form', 'Tree: explicit root, read only', (
            FormField('root', 'Root directory', '', required=True),
            FormField('depth', 'Depth (0..8)', '3', required=True,
                      validator=lambda value: None if value.isascii() and value.isdecimal() and 0 <= int(value) <= 8 else 'Use 0..8'),
        ), primary='Run', max_input_bytes=1024)
        self.results.append('/home', self.home())
        self._sync_focus()

    def home(self):
        return (f'Cereja TUI {__version__}\n\n'
                'Discover capabilities with /. Select a suggestion, then submit explicitly.\n'
                'Use /examples for bounded synthetic demonstrations; /tools for the catalogue.\n'
                'System, Tree, Large files, Context, Archives and Download: explicit forms and bounded operations.\n'
                'Opening Home does not collect hardware, filesystem or network data.\n'
                'F1: help. Tab: inspect prior results. Ctrl+C: copy selection or exit.\n'
                'Session results are ephemeral. Clipboard transport is unavailable.')

    def diagnostics(self):
        caps = self.session.capabilities
        # Explicit allowlist, never environment, argv, paths, host IDs or diagnostic sources.
        fields = ('input_interactive', 'output_interactive', 'color_depth', 'unicode',
                  'cursor', 'alternate_screen', 'paste', 'reduced_motion', 'plain')
        return '\n'.join((f'Cereja: {__version__}',
                          f'Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}',
                          'Platform family: ' + sys.platform,
                          *(f'{name}: {getattr(caps, name)}' for name in fields),
                          'History: memory only; no export', 'Clipboard: unavailable',
                          f'Retained logical bytes: {self.results.retained_bytes}',
                          'Payload limits are not heap/RSS limits.',
                          'Hardware inventory: not collected by Diagnostics; System requires Run/Refresh'))

    def _sync_focus(self):
        available = self.results.current is not None
        self.focus.update(FocusScope('ledger', (
            FocusTarget('composer'), FocusTarget('block', enabled=available),
            FocusTarget('content', enabled=available), FocusTarget('copy', enabled=available),
            FocusTarget('latest', enabled=bool(self.results.blocks) and not self.results.follow_latest),
            FocusTarget('help'), FocusTarget('exit'))))

    def _help(self, text=HELP, title='Help'):
        self.overlays.open(HelpOverlay('ledger-help', title, text))

    def submit(self):
        try:
            command = parse_command(self.composer.text)
        except ValueError as error:
            self.notice = str(error)
            return
        capability, args = command.capability, command.arguments
        self.notice = ''
        name = capability.name
        if capability.ui == 'Planned UI':
            self._help(capability.description(), '/' + name + ': Planned UI')
        elif name == 'help':
            self._help(BY_NAME[args[0]].description() if args else HELP)
        elif name == 'system':
            if sys.platform != 'win32' and not sys.platform.startswith('linux') and sys.platform != 'darwin':
                self._help('System unavailable: collector supports Windows, Linux and macOS only.', '/system')
            else:
                self.overlays.open(self.system_form)
        elif name in self.workflow_forms:
            self.overlays.open(self.workflow_forms[name])
        elif name == 'tree':
            self.overlays.open(self.tree_form)
        elif name == 'examples':
            if args:
                self._example(args[0], 20)
            else:
                self.overlays.open(self.examples_form)
        else:
            text = self.home() if name == 'home' else self.diagnostics() if name == 'diagnostics' else (
                'Capability catalogue (references do not execute)\n\n' +
                '\n\n'.join(c.description() for c in COMMANDS + REFERENCES))
            self.results.append('/' + name, text)
        self._sync_focus()

    def _system(self, value):
        try:
            sections = parse_sections(value)
        except ValueError as error:
            self.notice = str(error)
            return
        if self.bridge.active:
            self.notice = 'Busy: one operation is active. Nothing was queued.'
            return
        from .system import collect
        self.progress.update('System: no numeric progress')
        block = self.results.append('/system', 'System collection requested. Prior snapshots remain selectable.', active=True)
        self._operation_block = block
        self._system_started = time.monotonic()
        try:
            self.bridge.start('System information', lambda context: collect(context, sections))
        except Exception:
            self.results.finish(block, 'Failed', 'System worker could not start. Nothing was queued.')
            self._operation_block = None
            self._system_started = None
            self.notice = 'System worker could not start. Nothing was queued.'
            self.status.update('error', self.notice)
            self.activity.update('error', self.notice)
            self._sync_focus()
            return
        self.refresh()
        self._sync_focus()

    def _workflow_review(self, name, values):
        from .workflows import prepare
        try:
            values, target = prepare(name, values)
        except (ValueError, OSError):
            self.notice = 'Invalid parameters. Review the workflow help and explicit paths.'
            return
        if target is None:
            self._workflow(name, values)
            return
        self._workflow_values = (name, values)
        self._review = Confirmation('workflow-review', target, form=self.workflow_forms[name])
        self.overlays.open(self._review)

    def _workflow_target(self):
        if self._review is None or self._workflow_values is None:
            return None
        from .workflows import prepare
        name, _ = self._workflow_values
        try:
            _, target = prepare(name, dict(self.workflow_forms[name].values))
            return target
        except (ValueError, OSError):
            return None

    def _workflow(self, name, values):
        if self.bridge.active:
            self.notice = 'Busy: one operation is active. Nothing was queued.'
            return
        from .workflows import execute
        block = self.results.append('/' + name, 'Explicit operation requested.', active=True)
        if name == 'context':
            self._context_block = block
            self._context_terms = tuple(values['query'].split())
        self._operation_block = block
        self._system_started = time.monotonic()
        self.progress.update(name + ': indeterminate')
        try:
            self.bridge.start(name, lambda context: execute(name, values, context))
        except Exception:
            self.results.finish(block, 'Failed', 'Worker could not start. Nothing was queued.')
            self._operation_block = None
            self._system_started = None
        self.refresh()
        self._sync_focus()

    def _tree(self, root, depth, identity=None):
        if self.bridge.active:
            self.notice = 'Busy: one operation is active. Nothing was queued.'
            return
        from .tree import TreeResult, load
        if identity is None:
            self._tree_result = TreeResult(root, depth)
            self._tree_block = self.results.append('/tree', 'Tree root requested.', active=True)
            relative = ''
        else:
            relative = self._tree_result.records[identity]['relative']
            self._tree_block.active = True
        block = self._tree_block
        self._operation_block = block
        self._system_started = time.monotonic()
        self.progress.update('Tree: no numeric progress')
        try:
            self.bridge.start('Repository tree', lambda context: load(root, relative, depth, context))
        except Exception:
            self.results.finish(block, 'Failed', 'Tree worker could not start.')
            self._operation_block = None
            self._system_started = None
        self.refresh()
        self._sync_focus()

    def _example(self, kind, steps):
        if kind == 'text':
            from .examples import TEXT
            self.results.append('/examples', TEXT)
        elif kind == 'input':
            if self._input_example is None:
                self._input_example = ParameterForm('input-example', 'Synthetic input/selection', (
                    FormField('sample', 'Synthetic sample (64 bytes)', '  café e\u0301 界  ',
                              help='Edit, Shift+arrows or Ctrl+A to select; Ctrl+C requests copy. No export.'),
                ), primary='Done', max_input_bytes=64)
            self.overlays.open(self._input_example)
        elif kind == 'progress':
            if self.bridge.active:
                self.notice = 'Busy: one operation is active. Nothing was queued.'
                return
            from .examples import progress
            self.progress.update('Synthetic batches')
            block = self.results.append('/examples', 'Synthetic progress example\nFinite in-memory batches.', active=True)
            self._operation_block = block
            try:
                self.bridge.start('Synthetic batches', lambda ctx: progress(ctx, steps),
                                  cancellation=CooperativeCancellation(
                                      'tests.test_ui_ledger: synthetic checkpoints, finite batches, no owned I/O'))
            except OperationBusy:
                self.results.finish(block, 'Failed', 'Operation was rejected; nothing queued.')
            except Exception:
                self.results.finish(block, 'Failed', 'Synthetic worker could not start.')
            self.refresh()
        self._sync_focus()

    def _exit(self):
        if not self.bridge.active:
            self.bridge.request_exit('exit')
            return
        if not self.exit_open:
            self.exit_open = True
            self.focus.push(FocusScope('ledger-exit', (
                FocusTarget('stay'), FocusTarget('wait'),
                FocusTarget('cancel', enabled='cancel' in self.bridge.exit_choices))), initial='stay')

    def _exit_key(self, event):
        choices = self.bridge.exit_choices
        width, height = self.session.backend.dimensions()
        self.focus.update(FocusScope('ledger-exit', (
            FocusTarget('stay'), FocusTarget('wait'),
            FocusTarget('cancel', enabled='cancel' in choices and width >= 40 and height >= 12))))
        if not isinstance(event, KeyEvent):
            return
        if event.key == 'tab' and event.modifiers <= {'shift'}:
            self.focus.traverse(backward='shift' in event.modifiers)
        elif not event.modifiers and event.key in ('escape', 'enter'):
            choice = 'stay' if event.key == 'escape' else self.focus.focused
            if choice == 'stay':
                self.bridge.request_exit('return')
                self.waiting = False
                self.notice = 'Exit wait withdrawn; returned to Cereja TUI'
            else:
                choice = 'exit' if not self.bridge.active else choice
                if choice == 'cancel' and not self.bridge.cancel():
                    self.notice = 'Exit choice changed; return and review the operation'
                    return
                self.bridge.request_exit('wait' if choice == 'cancel' else choice)
                self.waiting = True
                self.notice = 'Waiting to exit. Ctrl+C then Stay returns to Cereja TUI.'
            self.focus.pop()
            self.exit_open = False

    def _action(self, action):
        if action.kind == 'copy':
            self.notice = 'Copy unavailable: no clipboard transport. Selection preserved.'
        elif action.kind == 'exit':
            self._exit()
        elif action.kind == 'rejected':
            self.notice = action.reason

    def refresh(self):
        """Observe completion/publication failure after a turn or explicit UI action, never poll."""
        snapshot = self.bridge.snapshot
        receipt = (snapshot.state, snapshot.active, snapshot.delivery, snapshot.worker_exited)
        if receipt == self._receipt:
            return False
        self._receipt = receipt
        block = self._operation_block
        state = snapshot.state
        if block is not None and block.active:
            block.state = 'Final pending' if snapshot.worker_exited else state
        if block is not None and block.active and not snapshot.active:
            if snapshot.delivery == 'delivered':
                outcome = snapshot.outcome
                text = (outcome.value if state == 'Succeeded' and type(outcome.value) is str else
                        'Synthetic operation cooperatively cancelled; worker exited.' if state == 'Cancelled' else
                        (failure_text(outcome.message) if block.command == '/system' else
                         'Synthetic operation failed. Diagnostic details are omitted.'))
                if block.command == '/tree' and state == 'Succeeded':
                    try:
                        text = self._tree_result.receive(text)
                    except (ValueError, KeyError, TypeError):
                        state, text = 'Failed', 'Tree publication could not be interpreted.'
                elif block.command in ('/context', '/compress', '/download') and state != 'Succeeded':
                    from .workflows import failure_text as workflow_failure
                    text = workflow_failure(outcome.message)
                elif block.command == '/large-files' and state != 'Succeeded':
                    text = ('Large-file search failed. Review the root, permissions and limits; '
                            'root components must not be links/reparse points. '
                            'Diagnostic details omitted; no complete scan is claimed.')
                elif block.command == '/tree':
                    text = 'Tree load failed. The directory may be unavailable or outside the limits.'
                self.results.finish(block, state, text)
            else:
                self.results.finish(block, 'Unavailable',
                                    'Final observation unavailable: ' + snapshot.delivery + '. No success is claimed.')
            self._operation_block = None
            self._system_started = None
        active = snapshot.active and state in ('Running', 'Committing', 'CancelRequested') and not snapshot.worker_exited
        label = 'loading' if snapshot.active else {
            'Succeeded': 'success', 'Cancelled': 'canceled', 'Failed': 'error', 'CleanupFailed': 'error',
        }.get(state, 'idle')
        if not snapshot.active and snapshot.delivery not in ('none', 'delivered'):
            label = 'warning'
            state = 'Final observation unavailable'
        message = ('Final pending' if snapshot.active and snapshot.worker_exited else state)
        message += ' | ' + snapshot.delivery if snapshot.delivery not in ('none', 'delivered') else ''
        self.status.update(label, message)
        self.activity.update(label, message, active=active)
        self._sync_focus()
        return True

    def handle(self, event):
        if self.closed:
            return
        if isinstance(event, (EOFEvent, QuitEvent)):
            self.activity.close()
            self.bridge.close()
            return
        if isinstance(event, InputErrorEvent):
            self.notice = 'Input rejected: incomplete or oversized terminal input. Draft preserved.'
            self.render()
            return
        if self.bridge.handle(event):
            if isinstance(event, ProgressEvent):
                self.progress.update('Downloaded bytes' if self._operation_block and self._operation_block.command == '/download' else 'Synthetic batches', completed=event.completed,
                                     total=event.total, reliable_total=event.total is not None)
            self.refresh()
            self.render()
            return
        if isinstance(event, TimerEvent):
            if self.activity.handle(event):
                self.render(decorative=True)
            return
        self.refresh()
        width, height = self.session.backend.dimensions()
        if isinstance(event, ResizeEvent):
            self.render()
            return
        if self.exit_open:
            self._exit_key(event)
        elif width < 40 or height < 12:
            if isinstance(event, KeyEvent) and event.key == 'c' and event.modifiers == {'ctrl'}:
                # Hidden selections still own copy priority during recovery.
                block = self.results.current
                selection = (self.composer.selection if self.focus.focused == 'composer' else
                             block.selection if block and self.focus.focused == 'content' else None)
                if self.overlays.top is not None:
                    self._action(self.overlays.handle(event))
                else:
                    self._action(copy_action(selection))
        elif self.overlays.top is not None:
            overlay = self.overlays.top
            action = self.overlays.handle(event, current_target=self._workflow_target())
            if action.kind == 'submit' and isinstance(overlay, ParameterForm):
                self.overlays.close()
                if overlay is self.system_form:
                    self._system(dict(action.values)['sections'])
                elif overlay is self.tree_form:
                    values = dict(action.values)
                    self._tree(values['root'], int(values['depth']))
                elif overlay in self.workflow_forms.values():
                    name = next(name for name, form in self.workflow_forms.items() if form is overlay)
                    self._workflow_review(name, dict(action.values))
                elif overlay is self.examples_form:
                    values = dict(action.values)
                    self._example(values['kind'], int(values['steps']))
                else:
                    self.notice = 'Synthetic input example finished. Edited text is not a result or history.'
            elif action.kind == 'confirmed' and overlay is self._review:
                current = self._workflow_target()
                if self._review.authorization(current) == action.target and current is not None:
                    name, values = self._workflow_values
                    self._workflow(name, values)
                else:
                    self.notice = 'Target changed; review again.'
                self._review = None
                self._workflow_values = None
            else:
                self._action(action)
        elif isinstance(event, KeyEvent) and event.key == 'f1' and not event.modifiers:
            self._help()
        elif isinstance(event, KeyEvent) and event.key == 'tab' and event.modifiers <= {'shift'}:
            self.focus.traverse(backward='shift' in event.modifiers)
        elif isinstance(event, KeyEvent) and event.key == 'escape' and not event.modifiers:
            if self.focus.focused == 'content':
                self.results.clear_selection()
            self.focus.focus('composer')
        elif self.focus.focused == 'composer':
            action = self.composer.handle(event)
            if action.kind == 'submit':
                self.submit()
            elif action.kind == 'changed' and isinstance(event, (KeyEvent, PasteEvent)):
                prefix = self.composer.text[:self.composer.caret]
                if prefix.startswith('/') and not any(c.isspace() for c in prefix):
                    self.overlays.open(Suggestions('slash', self.composer, tuple(
                        Suggestion(c.name, '/' + c.name, '/' + c.name + ' ', c.ui) for c in COMMANDS)))
            self._action(action)
        else:
            self._result_key(event)
        self.refresh()
        self._sync_focus()
        self.render()

    def _result_key(self, event):
        if not isinstance(event, KeyEvent):
            return
        focused, block = self.focus.focused, self.results.current
        if (focused == 'content' and block is self._tree_block and self._tree_result is not None
                and not event.modifiers):
            action = self._tree_result.view.handle(event)
            if action.kind == 'load':
                self._tree(self._tree_result.root, self._tree_result.depth, action.identity)
            elif action.kind == 'inspect' and action.content is not None:
                self._help(action.content.text, 'Tree path')
            if action.kind != 'unhandled':
                return
        if event.key == 'c' and event.modifiers == {'ctrl'}:
            self._action(copy_action(block.selection if block and focused == 'content' else None))
        elif event.key == 'a' and event.modifiers == {'ctrl'} and focused == 'content':
            self.results.select_text()
        elif not event.modifiers and event.key == 'enter':
            if focused == 'help':
                self._help()
            elif focused == 'exit':
                self._exit()
            elif focused == 'latest':
                self.results.latest()
            elif focused == 'copy':
                self.results.select_text()
                self.notice = 'Copy unavailable: no clipboard transport. Canonical text selected.'
            elif focused == 'block':
                self.focus.focus('content')
        elif block and not event.modifiers:
            if focused == 'block' and event.key in ('left', 'right', 'home', 'end'):
                ids = [b.identity for b in self.results.blocks]
                index = ids.index(block.identity)
                index = (0 if event.key == 'home' else len(ids) - 1 if event.key == 'end' else
                         max(0, min(len(ids) - 1, index + (-1 if event.key == 'left' else 1))))
                self.results.select(ids[index], latest=event.key == 'end')
            elif focused == 'content' and self._scroll_rows:
                rows = self._scroll_rows
                index = max((i for i, (start, _) in enumerate(rows) if start <= block.anchor), default=0)
                if event.key in ('page_up', 'page_down', 'home', 'end', 'up', 'down'):
                    step = max(1, self._page - 1) if event.key.startswith('page_') else 1
                    index = (0 if event.key == 'home' else len(rows) - 1 if event.key == 'end' else
                             max(0, min(len(rows) - 1, index + step * event.repeat *
                                        (-1 if event.key in ('up', 'page_up') else 1))))
                    block.anchor = rows[index][0]
                    self.results.follow_latest = False

    def _paint_results(self, frame, body):
        block = self.results.current
        if block is None:
            frame.draw_text(body.x, body.y, 'No retained results', clip=body)
            return '0 results'
        index = self.results.blocks.index(block)
        y = body.y
        if index and body.height > 4:
            previous = self.results.blocks[index - 1]
            frame.draw_text(body.x, y, f'  {previous.identity} {previous.command} [{previous.state}]', clip=body)
            y += 1
        marker = '>' if self.focus.focused == 'block' else ' '
        frame.draw_text(body.x, y, f'{marker}* {block.identity} {block.command} [{block.state}]',
                        clip=body, style=Style(bold=True))
        y += 1
        if block is self._tree_block and self._tree_result is not None:
            self._tree_result.view.paint(frame, Rect(body.x, y, body.width, max(0, body.height - (y - body.y))),
                                         focused=self.focus.focused == 'content')
            return 'Tree | Right expand/load | Left collapse | Enter inspect'
        # A pinned revision stays readable when its active operation completes.
        content = block.selection.content if block.selection else block.content
        key = (content.identity, content.revision, body.width, frame.policy)
        if self._layout_cache is None or self._layout_cache[0] != key:
            self._layout_cache = key, _rows(content, max(1, body.width), frame.policy)
        rows = self._layout_cache[1]
        page = max(1, body.y + body.height - y)
        row = max((i for i, (start, _) in enumerate(rows) if start <= block.anchor), default=0)
        row = min(row, max(0, len(rows) - page))
        self._page, self._scroll_rows = page, rows
        for _, text in rows[row:row + page]:
            selected = block.selection is not None
            frame.draw_text(body.x, y, text, clip=body, style=Style(reverse=selected))
            if block is self._context_block and block.state == 'Succeeded':
                from .workflows import highlight_spans
                spans = highlight_spans(text, self._context_terms)
                x = body.x
                for unit in text_metrics(text, frame.policy).units:
                    if any(start < unit.end and end > unit.start for start, end in spans):
                        frame.draw_text(x, y, unit.text, clip=body,
                                        style=Style(bold=True, reverse=selected))
                    x += unit.width
            y += 1
        pinned = ' pinned' if content is not block.content else ''
        return f'{index + 1}/{len(self.results.blocks)} | lines {row + 1}-{min(len(rows), row + page)}/{len(rows)}{pinned}'

    def render(self, *, decorative=False):
        if self.closed or self.loop.stopped:
            return
        width, height = self.session.backend.dimensions()
        frame = CellBuffer(width, height, policy=TextPolicy(ascii_only=not self.session.capabilities.unicode))
        cursor = Cursor()
        if width < 40 or height < 12:
            self.activity.set_visible(False)
            for y, text in enumerate(('Resize to 40x12', f'Current {width}x{height}',
                                      'Ctrl+C: copy/exit', self.status.content.text)):
                frame.draw_text(0, y, text, clip=Rect(0, 0, max(0, width - 1), height))
            if self.exit_open:
                labels = ' '.join(('>' if self.focus.focused == v else '') + v for v in ('stay', 'wait'))
                frame.draw_text(0, max(0, height - 1), labels, clip=Rect(0, 0, max(0, width - 1), height))
            self.loop.request_render(frame, cursor=cursor, decorative=decorative)
            return frame
        body = Rect(2, 3, min(75, width - 4), height - 8)
        dock = Rect(2, height - 4, width - 4, 4)
        frame.draw_text(2, 0, 'Cereja TUI', style=Style(bold=True))
        frame.draw_text(2, 1, '|' + '-' * min(73, width - 5), style=Style(foreground=1))
        if self.notice:
            frame.draw_text(2, 2, self.notice, clip=Rect(2, 2, width - 4, 1))
        pager = self._paint_results(frame, body)
        alerts = []
        if self.results.omitted:
            alerts.append(f'Omitted {self.results.omitted}')
        if self.results.current is not None and self.results.current.truncated:
            alerts.append('Truncated')
        if not self.results.follow_latest:
            alerts.append('Latest')
        pager = ' | '.join((*alerts, pager))
        frame.draw_text(2, height - 5, pager, clip=Rect(2, height - 5, width - 4, 1))
        frame.draw_text(2, height - 4, '-' * (width - 4))
        input_view = self.composer.paint(frame, Rect(2, height - 3, width - 4, 1),
                                         focused=self.focus.focused == 'composer' or
                                         isinstance(self.overlays.top, Suggestions))
        cursor = input_view.cursor
        focused = self.focus.focused
        hints = ('Tab inspect | F1 help | ^C exit' if focused == 'composer' else
                 f'{focused}: Enter | Tab next | F1 help')
        frame.draw_text(2, height - 2, hints, clip=Rect(2, height - 2, width - 4, 1))
        status_rect = Rect(2, height - 1, width - 4, 1)
        if self.bridge.active:
            if self._system_started is not None:
                snapshot = self.bridge.snapshot
                phase = 'Final pending' if snapshot.worker_exited else snapshot.state
                self.activity.update('loading', f'{phase} | request elapsed {time.monotonic() - self._system_started:.1f}s',
                                     active=snapshot.state == 'Running' and not snapshot.worker_exited)
            self.activity.set_visible(not self.progress.determinate)
            if self.progress.determinate:
                snapshot = self.bridge.snapshot
                phase = 'Final pending' if snapshot.worker_exited else snapshot.state
                span = min(len(phase) + 1, status_rect.width)
                frame.draw_text(status_rect.x, status_rect.y, phase, clip=status_rect)
                self.progress.paint(frame, Rect(status_rect.x + span, status_rect.y,
                                               status_rect.width - span, 1))
            else:
                self.activity.paint(frame, status_rect)
        else:
            self.activity.set_visible(False)
            if self.notice:
                frame.draw_text(2, height - 1, self.notice, clip=status_rect)
            else:
                self.status.paint(frame, status_rect)
        if self.overlays.top is not None:
            shelf = isinstance(self.overlays.top, Suggestions)
            view = self.overlays.paint(frame, body, dock, current_target=self._workflow_target(),
                                       height=min(3 if width < 60 else 7, body.height) if shelf else body.height)
            if not shelf:
                cursor = view.cursor
            frame.clear(clip=Rect(2, height - 5, width - 4, 1))
            frame.draw_text(2, height - 5,
                            f'Overlay {view.viewport.offset[1] + 1}/{max(1, view.viewport.content_height)}',
                            clip=Rect(2, height - 5, width - 4, 1))
        if self.exit_open:
            frame.clear(clip=body)
            frame.draw_text(body.x, body.y, 'Exit: operation owns the slot', clip=body)
            frame.draw_text(body.x, body.y + 1, 'Stay or wait for actual worker exit.', clip=body)
            choices = [('stay', 'Stay'), ('wait', 'Wait')]
            if 'cancel' in self.bridge.exit_choices:
                choices.append(('cancel', 'Cancel'))
            text = ' '.join(('>' if focused == key else '') + '[' + label + ']' for key, label in choices)
            frame.draw_text(body.x, body.y + body.height - 1, text, clip=body)
            cursor = Cursor()
        self.loop.request_render(frame, cursor=cursor, decorative=decorative)
        return frame

    def run(self):
        self.render()
        try:
            while not self.loop.stopped:
                self.loop.turn(block=True)
                if not self.loop.stopped and self.refresh():
                    self.render()
        finally:
            self.close()

    def close(self):
        if not self.closed:
            self.closed = True
            self.activity.close()
            self.bridge.close()
            self.loop.close()


# Preserve old imports and pickle globals without a second class or wrapper.
Ledger = TUI
