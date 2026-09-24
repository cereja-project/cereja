# Cereja shell: selected Ledger specification

Status: the user selected A, Ledger. The visual-alternative gate is satisfied. This specification supports implementation planning; it is not a production implementation or evidence of terminal/runtime usability. The current product direction is an interactive Cereja shell/workbench with a persistent bottom command composer and rich inline content. The old dashboard-first references remain functional evidence only. Neither alternative is a chatbot, agent, natural-language command interpreter, full filesystem browser or copied assistant interface.

## Shared product grammar

The composer is the persistent interaction anchor. `/system`, `/tree`, `/context`, `/examples` and `/help` discover or navigate Cereja capabilities. Exact parameter spelling is proposed interaction syntax until mapped to the actual command adapters. Existing CLI equivalence must be explained accurately rather than claiming the shell and CLI parsers are identical. Archive and Download entry names remain proposed `/compress` and `/download`, subject to review; their selected functional scope remains unchanged.

Typing `/` opens a keyboard-selectable command list immediately above the composer. Typing more filters by command prefix in the prototype; description search is a later discoverability option. Choosing a suggestion inserts the command and closes the suggestion list; it never runs work. Context help describes required parameters, defaults and effects for the current command. Parameter overlays can gather paths, explicit roots, URL or destination without inventing a directory picker. Archive files and directories are both accepted v1 scope and require their own safety validation.

No message bubbles, assistant avatar, model selector, conversational response animation, generated recommendations or natural-language intent guessing. A submitted operation has a command label, typed parameters, lifecycle state and domain result. Examples are synthetic and explicitly marked. A command is not an exchange with another speaker.

## Selected A: Ledger

Composition: a continuous reading column of rich command/result sections above the composer, separated by whitespace and a short left stem. No outer boxes around ordinary results. The cherry stem marks only the active result heading and the composer focus marker. A result reads top to bottom: command name, compact state, important result, supporting detail. V1 retains ordered ephemeral result blocks, with the newest active block nearest the bottom composer and earlier blocks selectable above it. The composer draft is independent of the result sequence. There is no disk history, retained sensitive field or queued work. Retention is bounded by the resource policy below, preserving Ledger's sequential reading model.

The HTML prototype reserves three top rows (identity, rule and clearance), 33 result rows and four bottom rows (composer rule, input, hint and status) at 120x40. Content begins at column 3; at most 88 columns are used for prose, while tables may use the remaining width. `/system` uses full-width section headings followed by aligned label/value rows. A selected result has a `>` marker and a brighter heading, not a surrounding frame.

At 80x24: three top rows, 17 result rows and four bottom rows. At 40x12: three top rows, five result rows and four bottom rows. Composer outer width is viewport minus two cells. Long input scrolls horizontally by grapheme; the insertion point stays visible. Long results wrap or scroll in their own surface without displacing the composer.

The empty shell shows a short purpose line and three command examples aligned with the reading column. It avoids a dashboard grid. Initial focus is in the composer. Hierarchy is deliberately sparse: the bottom accent locates action, the current result heading locates output, subdued separators distinguish supporting metadata.

## Non-selected B: Workbench (comparison record)

Composition: one replaceable, framed inspection canvas above a recessed bottom composer. A narrow status strip is part of the result frame, keeping command identity and outcome attached to the content. The composer has a three-sided frame and a labelled command notch; its shape remains recognizable in monochrome. The active operation replaces the current canvas after validation; inputs and selected result state remain available for Edit/Back, but there is no accumulated transcript or implied history.

The HTML prototype reserves four top rows (frame/title, context, rule and clearance), 32 result rows and four bottom dock rows at 120x40. A pager uses a separately reserved result row when content overflows, never overwrites a value. `/system` uses two columns of panels (system/OS on the left, CPU/memory/GPU on the right) with explicit unavailable values. Panel headings are short and text remains one terminal cell scale. The single visual anchor remains the bottom composer when editing, or the active result title when inspecting; all panels do not receive equal accent treatment.

At 80x24: four top rows, 16 result rows and four dock rows. At 40x12: four top rows, four result rows and four dock rows; overflowing content reserves one of those result rows for paging. The two-column panel layout collapses to one scrollable section list. The currently selected section's title remains visible. No miniaturized typography or hidden required controls.

The empty canvas shows one concise purpose statement, current environment availability and the instruction `Type / to explore Cereja`. It is a working surface, not a dashboard or conversational welcome card. Contextual options appear in overlays, not a permanently competing sidebar.

## Recorded alternative differences

