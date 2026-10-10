# Suggestions, forms and review overlays

UI-10 / [#309](https://github.com/cereja-project/cereja/issues/309) adds opt-in
`cereja.ui.overlays`, using [editing/focus](ui-editing.md), [layout](ui-layout.md)
and the existing Unicode/cell policy. Python 3.11+, standard library only.
Imports acquire no terminal and start no workers/timers. Every operation returns
an intent; there is no parser, shell, filesystem/network effect or clipboard.

## Suggestions

`Suggestion(identity, label, insertion, description='')` freezes caller-supplied
safe text. Labels are single-line; insertion is literal canonical text.
`Suggestions(identity, composer, suggestions, start=0)` filters by the exact,
case-sensitive insertion prefix at `start..composer.caret`, in catalogue order.
It neither creates an application catalogue nor performs description search.

- `matches` and `selected` expose the current filtered tuple/stable identity.
  `refresh()` explicitly reconciles external draft/caret changes.
- Up/Down move the highlighted item (navigation, not textual selection).
- Enter/forward Tab replace that logical prefix, preserve its suffix, set the
  inserted caret and close the shelf. One event, including its repeat count,
  yields only `inserted`. Only a later key routed to the composer yields
  `submit`; neither intent executes.
- Escape closes with the draft/caret/range intact. No match consumes Enter/Tab
  and leaves the draft/shelf unchanged with a reason.
- Normal edits/paste use TextInput and update filtering. External changes make
  the next acceptance reject/reconcile, requiring review again.
- An oversized insertion retains the original draft/caret/selection and shelf.
  Ctrl+C uses the composer's active textual range, never the highlighted row.

The catalogue is limited to 256 items and 64 KiB aggregate safe UTF-8 metadata.
The whole catalogue is rejected when over limit; there is no silent truncation
or hidden lookup. The existing composer input bound remains independent.

## Parameter forms

`FormField(identity, label, value='', required=False, help='', enabled=True,
validator=None)` is immutable. A validator receives safe canonical text and
returns None or a nonempty error string. It must not perform domain work.
`ParameterForm(identity, title, fields, primary='Review', max_input_bytes=65536)`
retains reusable TextInputs, explicit labels/defaults/bounds and field errors.

Required labels show `*`; canonical UTF-8 byte bounds remain visible. Disabled
fields are displayed but skipped in traversal, validation and submitted values.
The form admits 32 fields and 64 KiB initial aggregate metadata. Each editor has
the configurable TextInput bound (64 KiB by default); this bounds growth by
field count, not Python heap usage or Ledger result retention.

`input(identity)` exposes a field's editor; `values` returns immutable enabled
identity/value pairs. `snapshot` includes every field's content revision/text.
`fields` and `max_input_bytes` are read-only.

`validate()` performs explicit, synchronous validation and returns `submit`
with values or `rejected`. It retains good values, reports safe errors and never
starts a job. A callback changing the active focus scope also rejects submission.
`validated` is true only for the exact checked snapshot. Any edit,
even a later reversal, invalidates it. Mutating validators reject with Changed
during validation; callback exceptions/invalid error values become Validation
unavailable, without leaking exception diagnostics. Callbacks are not preempted.

Within the stack, Enter validates the focused field/primary action; Back/Escape
keeps values; failed validation focuses/reveals the first invalid field.
Tab/Shift+Tab wrap enabled fields -> primary -> Back -> Help. F1/Help saves that
scope and opens bounded contextual help (default, bound and caller description).
Return restores the same field's content, caret/range and focus. Reopening the
same form retains its values; it does not replace the composer draft.

Callers redact secrets and sensitive URL diagnostics before widget/validator
text. UI validation provides early feedback; domain validation remains separate.

## Exact-target review

`ReviewTarget(action, source, destination, output_kind, effects, policy, version,
permitted=False)` freezes the complete caller-normalized, safe target tuple.
The toolkit does not guess paths, normalize a filesystem destination, inspect
target existence, choose overwrite policy or establish safe replacement.
All required strings must be nonempty and already safe. `plain_text` is a stable
canonical representation with JSON-quoted values, independent of cells, padding,
markers or soft wraps. Literal LF/TAB/quotes/backslashes cannot impersonate another
field; decoding each quoted value recovers its exact original string, including
intentional whitespace. Free help/source text retains the existing raw canonical
LF/TAB copy contract.

`permitted` defaults False. True is an explicit caller assertion that its policy
supports presenting Run, not domain authorization or a publication guarantee.
`Confirmation(identity, target, form=None)` binds that tuple and, when present,
the exact validated form snapshot. Unvalidated forms cannot open review.

- Default focus is always Back. Enter activates only the focused action.
- Run stays disabled until the current target is supplied to painting and the
  full retained details can be inspected in usable geometry. Unsupported policy,
  unavailable target or hidden geometry disables it.
- All tuple changes (including policy/state/version) and all form edits invalidate
  consent. Changed review returns to Back and requires explicit `review(target)`
  after revalidation. Editing then reverting does not reuse old consent.
- Explicit Run returns `confirmed` with the exact immutable tuple, closes the
  overlay and restores invoking focus. It starts zero operations.
- `authorization(current)` is a UI-owned freshness check returning that tuple
  or None. It is not durable permission for a worker. The future domain consumer
  must recheck race-sensitive state and its own atomic safety before effects or
  publication. Changing metadata, closing/reopening or hidden detail never
  authorizes a different target.
- `target`, `form`, `details` and `stale` are read-only; explicit review creates
  a new details revision. Pinned selections keep their old canonical snapshot.

The destination identity and actions stay in the fixed header/footer. Long
header text has explicit visual ellipsis; the entire exact value remains in the
paged canonical body. Up/Down, PageUp/PageDown (one overlap row), Home/End inspect
all source/effect/policy/version details. Help also exposes the retained tuple.
At 40x12, Back/Run/Help and the pager remain above the four-row composer dock.
Below usable geometry Run is unavailable; state survives resize.

## Help, scope and rendering

`HelpOverlay(identity, title, text, revision=0)` retains up to 64 KiB safe canonical
text. Content is read-only; `select(anchor, caret)` validates logical grapheme
offsets, Ctrl+A selects all, and Ctrl+C returns a copy request. Tabs, blank lines,
indentation, intentional spaces and source Unicode survive wrapping/ASCII
fallback. There is no clipboard transport or Copied acknowledgement. Empty or
inactive selections do not intercept Ctrl+C from another surface.

`OverlayStack(focus)` uses the existing FocusManager and its depth bound.
`open(overlay)`, `close()`, `top`, `handle(event, current_target=None)` and
`paint(frame, bounds, composer, current_target=None)` support these four overlay
types. Only the active top scope handles keys. A foreign focus scope covers it
without editing hidden inputs; close refuses to pop foreign focus. Failed help
construction/depth is a visible rejection preserving the invoking state.

`OverlayAction` carries kind/reason, immutable values, optional textual selection
or exact target. Kinds are editing intents plus inserted/back/help/confirmed.
Copy failure/unavailability must retain state and never fall through to exit.
Exit remains an application intent, with later job-aware handling.

`overlay_bounds(bounds, composer, width=75, height=12)` anchors above the composer,
within drawable bounds and composer width. `paint` returns
`OverlayView(rect, viewport, cursor)`; only the top overlay paints. Forms use
existing viewports to reveal the focused label/input/error. No timer, animation,
queue, disk history or domain state is introduced. Callers paint the persistent
composer, reserve the final terminal column and schedule frames/cursor normally.
For a suggestion shelf the composer owns its visible caret; form painting returns
the field caret. No-color, ASCII and reduced motion keep their existing contracts.

## Runnable bounded examples and baseline

```python
from cereja.ui.editing import TextInput
from cereja.ui.events import KeyEvent
from cereja.ui.focus import FocusManager, FocusScope, FocusTarget
from cereja.ui.overlays import Suggestion, Suggestions, OverlayStack

draft = TextInput('composer', '/sy')
focus = FocusManager(FocusScope('base', (FocusTarget('composer'),)))
stack = OverlayStack(focus)
stack.open(Suggestions('slash', draft, (Suggestion('system', '/system', '/system '),)))
assert stack.handle(KeyEvent('enter')).kind == 'inserted'
assert draft.text == '/system '
assert stack.top is None
assert draft.handle(KeyEvent('enter')).kind == 'submit'  # still no execution
```

```text
python -B -S benchmarks/ui_overlays.py --demo --ascii --state form --size 40x12
python -B -S benchmarks/ui_overlays.py --demo --ascii --state review --size 40x12
python -B -S benchmarks/ui_overlays.py --demo --ascii --state stale --size 40x12
python -B -S benchmarks/ui_overlays.py --samples 31 --warmup 3 --memory-samples 3 --output report.json
python -B -S -m unittest tests.test_ui_overlays
```

[Tests](../../tests/test_ui_overlays.py) replay first/second Enter, Tab/Escape,
filter/no-match, safe paste/copy, scope containment/return/failure, validation
mutation, stale target/form consent, exact-target paging and all five synthetic
views at 120x40, 80x24 and 40x12. Existing native transport tests are separate
from these virtual editor/widget scenarios.

[Raw baseline](../../benchmarks/ui_overlays_samples/baseline-windows-py314.json):
31 samples per workload/size, three warmups and three separate untimed traced
memory samples. It measures a keyboard event through models/layout/painting into
a cell buffer. Filtering 256 items and three-field validation are toolkit workloads;
a 512-CJK target is wrapping/paging stress. Source fingerprints, median/p95/MAD
and memory boundaries are explicit. This excludes scheduler pacing, renderer
acknowledgement, terminal presentation, human input, clipboard, domain/application
and RSS. No #304 budget or Ledger retention candidate is changed.

Real participant, terminal/emulator/SSH/ConPTY, clipboard, accessibility/usability
and full application acceptance remain pending. Actual Ledger catalogue/parser,
domain forms/operations and official `cereja ui` remain later increments.
