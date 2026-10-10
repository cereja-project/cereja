# Text editing, selection and focus

UI-09 / [#308](https://github.com/cereja-project/cereja/issues/308) adds opt-in
`cereja.ui.editing` and `cereja.ui.focus`. Python 3.11+, standard library only.
Root and UI namespace imports remain lazy. These modules acquire no terminal,
start no workers/timers and implement no shell, domain operation or clipboard.

## Canonical text and copy

`TextContent(identity, revision, text)` is an immutable safe snapshot.
`text` is normalized with the existing [Unicode policy](ui-text.md):
ESC/C0/C1/DEL and bidi controls become visible text; lone surrogates become
replacement characters. LF, tabs, indentation, blank lines, intentional spaces
and Markdown syntax remain. There is no strip, dedent, NFC/NFD or soft wrapping.
Callers must redact secrets **before** construction, assign unique revisions
within an identity, and bound total retained snapshots.

`TextSelection(content, anchor, caret)` pins that exact snapshot. Offsets are
Python-string offsets into its **safe canonical text**, at grapheme boundaries
(including LF/TAB tokens). They are not original unsafe-source, UTF-8 byte, cell
or visual-row offsets. Reverse ranges are supported; `start`/`end` order them,
and `text` slices only that logical range. Rendering fallback never changes it.
A new snapshot with the same identity cannot shift the old selection's offsets.

`copy_action(selection)` returns an `InputAction('copy', selection=...)` for a
nonempty textual range, otherwise `InputAction('exit')`. Route it using only the
current key-owning surface's selection. A selected row/node remains navigation
state and does not create a `TextSelection`.

Copy is a **request**, not a successful clipboard acknowledgement. A consumer
must branch on `copy`, report unavailable/failure without exiting, and retain
the draft/range/focus/inspection. It may report Copied only after a supported
transport acknowledges the write. This increment selects no native clipboard,
OSC 52, polling or remote-to-local transport. Native terminal mouse selection
cannot be portably detected and can include presentation artifacts.

An immutable selection can pin bounded inspected content independently of newer
output. The caller owns retention/eviction: explicitly invalidate an unavailable
snapshot with a reason instead of rebinding offsets or copying newer content.
The [accepted copy contract](../design/cereja-ui-ux.md#accepted-clean-copy-contract-2026-10-09)
owns the eventual application behavior and clipboard acceptance.

## TextInput

`TextInput(identity, text='', max_bytes=65536)` owns content, caret, textual
anchor and horizontal viewport. Mutation and painting require the creating UI
thread. `content`, `text`, `caret` and `selection` are read-only properties;
a content edit increments the revision. Old immutable selections retain their
snapshot. Rejected edits preserve all state and return a reason.

The configurable default 64 KiB bounds canonical UTF-8 input after sanitization,
including expanded visible controls. Raw-length and repeat checks bound
preprocessing. It is independent of the transport's paste bound, scheduling
payload limits and Ledger retention candidates. It is not a Python-heap bound.

| API / key | Behavior |
| --- | --- |
| `move(offset, extend=False)` | Set a canonical grapheme boundary; Shift-style extension retains its original anchor. |
| `set_selection(anchor, caret)` | Validate/set a logical textual range on the current revision. |
| `insert(text)` | Replace the range or insert at caret, sanitize and resegment adjoining clusters. Empty input preserves state. Suggestions use this same API, with zero execution. |
| `handle(PasteEvent(text))` | Atomic literal insertion; embedded LF/slash never submit. |
| Left/Right | Whole graphemes; without Shift collapse a range toward that edge, then apply repeats. |
| Home/End | Beginning/end of the whole draft; Shift extends. |
| Backspace/Delete | Delete the range or whole adjacent grapheme(s). |
| Ctrl+A | Select the whole canonical draft. |
| Ctrl+C | Copy request for this surface's nonempty text selection; otherwise exit intent. |
| Enter | Submit intent only. Parsing, validation and execution remain caller-owned. |
| Printable text, including q | Insert text. Native printable Ctrl+Alt/Shift+Ctrl+Alt (AltGr) stays text. |
| Other modified/control keys, Tab, F1, arrows local to other controls | `unhandled`; caller routes traversal, discovery, help and navigation. |

Actions are `changed`, `handled`, `rejected`, `unhandled`, `submit`, `copy`
or `exit`. They do not execute application work. Repeats are applied atomically
without a loop proportional to an untrusted repeat count.

`paint(frame, rect, focused=False, clip=None, tab_size=4)` clears and paints
only the first clipped row. It returns `InputView(viewport, cursor, line_start)`.
The caret's logical line scrolls horizontally by whole graphemes/tab boundaries;
LF remains in canonical text, with no visual wrapping. Two ASCII marker cells
distinguish focus `>` from textual selection `*`; selected visible spans use
reverse video without requiring color. Width fallback follows the frame's
`TextPolicy`. A partially visible wide glyph is blanked by existing buffer
clipping; a one-cell text window still reveals the caret. Hidden/empty windows
preserve edit state and hide the terminal cursor.

The caller reserves terminal geometry and decoration outside copy payloads,
passes the returned cursor to the renderer/scheduler, and requests frames when
state changes. No caret blinking, animation, redraw loop or history is added.
Use [layout](ui-layout.md) and [scheduling](ui-scheduling.md) without changing
their clipping, output transactions or 30/4 Hz limits.

## Focus scopes

`FocusTarget(identity, enabled=True, visible=True)` names a control.
`FocusScope(identity, targets)` freezes unique targets in explicit traversal
order. `FocusManager(scope, max_depth=16)` initially focuses its first enabled,
visible target; an empty scope has no focused target. All mutation is UI-owned.

- `focus(identity)` requires an eligible target in the active scope.
- `traverse(backward=False)` wraps forward/backward through eligible targets.
- `push(scope, initial=None)` contains focus within the new top scope.
- `pop()` restores the previous scope's stable focus identity. The base cannot
  be popped. The depth limit includes the base.
- `update(scope)` refreshes any active/covered scope. Removed/disabled/hidden
  focus chooses the next surviving eligible target in the old order, then the
  previous, then the first new target or none. Covered updates never steal top focus.
- `scope`/`focused` expose the current owner.
  `focus_markers(focused, selected)` yields two independent ASCII markers.

The manager retains identity only. Composer content, form values, selected
row/node, result scroll and inspected revision belong to their separate owners.
Opening/closing help therefore does not copy or overwrite edit state. Actual
suggestion lists/forms/confirmation overlays are #309, collections #310, and
Ledger/application key routing #313.

## Runnable example and measurement

```python
from cereja.ui.editing import TextInput
from cereja.ui.events import KeyEvent, PasteEvent

draft = TextInput('composer')
draft.handle(PasteEvent('  /example\n\tvalue  '))  # literal editing, no execution
draft.handle(KeyEvent('a', modifiers=frozenset({'ctrl'})))
request = draft.handle(KeyEvent('c', modifiers=frozenset({'ctrl'})))
assert request.kind == 'copy'
assert request.selection.text == '  /example\n\tvalue  '
# With no clipboard transport, show Copy unavailable and retain selection.
assert draft.selection == request.selection
```

A bounded synthetic example exercises graphemes, copy requests, contained help
and return, insertion, fixed composer and the three selected sizes:

```text
python -B -S benchmarks/ui_editing.py --demo --ascii --size 40x12
python -B -S benchmarks/ui_editing.py --samples 31 --warmup 3 --memory-samples 3 --output report.json
python -B -S -m unittest tests.test_ui_editing tests.test_ui_imports
```

[Raw frozen Windows/Python 3.14 baseline](../../benchmarks/ui_editing_samples/baseline-windows-py314.json)
contains 31 samples per workload/size, three warmups and three separate untimed
tracemalloc samples. One event arrives immediately after a primed frame.
The window measures VirtualBackend injection, editing, layout, scheduling and
renderer acknowledgement/flush in memory, using real monotonic scheduler delay
and sleep. The unchanged 30 Hz ceiling contributes to latency. Handler delay,
handler-to-request work, scheduler sleep, median/p95/MAD and source fingerprints
are separate. Long input is stress evidence; no performance threshold or #304
budget is changed.

Requirement tests cover Unicode edits, joining clusters, bounded repeats/paste,
canonical range copying, version pinning, ownership, narrow/ancestor clipping,
focus restoration/removal, no-color/ASCII/reduced-motion and zero idle redraw.
The harness is not a human keyboard, terminal presentation, clipboard, emulator,
SSH/ConPTY or Ledger measurement. Existing real native transport checks do not
establish editor usability. Real clipboard/participant/accessibility acceptance
remains under #321.

Unsupported: IME/composition-specific events, word-level editing/undo, full bidi
shaping, multiline visual editing/wrapping and mouse/native-terminal selection.
Unsupported terminal/font cluster behavior follows the existing Unicode fallback.