| Property | A: Ledger | B: Workbench |
| --- | --- | --- |
| Result organization | Ordered inline result blocks with bounded ephemeral session retention | One current inspection canvas, replaced deliberately |
| Spatial hierarchy | Open column, left stem, minimal separators | Framed workspace, integrated status strip, modular panels |
| System reading | Stacked section headings and aligned rows | Wide two-column panels; narrow section list |
| Composer signature | Open field under one rule with cherry prompt stem | Recessed three-sided field with labelled notch |
| Navigation consequence | Select earlier result blocks and scroll their content; follow newest only on request | Edit/Back restores current-operation inputs; no transcript |
| Cost to validate | Scroll anchoring, section hierarchy and output provenance | Replacement, restoration and panel focus order |

Both use the same cherry accent and command grammar. Preference should therefore reflect composition, interaction and reading cost, not only color.

## Keyboard, focus and overlays

| Action | Proposed key and behavior |
| --- | --- |
| Open discovery | Type `/` in composer. Suggestions open above it, maximum seven rows (heading, five items, hint) at wide sizes and three at 40x12. |
| Suggestion selection | Up/Down changes selected suggestion; Enter accepts it without executing. Selection and focus have distinct text markers. |
| Complete | Tab accepts an unambiguous suggestion while discovery is open; otherwise cycles enabled visible controls. Shift+Tab cycles backward. |
| Submit | Enter with discovery closed validates a complete command. Required field overlays or effects review occur before execution. |
| Composer/result focus | Tab cycles composer and result region when no discovery overlay is open. In the browser review prototype, F6 returns to external review controls so keyboard users are not trapped; that escape is not a product command. |
| Context help | `/help` opens a contextual overlay; current command context is preserved. F1 remains an optional product binding, not implemented by this prototype. Help closes back to the exact caret/selection. |
| Escape | Close the top overlay, then dismiss discovery. It does not cancel work or erase the whole command implicitly. |
| Result movement | The prototype implements arrows and Enter for Tree/Context/Examples and PageUp/PageDown for content scrolling. Full Home/End and grapheme editing remain toolkit acceptance work; the browser input is not proof of those contracts. |
| Exit | Ctrl+C requests application exit through the operation-aware lifecycle. Never promise it safely cancels unsupported work. |

The composer owns normal typing even when result content is visible; typing while a result control has focus must not secretly rewrite it. A visible focus marker and contextual hint name the current target. Bracketed paste inserts bounded text without dispatching slash commands. Newline-containing paste requires explicit submission after review. Control text is sanitized before measurement and output.

Overlays open directly above the composer and never cover its active line. Wide overlays are limited to the composer width and available result height. Small screens use a single scrolling overlay with a fixed title/action row; overlay focus is contained until close, then restored. Only one topmost overlay captures keys. Confirmation overlays state exact targets and effects, default to keep/back, and bind consent to the validated target. Suggestions use no execution-style confirmation language.

During one active operation, the composer remains editable for discovery/help/navigation, but another execution is refused visibly with `Working: <operation>` and Return to current. Nothing queues or starts later. No Cancel appears without proven safe cooperative interruption. Completion does not steal composer focus or discard an unfinished command.

## Required state comparison set

The comparison record used matching fixture states. Implementation planning now targets Ledger at 120x40, 80x24 and 40x12; Workbench is not a second implementation requirement. The initial, slash discovery and `/system` states are essential to assessing the shell grammar, not optional decorative screens.

| State | A: Ledger treatment | B: Workbench treatment | Truth condition |
| --- | --- | --- | --- |
| Initial | Purpose and three command examples in open column; composer focused | Empty framed surface and one exploration instruction; composer focused | No unrequested collection or implied agent response |
| Slash discovery | Borderless compact suggestion shelf above rule | Framed command overlay aligned with composer notch | Accept inserts, second explicit submission runs |
| `/system` | Stacked OS/CPU/memory/GPU label-value sections | Two-column wide panels, one-column small sections | Actual snapshot or explicit fixture; Unavailable stays visible |
| Determinate | Inline byte counts and thin cell bar | Progress module inside canvas with status strip | Actual bytes and reliable total; fixture values labelled |
| Indeterminate | Static operation label with optional small spinner | Known section placeholders with optional restrained highlight sweep | Known activity only; no fake percentage, speed, ETA or Cancel |
| Error | Error heading and actionable detail under command label | Error state attached to current canvas; Edit/Retry actions | Partial side effects explicit; no automatic retry |
| Empty | No results within bounds plus query/root context | Empty result panel with Edit action | Empty is not failure and does not prove global absence |
| Small | Results wrap/scroll above fixed composer | Panels collapse above fixed composer | No essential action disappears; below 40x12 recovery preserves state |

The comparison uses the captured 768/1536-byte event snapshot (50%) and the same count with unknown total from the local loopback probe. It is a fixed design snapshot, not a live transfer. Speed and ETA are omitted because the probe contains no timestamp samples. Earlier 524288/1048576 values were fictional fixtures, not observed measurements. System skeletons only reserve known section slots; shimmer is a comparative optional effect, not a default claim of usefulness. A static label is the no-motion, no-color and low-bandwidth equivalent.

## Selected Ledger state and navigation contract

The shell has three independent state owners: composer draft (text, caret and selection), result ledger (ordered block identities, safe parameters, typed outcomes, selected block/item and per-block scroll anchors), and transient overlay (kind, invoking focus and temporary form values). No domain module owns widget state. Close/resize/help preserve the draft. Re-render and background completion never overwrite typing or move focus. Explicit Edit parameters replaces the draft only after handling an existing nonempty draft without silent loss.

Tab/Shift+Tab traverse enabled visible controls in the active surface. Composer and selected result block are distinct focus regions. A block header is selectable; Left/Right on that header selects the previous/next retained block, while control-local arrows keep their normal meaning. PageUp/PageDown scroll the selected block viewport, not the composer or another block. Lists/trees preserve selected stable identity when focus leaves. Expanding a tree or returning from a snippet restores the same selected item and viewport anchor. When an item disappears, select the next surviving item, then previous, then the empty-state action. Scroll clamps after resize while keeping selection visible. A pager consumes its own row and never overwrites content. At 40x12 the bottom four-row composer dock stays fixed; results and overlays scroll above it. Below minimum size preserve state and offer resize or job-aware exit.

Slash discovery uses prefix matching, stable ordering and an explicit no-match state. Enter on a highlighted suggestion inserts its command; Enter again with discovery closed submits validation. `/help` and parameter help are overlays and leave the current result intact. Selecting a command without required values opens its parameter form rather than reporting a meaningless execution error. Forms retain valid values when one field fails. Bare text is not an AI request and does not execute shell code; show a concise slash-command hint.

For v1, one active background operation of any type owns execution. Another run is refused with the current operation named and Return to current, without queueing. Navigation/discovery remain usable. Completion updates the current operation in place and preserves composer focus. Exit during unsupported cancellation keeps the active-job state explicit; restoring terminal modes never implies an operation was rolled back. Cancellation is exposed only when safe cooperative interruption is proven.

## Bounded ephemeral Ledger retention

Proposed initial resource policy: retain up to 20 completed result summaries plus the one active block, with at most 2 MiB of canonical UTF-8 sanitized retained payload across blocks. The count and byte cap are experimental engineering budgets, not measured optima or a claimed Python heap ceiling. Store the canonical capped payload rather than an uncapped duplicate model; account bounded view models separately during memory benchmarks. Tree/search traversal, result limits, log retention and event queues retain independent bounds.

On appending a new operation, evict the oldest completed blocks until both caps fit. Never evict the active block. If a block's detailed payload cannot fit, retain its bounded identity/status summary and explicit truncated/omitted counts. Active streams use bounded windows; once full they discard oldest detail and count omissions while keeping lifecycle identity/outcome. On completion apply the same completed-block caps. No secret/sensitive fields enter retained summaries, including diagnostic payloads; sanitize before byte accounting. Nothing writes to disk or restores results across sessions.

New blocks appear chronologically at the bottom of the result sequence. Auto-scroll happens only when the user was already following latest. If inspecting an earlier block, retain its selection and viewport anchor, show a `New result` notice and offer `Latest`. Completion updates its own block without changing composer caret, result focus or scroll. If the selected completed block is evicted, choose the nearest surviving completed block, then active block, and show an eviction notice. An explicit Latest action reenables follow-latest. Resize preserves block identity and clamps only its scroll bounds.

Verify count cap, canonical byte cap, oversized single result, active stream pressure, selected-block eviction, latest-follow behavior and no sensitive/disk retention with deterministic tests. Benchmark actual peak memory before tightening or relaxing these proposed values. The existing comparison prototype's current-only behavior is a limitation to correct, not the selected Ledger contract.

## Selected capability flows and inline outcomes

| Flow ID | Composer and parameter flow | Inline result and recovery |
| --- | --- | --- |
| L1 System | `/system` -> accept -> submit basic collection. Explicit Refresh uses the same basic/sensitive-off scope; full detail is a separate deliberate request. | Section headings and key-value/table rows; per-field Unavailable; known-activity loading placeholders; prior snapshot remains labelled during refresh. Failure preserves old snapshot and offers retry. |
| L2 Tree | `/tree` -> Path/Depth overlay -> validate explicit path -> Load. | Structured hierarchy, expand/collapse, selected full sanitized path, bounded visible rows, ignore policy, no symlink traversal. Long labels truncate with details available. No filesystem edit/open/delete browser. |
| L3 Context | `/context` -> explicit roots, query, extensions and bounds -> validate -> Search. | Bounded results and skipped reasons; matched text markers, selected snippet and Back preserve result identity. Empty states say within limits; error retains inputs. Cache off. No Cancel without safe service support. |
| L4 Archives | `/compress` -> mode Compress/Decompress -> Source/Destination -> validate effects -> exact-target confirmation only if supported overwrite is requested -> execute. | Running with honest indeterminate activity, bounded logs and real final duration/result/error. Existing target refused by default. Partial-output state precedes explicit retry. Files and directories are accepted v1 scope. Directory collection and extraction each require explicit destination rules, traversal/link defenses, resource bounds, failure behavior and their own acceptance cases; existing API behavior is not assumed safe merely because the mode exists. |
| L5 Download | `/download` -> URL/Destination overlay -> validate supported scheme and exact destination -> effect review/required confirmation -> execute. | Actual TransferProgress byte events; total when reliable; sample-derived speed only when available; otherwise indeterminate. Network errors and partial-target state are explicit. No assumed resume or safe cancellation. |
| L6 Examples/help | `/examples` -> selected synthetic example, or `/help` overlay. | Demonstrate table, input, selection, progress/log states without affecting real files/network. Help restores exact composer caret and result focus. |

The slash command opens one deterministic capability flow; it does not pass arbitrary text to a shell. UI validators may give early feedback, but domain validation remains authoritative. Overwrite consent binds to the final path and effect; a changed target invalidates it. Validate and review before starting any side effect, then recheck race-sensitive target state without claiming atomic safety from a modal alone.

## Flow-to-component planning traceability

| Planning slice | Required reusable toolkit contracts | Application-owned behavior and evidence |
| --- | --- | --- |
| Shell/discovery | Input, list selection, overlay, focus manager, Row/Column, clipping | Slash registry, prefix suggestions, insert-then-submit, bounded ordered block state; replay draft preservation, eviction and follow-latest traces |
| Parameter/review overlays | Form inputs, validation labels, modal focus containment, buttons | Typed adapter parameters and exact effects/targets; prove no execution on selection or rejected confirmation |
| L1 System | Text, Panel/group, Table/key-value, StatusBar, scroll, timers | Typed hardware data, refresh and missing fields; responsive snapshots and real service error path |
| L2 Tree | TreeView, virtualized scroll, text metrics, selection | Structured nodes, explicit path/depth and ignores; large/deep/Unicode/resize fixtures |
| L3 Context | Form, ListView, safe highlighted text, scroll/detail surface | Roots/bounds/results/skipped reasons; empty/error/snippet-return fixtures |
| L4 Archives | Buttons, confirmation, indeterminate indicator, LogView | Mode dispatch, existing-target refusal, side effects and final result; file and nested-directory round trips plus traversal/link/resource/partial-failure tests; domain gaps require safety work before acceptance |
| L5 Download | ProgressBar, status, timers, background event posting | Actual byte/total samples, URL/destination and partial errors; known/unknown total local fixture transfer |
| Current background operation | Worker/event wakeup, lifecycle state, bounded logs, shutdown | One-operation policy, no pending start, capability-accurate cancellation; prove input responsiveness and truthful outcomes |
| L6 Examples/accessibility | Public widget API, shared motion policy, no-color text styles | Synthetic versus real provenance, contextual help, motion off/ASCII, keyboard state restoration |

Toolkit modules own input normalization, focus, layout, cell metrics, safe rendering, timers and generic widget behavior. The application owns slash command names, capability eligibility, domain adapters, operation effects, limits and result schemas. Domain services never import `cereja.ui`; reusable callback/cancellation work remains optional separate evidence-driven instrumentation. A reference toolkit example can justify a component without claiming a production service supports its features.

## Color, typography and motion

Restrained cherry identity: Ledger dark background `#18141A`, foreground `#E9E1E5`, muted `#AA9DA5`, cherry/focus `#FF89AA`. Workbench light background `#F2EEE6`, foreground `#30252B`, muted `#6F6065`, cherry/focus `#9C264C`. Cherry belongs to the composer marker, selected command and one active heading, not every border. Error and success include words and distinct ASCII markers; cherry alone never means error.

Use terminal-owned monospace and one cell-based text scale. Hierarchy comes from position, weight where available, capitalization sparingly, whitespace and border geometry. No giant font, browser-style size ladder, letterspacing or forced six-percent margin. One-cell outer clearance and one/two-cell internal spacing are proportionate to terminal constraints. Keep readable prose measures near 45-75 cells where available; narrower terminals wrap at semantic boundaries using shared Unicode metrics. Paths are not destructively word-wrapped when that obscures identity: show full selected value in details.

Overall render ceilings remain 30 Hz local and 4 Hz low-bandwidth; indicator ceilings 8/2 Hz. Idle has no periodic redraw. Motion off removes visual timer animation, retaining meaningful domain updates. Hidden/disposed indicators remove deadlines. No animated response typing, sliding screen transitions, pulse-only status or fake activity. Optional shimmer uses common timers and clipped dirty regions and must demonstrate benefit over a static placeholder before adoption.

## DesignSignalPacket for terminal review

`composition_state`: canvas is integer cells; one persistent bottom composer anchor; result area above; overlays never cover input line; A uses an open reading column, B uses framed modular canvas; clearance is one cell, not percentage margins; intended negative space separates result from action without reducing the 40x12 usable region.

`typography_state`: terminal monospace, one-cell scale; primary headings differentiated by position and optional bold; body and hints remain readable in monochrome; exact copy locks are `/system`, `/tree`, `/context`, `/examples`, `/help`, `Working`, `Unavailable`, `Error`, and `Type / to explore Cereja`.

The composition and typography skills inform hierarchy, protected text regions, grayscale review and semantic line breaking. Their poster/font-size defaults are intentionally adapted to terminal cells. Verify actual contrast in each chosen host/palette; token values alone do not prove accessibility.

## Review gates

Compare both at identical dimensions and content in color and monochrome, with motion off first. Evaluate where users first look, whether they locate the composer, discover slash commands, distinguish selection from execution, inspect System, recover from error, and return to unfinished input without state loss. Record observations instead of claiming usability from a screenshot.

Structural preflight: total allocated rows equal viewport height; composer always visible; overlays have bounded scroll; required actions reachable at 40x12; one active operation; no color-only meaning; no fabricated service telemetry. Browser mockups can validate composition and copy, not terminal Unicode width, event handling, host restoration or assistive-technology support.

Ledger is the user-selected visual direction and can drive concrete high-level planning tasks. Files and directories are both accepted v1 scope; directory-specific safety stages and acceptance criteria remain required. Selection does not establish runtime, real-terminal, accessibility or usability validation.

## Ledger sequential-result cell specimen

Static 80x24 cell specimen for the selected retention contract. Both blocks are
fixtures, not live hardware/network output. This supplements the comparison HTML,
which still replaces the current result and does not implement session retention.
The System summary is completed; Download is the sole active operation. The user
is inspecting block 1, so arriving progress does not move selection or scroll.
`Latest` explicitly returns to follow-latest mode. Headers preserve command identity,
state and position; result payloads remain subject to the documented bounded policy.

```text
CEREJA                                                SESSION 2 blocks | FIXTURE
-------------------------------------------------------------------------------

> 01 /system                           SUCCESS | snapshot fixture
  OS              Example OS
  Python          3.x
  Memory          Unavailable
  [Details]       Completed result retained temporarily

  02 /download                         WORKING | captured event fixture
  artifact.bin
  [##########..........] 50%           768 / 1536 bytes
  Speed unavailable                    Cancel unavailable

  Inspecting result 1 of 2              [Latest: result 2]
  Header focus: Left/Right selects      PgUp/PgDn: selected result




-------------------------------------------------------------------------------
  cj > /help
  Enter: help   Tab: results            Draft stays independent
  1 active operation                   1 completed + 1 active | no queue
```

At 40x12, the selected block occupies the bounded content viewport; adjacent
blocks collapse to command/state headers with a result-position indicator.
Block selection and the Latest affordance remain keyboard reachable. The composer
keeps its four rows, the result pager keeps its own row, and no value is overwritten.
Eviction announces `Oldest completed result removed from this session` with the
remaining count, without exposing dropped content or moving composer focus.
