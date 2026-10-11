# Cereja UI Ledger UX specification and review boundaries

Status: the user selected five initial capability areas for concrete flow and wireframe elaboration: System Information, Repository/Directory Tree, Context Search, Compress/Decompress, and Download. The user selected Ledger as the visual language. The specification below enables concrete planning including files and directories with dedicated archive safety stages; implementation and observed usability are not established. No integration is implemented by these artifacts.

## Superseding interaction direction

The latest user direction replaces dashboard-first navigation with an interactive Cereja shell/workbench. A persistent command composer sits at the bottom; rich inline results occupy the area above it. Slash discovery and navigation include `/system`, `/tree`, `/context`, `/examples` and `/help`, with autocomplete, contextual help and keyboard overlays. This is a deterministic interface to Cereja capabilities, not a chatbot, agent or natural-language execution assistant.

The five selected capability areas and their safety/data boundaries below remain functional evidence. Their earlier dashboard-first navigation and the 73-screen HTML are historical proposals, not the current interaction design. See the [selected Ledger specification](cereja-ui-visual-language.md) for the current layout, state model, flows and component traceability. The user selected A, Ledger; the visual-alternative gate is satisfied and high-level planning can follow that specification. B is preserved only as a non-selected comparison record. Files and directories are both explicitly accepted for v1; their safe handling requires dedicated stages and criteria.

Current flow proposal: focus bottom composer -> type slash prefix -> choose capability -> complete explicit parameters using contextual help/keyboard overlay -> submit validation -> required target-bound effects confirmation -> execute one background operation -> inspect rich inline result -> edit or issue another command after completion. Autocomplete selection never executes. Existing-target refusal, truthful telemetry and cooperative-cancellation limits remain unchanged.

## Define Cereja UI v1 Product Scope

This named stage records both settled decisions and remaining choices:

| Decision | Current state |
| --- | --- |
| Objective | Settled: interactive discovery, inspection and execution of existing Cereja capabilities, also serving as toolkit reference and dogfooding. |
| Primary user | Settled: Python developers and technical Cereja library/CLI users. |
| Secondary users | Settled: contributors and maintainers. |
| Product versus demonstration | Settled: an interactive Cereja product plus toolkit reference/dogfooding, not a widget-only showcase. |
| Initial capability proposal | Selected for elaboration: System Information, path-based Repository/Directory Tree, explicit-root Context Search, one Compress/Decompress area, and URL/destination Download. Ledger and file-plus-directory archive scope are selected; runtime acceptance follows the implementation tasks. |
| Interaction and visual language | Selected Ledger shell: persistent bottom composer, slash discovery, keyboard overlays, ordered bounded ephemeral inline result blocks. Detailed acceptance still requires implementation evidence. |
| Exclusions | Established direction excludes a generic file/search/system-administration product; exact per-capability exclusions remain to be recorded. |

Concrete proposed IA, flows and wireframes may now be elaborated for the selected areas. Ledger now provides the selected visual basis for product-derived planning; file and directory archive safety work has separate explicit acceptance criteria. Terminal/core infrastructure remains independent.

## Established requirements, proposals, and open decisions

Established technical requirements: reusable toolkit and explicit `cereja ui` application; independent core; keyboard usability; zero runtime dependencies; Python 3.11+; Windows/Linux/macOS; plain fallback; safe text; lazy loading; buffered partial rendering; documented Unicode policy; motion/no-color accessibility policies.

A capability is eligible for v1 only when all four conditions are evidenced: it already exists in Cereja, an interactive interface adds real value, it exercises important toolkit components, and it fits Cereja's purpose. Presence in the CLI index alone is insufficient. The user selected the five areas above using utility, toolkit coverage, interaction variety, low operational risk and controllable scope. The four eligibility conditions remain relevant to later additions.

Historical grouping supplied before the shell selection: Home/Dashboard, Tools/Capabilities, System, Examples, About/Diagnostics. Current navigation uses Ledger slash discovery and overlays; these groupings do not require dashboard pages. Dashboard should explain where the user is, what Cereja does, the environment and how to navigate. Candidate content includes Cereja/Python versions, OS, available CPU/RAM/GPU information, shortcuts and terminal capabilities. Collection cost, unavailable values and privacy need explicit behavior. Recent actions require a demonstrated use and a state/privacy decision; they are not an assumed feature.

| Open alternative | Justification | Impact if selected |
| --- | --- | --- |
| Settings | Additional session controls beyond existing capability options | Requires a scope decision; no new persistent settings surface is selected. |
| Further Tools integrations | Discover, inspect and execute another existing capability | Require a separate inclusion decision and evidence; no arbitrary command shell is implied. |

Tree accepts a user-provided path and exposes its hierarchy; it is not a full filesystem browser. Search requires explicit roots and is bounded context retrieval, not a generic search product. Download accepts a user URL and destination; it is not a full HTTP client. HTTP, encrypt, decrypt, protect, privacy, security, module and registry entries remain discovery/documentation links to their actual CLI or Python API, not runnable TUI actions.

## Capability execution flow under the shell grammar

This shared flow is proposed for the selected initial areas; it is not final design acceptance:

1. **Discover:** focus the bottom composer -> type `/` -> filter and select an eligible existing capability. Selection inserts its slash command without execution. The list states purpose and availability without loading unrelated subsystems. A missing host capability has a reason, not an unexplained disabled row.
2. **Inspect:** show what the capability does, its accepted input, expected result and known effects (read-only, file write, network or other operation-specific effects). Show the existing CLI/API equivalent only where accurate, without exposing secret values.
3. **Configure:** edit typed parameters with visible defaults and required markers. Validation explains the specific field error, retains other entries and performs no execution. Selecting a capability or moving focus never runs it.
4. **Review and run:** show effective nonsecret parameters and targets. An explicit Run action initiates parameter validation and effects review. Execution begins only after any required confirmation bound to the exact target and effect. Read-only operations without additional effects execute after validation without a blanket second confirmation. Default behavior refuses an existing target. Explicit overwrite is a proposal only where safe output publication supports it, not blanket consent. A changed target invalidates any previous effect review.
5. **Observe:** retain the operation identity and parameters while reporting Working and bounded output. Use a percentage only when the service supplies a reliable denominator. Keep input/navigation responsive. A Cancel action exists only with verified safe cooperative interruption. Leaving the view or stopping observation is navigation, never a cancellation substitute. Do not label unacknowledged work Canceled.
6. **Inspect result:** distinguish successful domain completion, partial completion, cancellation and failure. Show useful structured results or bounded safe text. Preserve source/target provenance and indicate truncated output. Explicit clean text copy follows the contract below; export/file writes are not implied by a result panel.
7. **Recover or return:** restore the composer command or parameter overlay; Edit preserves safe values; retry is explicit and never automatic for non-idempotent work. Surface partial side effects before offering retry. Back restores the invoking composer caret/selection or result focus and scroll. Secrets are excluded from history/diagnostics and are not silently persisted.

The application must call existing domain services or an explicit presentation-independent adapter, not construct a shell command from form values. An operation that lacks a suitable result, progress or cancellation contract creates adapter work; it does not justify fabricated progress, thread termination or claims of rollback. Escape during active work needs an operation-specific decision about cancellation versus leaving the result view.

Proposed consistency choices: one catalogue/detail convention; session-only safe parameter retention; a bounded Activity view that keeps active job identities visible while users inspect another screen. The initial UI permits one active job of any type at a time, with a worker keeping the UI responsive. This satisfies asynchronous/concurrent I/O relative to a responsive UI; it does not require multiple downloads. No mandatory queue or silently pending start is included. Multiple simultaneous operations are deferred and do not create another v1 decision gate. These choices remain reviewable.

## Current integration evidence

`cereja/commands/system.py` calls `hardware.info(detail="basic", include_sensitive=False)` for the default snapshot. `docs/guides/system-info.md` documents missing fields, opt-in sensitive identifiers and on-request collection. An exploratory System surface can consume that typed result, show `Unavailable` for missing values and collect only after an explicit Load action. It must not parse formatted CLI output. Cancellation is a service-contract question: the synchronous collector does not prove cooperative cancellation.

`cereja/commands/registry.py` and `docs/cli.md` contain the actual current CLI index. They do not yet establish an implemented `ui` command. Existing commands and structured output must remain separate from a future interactive session.

## Accepted long-operation contract

Level 1 is executable existing API integration: clear Running state, honest indeterminate activity, actual final duration/result/error, and no Cancel when safe cooperative interruption is absent. Compression remains useful in v1 at this level and is not blocked on future instrumentation. Apply the same rule to Download, Search, System and every other operation.

Level 2 is a separate investigation into reusable domain callbacks/progress and cooperative cancellation usable by CLI, UI and external callers. Domain code never imports UI. Level 3 records evidence and defers detailed progress/cancellation if the instrumentation cost is disproportionate, retaining the honest indeterminate v1 baseline.

Never simulate percentage, speed, ETA or cancellation. Determinate progress needs actual advance and a reliable total. Speed needs real byte/time observations. Spinner or shimmer only indicates known active work, never fabricated progress. No forced process/thread termination is marketed as cooperative cancellation. Synthetic toolkit examples are explicitly separate demonstrations and do not establish real-service support.

## Concrete initial area flows

| Area | Parameters and ordered interaction | Results, limits and recovery |
| --- | --- | --- |
| System Information | `/system` -> Load basic snapshot -> select section -> inspect -> Refresh. Full detail is an explicit request; unique identifiers remain off by default. | Panels and key-value/table rows; availability and collection state per section. Retain prior snapshot during refresh. Missing fields say Unavailable. No false percentage. A failed refresh retains the prior snapshot with its timestamp and error. |
| Repository/Directory Tree | `/tree` -> explicit Path and Depth overlay -> Load -> expand/collapse -> select node -> inspect full sanitized path -> Back. | Structured TreeView, bounded visible rows, scroll position and node identity survive resize. Show truncated labels and full details; respect ignores and do not traverse symbolic links. No file open/edit/delete action. A structured service is needed instead of parsing the existing rendered tree. Large-volume traversal limits must be visible. |
| Context Search | `/context` -> explicit root list, query, extension filters and visible limits -> Search -> results -> selected bounded snippet -> return. | Existing default bounds: 10 results, 1 MiB/file, 2 snippets/result and 240 characters/snippet. Show limits and skipped reasons. Highlight literal matches with text markers in no-color mode. Empty means no results within limits, not proof of no match. Cache stays off unless explicitly designed later. No Cancel unless safe cooperative interruption is verified; stale generations never replace newer results. |
| Compress/Decompress | `/compress` -> choose Compress/Decompress mode -> source and destination -> Run requests validation -> inspect exact target/effects -> overwrite confirmation if required -> execute -> Activity -> result. | One area, two modes. Executable existing API with indeterminate Running, real final duration/result/error and no Cancel at the baseline; detailed instrumentation is optional follow-up. Bounded logs, target path and partial-output state. Failure offers Edit or explicit Retry after showing side effects. No claimed rollback. Encryption, passwords and advanced archive options are outside this initial proposal. |
| Download | `/download` -> URL and destination overlay -> Start requests validation -> review exact destination/effects -> required target-bound confirmation -> execute -> Activity -> result. | Use supported URL schemes and destination rules from actual service. The existing TransferProgress supplies actual received bytes and an optional total. Show received bytes from those events, determinate progress only with a reliable total, and unknown-total activity otherwise. Derive speed only from actual byte/time samples; omit it until valid samples exist. No synthetic timer may advance bytes or percentage. One active background operation keeps the UI responsive. Another Run/Start is unavailable with the current operation named and a Return to current action until it finishes. The user invokes the next operation again after completion; nothing silently queues or starts later. Multiple simultaneous transfers are deferred. Network errors, existing target and partial files have specific recovery; do not imply resume support. Cancellation depends on the verified transfer contract. |

Navigation is the selected Ledger shell: slash discovery, parameter/help overlays and an ordered bounded ephemeral result ledger. Earlier Home/Tools/System/Examples/About groupings are capability metadata, not mandatory pages. System is central utility reached via slash discovery without duplicating state. The shell initial surface can show Cereja/Python versions, environment summary availability, purpose and slash guidance. CPU/RAM/GPU are shown only when collected and available. Recent actions are excluded until justified. About/Diagnostics shows terminal capabilities and session policies with sanitized diagnostics; exporting diagnostics is not automatic.

Tools labels have literal meanings: **Available** only for an actually runnable UI integration on this host; **CLI** for a verified CLI entry; **Python API** for a verified public API; **Planned UI** for an unbuilt selected candidate. These planning wireframes use Planned UI, never Available for unbuilt work. The wider catalogue can show documentation without creating execution buttons.

Modal proposal: an overwrite confirmation states source, exact target, effect and any known partial-output behavior. Default focus is Keep existing/Back, not overwrite. Enter activates only the focused action. Escape closes without running and restores the invoking control. Changed targets invalidate a prior confirmation. Run first validates parameters and the exact target, then obtains any required confirmation, and only then launches execution. Bind consent to that target and intended effect. Recheck destination state immediately before execution to handle races; confirmation does not provide an atomic overwrite guarantee.

Activity proposal: track operation ID, state, start time, safe parameters and bounded messages. The single current operation has states running, cancel requested only if supported, succeeded, failed, canceled only with acknowledgment, and outcome unknown. There is no implicit queue or persistent history; completed inline blocks follow the bounded ephemeral Ledger policy. Leaving a view does not cancel work. Closing the app with active work invokes an explicit job-aware exit decision; the UI never claims forced thread termination or rollback. If safe cooperative interruption is unavailable, omit Cancel and explain that work continues when leaving the view. Stop observing is not a cancellation action. Ctrl+C not consumed by active-text copy routes through the same exit lifecycle and restores terminal modes.

## Reference wireframes and review scope

The [reference sheet](cereja-ui-wireframes.html) contains all five areas, navigation screens, parameter forms, result details, activity, confirmation and error/empty/loading specimens at 120x40, 80x24 and 40x12, plus below-minimum recovery. Download includes both known-total and unknown-total TransferProgress fixtures; byte/time samples in the sheet are fictional inputs illustrating supported data, not live measurements. Fictional values are labelled. This is a concrete proposal, not a runnable TUI or observed usability. Compact forms use a scrolled field body with fixed actions and visible position so fields are reachable rather than silently discarded.

Examples retain synthetic Text/layout, Input/selection and Progress/feedback scenarios. They exercise toolkit behavior independently of service limitations. A deterministic synthetic job may show 6/20 steps, but that does not establish progress support in compression, tree, search or System services.

## Historical interaction hypotheses

Earlier key and responsive hypotheses are superseded by the final Ledger review
contract below. In particular, Escape closes/returns and never cancels work; q is
ordinary text with no global exit binding. Visible Help and Exit actions supplement
optional host key bindings. The old split catalogue/dashboard hypothesis is not
the current layout.

Focus is different from selection: a focused control has a textual marker; a selected row persists while focus moves. Returning to an example catalogue should restore its selected identity and scroll anchor. Loading should not steal focus. A removed control needs deterministic fallback to the next enabled visible control. These are testable interaction hypotheses to finalize after scope selection.

Reference responsive hypothesis: at >=100 columns and >=30 rows, catalogue and preview can split 40%/60% after the gutter. At 60-99 columns or 18-29 rows, use one primary region. At 40-59 columns or 12-17 rows, use compact controls and one content region. Below 40x12, show size-recovery guidance and preserve state. The chosen product can revise these thresholds after task trials. Browser pixels do not validate terminal cells.

Candidate plain fallback: a short static guide on noninteractive `cereja ui` invocation, without raw mode, alternate screen or prompt loop. Existing linear CLI output is an accessibility fallback, not evidence that a full-screen TUI works with screen readers. Final fallback content and exit semantics remain product-contract decisions.

## Exploratory component traceability

| Reusable component | Evidence specimen | States to evaluate |
| --- | --- | --- |
| Text, Panel, StatusBar | All authorized reference screens | Normal, clipped, empty, working, success, warning, error, canceled |
| Row, Column, Stack, split layout | Text/layout example and catalogue | Visible, constrained, hidden, resized |
| Button/action | Examples Start/Cancel/Reset, System Load | Default, focused, pressed, disabled with reason, busy |
| Input | Tree path, Search roots/query, archive paths, Download URL/destination | Empty, editing, focused, invalid, disabled, rejected paste; caret and selection |
| ListView | Catalogue, example choices, System sections | Empty, loading, selected, focused, unavailable, failed |
| ScrollView | Example details and System | Top/middle/end, wrapped, narrow, unavailable |
| Table/key-value composition | Text/layout and System | Missing values, long labels, bounded visible rows |
| Spinner/ProgressBar | Synthetic feedback job and System loading | Running, determinate, complete, canceled, failed, motion off |
| LogView | Archive/Download Activity and synthetic feedback | Bounded retention, follow-tail on/off, empty, paused scrolling, dropped-count notice |
| TreeView | Repository/Directory Tree | Hierarchy, expand/collapse, large volumes, selected identity, Unicode truncation and resize |
| Modal/Confirmation | Archive or Download overwrite | Safe initial focus, target revalidation, cancel, return focus |
| BackgroundTasks/Cancellation | Activity for long-running operations | One active operation, responsive UI, rejected second start, late result, verified cancel acknowledgment, failure, unknown outcome |

These mappings justify toolkit planning from concrete proposed flows. They do not approve final product implementation or prove existing services provide all required progress/cancellation behavior.

## Exploratory design system

Hierarchy hypothesis: title, task context, primary control, details, status, contextual hints. Use one row per result, one blank row between groups and one-cell horizontal padding. Comfortable density can add row gaps where space permits; compact layout removes them. Avoid decorative banners and emoji-only labels.

ASCII borders (`+`, `-`, `|`) form the reference baseline. Optional Unicode single-line borders require width validation; borderless sections need headings and gutters. Borders never carry the only focus or error indication.

Terminal-default colors are the conservative baseline. Candidate dark foreground/background: `#E6E6E6`/`#181818`; focus `#FFD75F`. Candidate light foreground/background: `#202020`/`#FAFAFA`; focus `#004B87`. Semantic roles are foreground, background, muted, focus, selection, success, warning and error. Real-terminal contrast must be checked because indexed palettes can be customized. Essential metadata must remain readable.

Capability descent: truecolor -> tested 256-color mapping -> semantic 16-color mapping -> Unicode/basic styling -> ASCII/plain. Nonempty `NO_COLOR` removes color, independently of motion and interaction. Words such as Working, Done, Warning, Error and Canceled preserve meaning. User overrides cannot make an unsupported host capability reliable.

## Motion, loading, and feedback policy

All motion uses the same deadline scheduler, invalidation, and renderer. No widget starts its own redraw thread. Overall frame ceiling: 30 Hz locally and 4 Hz in low-bandwidth mode. An active indicator has a stricter ceiling of 8 Hz locally and 2 Hz in low-bandwidth mode. Motion off produces zero timer-driven visual changes. These ceilings do not require continuous redraw. These are policy candidates to benchmark, not measured optimal rates. Visible work updates can still report meaningful changed counts with Motion off. Coalesce visual notifications; never drop ordered user input.

| Effect | Decision and fallback |
| --- | --- |
| Spinner | Exploratory option for unknown-duration foreground work. ASCII `| / -` frames; static `Working` with elapsed time only on real state updates when motion is off. |
| Determinate progress | Show completed/total and percentage only for a reliable denominator. Partial bar invalidates its own cells; static numeric progress in plain output. |
| Indeterminate bar | Optional toolkit example, not the default example. Reuse spinner timing; static `Working` fallback. |
| Loading dots | Alternative to spinner, never simultaneous. Bounded suffix width prevents reflow; static label fallback. |
| Pulse | Defer: color-intensity changes have weak value and poor no-color equivalence. Static activity label communicates the same state. |
| Shimmer | Evaluate on the System example against static skeleton and plain Working. Off by default; bandwidth, distraction and no-color evidence decide whether it helps. Renderer offers clipped dirty regions and shared timers; no shimmer-specific core API. |
| Skeleton loading | System may reserve known section slots with explicitly labelled static Loading placeholders. Do not invent values or search-result rows/counts. Retain a prior snapshot during refresh. Compare static skeleton versus simple Working before selecting the default. |
| Temporary highlight | Optional single event-triggered emphasis on changed detail. Clear once after 800 ms; Motion off keeps explicit `Updated` status without timed highlight. |
| Cursor blink | Prefer host cursor; do not create a second blinking caret. Motion off requests steady caret where supported, otherwise documents host control. |
| State transition | Immediate content replacement; no sliding, fading, or animated screen navigation. Preserve focus and anchors. |
| Success | `Done` and result count until the next action. No animation or auto-dismiss required. |
| Warning | Persistent `Warning` plus actionable cause; never only yellow. |
| Error | Persistent `Error` with Retry/Edit action; no shaking/flashing. |
| Ongoing activity | `Working`, named operation, capability-accurate Cancel or cancellation-unavailable reason; no invented completion percentage. |

On completion, cancel, hiding, terminal loss, or widget disposal, remove animation deadlines. Idle evidence must show zero periodic redraws/writes. SSH is not detected as an excuse for arbitrary behavior; expose low-bandwidth/motion-off choices and test their output bytes. Plain output never contains cursor control or animation frame history.

## Validation after the product gate

Use selected Ledger flows L1-L6 and their state contract as the planning baseline. Validate both file and directory archive modes and their safety stages; do not treat visual selection as runtime or usability validation. Proposed task trials: load/refresh System with unavailable fields; load a user path and find a nested Tree node; search explicit roots and inspect a bounded snippet; compress and decompress via the same area while rejecting an overwrite; download to an explicit destination and recover from a network failure; inspect the single active operation, verify the UI stays responsive and a second operation cannot silently queue, and exercise cancellation only where supported; open synthetic examples and resize. Return without losing inputs or selection. Repeat at all three sizes, no-color, ASCII and Motion off. Record participants, completion, wrong actions, help requests, steps and lost-state failures. A structural walkthrough is not observed usability.

Candidate hard gates: every selected task reachable by keyboard, zero focus traps, zero lost input/selection after return/resize, visible error recovery, zero color-only meaning, no hidden required control below minimum size. Final product scope may add tasks before these gates are frozen.

Once the virtual backend exists, verify actual cell snapshots and key-event traces, including long labels, CJK, combining characters, emoji, malicious controls, unavailable fields, slow jobs, cancel and stale results. HTML validates composition intent only. Release evidence requires Windows/Linux/macOS terminal trials, SSH/slow output, redirection/CI and assistive-technology trials before any full-screen accessibility claim.

## Bounded Ledger retention and planning handoff

Ledger retains ordered ephemeral result blocks, newest active nearest the composer, with selectable earlier blocks. Proposed limits are 20 completed summaries plus one active block and 2 MiB canonical UTF-8 sanitized retained payload. These are experimental budgets, not measured optimal values or a Python heap claim. Evict oldest completed blocks only, never active identity; bounded stream/detail truncation has visible omission counts. Tree/search/log/event limits remain independent. No sensitive retained fields or disk history.

Composer draft/caret stays independent. PageUp/PageDown scroll the selected result block. New output follows latest only if that mode was already active; otherwise preserve the selected block/anchor with a New result notice and Latest action. Completion never steals focus. The selected visual specification defines the detailed retention/eviction contract, L1-L6 and flow-to-toolkit traceability.

Files and directories are accepted archive v1 scope, with dedicated source collection, extraction confinement, links/traversal, resource limits, publication and partial-failure stages. Existing API safety gaps require implementation work and tests, not an assumption that directory support is already safe. Generic widgets stay domain-independent; application adapters own Cereja effects and schemas.

## Final Ledger review contract (#303)

Disposition: completed specification for review under the accepted Ledger scope,
not final human acceptance. This section resolves earlier interaction proposals for
the current planning handoff. The [visual language](cereja-ui-visual-language.md)
owns tokens, hierarchy and bounded retention; the
[operation contracts](cereja-ui-operation-contracts.md) own source-grounded domain
gaps. [The cell viewer](cereja-ui-ledger.html) is an authored review artifact with
synthetic fixtures, except labelled captured Download events. It has no live
service execution, application shell, production widgets or persistent history.

### Exact cells and recovery

The maintainer approved the current design for incremental implementation on
2026-10-09 and explicitly authorized starting #306. This includes the subtle
snippet surface and accepted clean-copy contract. It is a design decision,
not a participant walkthrough, assistive-technology trial or terminal result.
The first #307 implementation is documented in [ui-layout](../guides/ui-layout.md).

Coordinates are one-based, inclusive. H is height and W is width. One cell scale,
no pixel-based font hierarchy. Column W is unused in interactive frames. Normal
content starts at column 3, ends by W-2 and reserves outer clearance. Prose uses
45-75 cells when available; at 40 columns it wraps to 36. Long values and paths
have paged full-value inspection, not an ambiguous permanently clipped identity.

| Region | 120x40 | 80x24 | 40x12 |
| --- | --- | --- | --- |
| Identity, rule, clearance | Rows 1-3 | Rows 1-3 | Rows 1-3 |
| Result body | Rows 4-35 (32) | Rows 4-19 (16) | Rows 4-7 (4) |
| Result/overlay pager | Row 36 | Row 20 | Row 8 |
| Composer rule | Row 37 | Row 21 | Row 9 |
| Input, persistent | Row 38 | Row 22 | Row 10 |
| Contextual keys/action access | Row 39 | Row 23 | Row 11 |
| Job/session status | Row 40 | Row 24 | Row 12 |
| Total | 3+32+1+4=40 | 3+16+1+4=24 | 3+4+1+4=12 |

The four-row dock is always reserved. The pager never overwrites a value. Result
blocks remain chronological, with stable command/outcome headers; compact views
page the selected block and adjacent headers rather than discarding earlier blocks.
Block position and Latest remain reachable by keyboard even while payload is paged.
There is no permanent sidebar or dashboard split.

Parameter/help/review overlays occupy only the result body. They reserve one
title row, H-10 scrolling body rows and one fixed action row, plus the separate
pager: 30/14/2 body rows at the three sizes. At 40x12 a two-row field/error page
is valid; Tab reveals the focused field or action before input reaches it. The
overlay action row contains short labels whose full meanings appear in Help.
No essential action is cut from the viewport. Slash discovery uses at most seven
body rows at 120/80 and three at 40 (title, one selected suggestion, insert hint);
the selected item and position stay visible. No-match offers Edit/Help, no Run.

Below either W=40 or H=12, enter Size recovery. Suspend interaction with hidden
controls and preserve draft/caret/selection, form values/focus, block/item identity,
anchors and follow-latest. Display required/current size and Resize/Exit guidance
within available cells. Use recovery pages if all guidance cannot fit (very small
hosts can show one short line). Active work continues, with bounded events and
truthful status. Ctrl+C/visible Exit uses the same job-aware exit decision; hiding
the composer is not cancellation. Return to the prior surface on resize, clamp
anchors to valid bounds and reveal the focused item. No commands auto-submit.

### Keyboard, editing, focus, selection and scroll

| Surface/action | Contract |
| --- | --- |
| Initial | Focus composer. No filesystem, hardware or network collection before explicit submission. |
| Composer editing | Printable characters including q stay text. Left/Right move by grapheme, Home/End to draft ends; Shift extends selection. Backspace/Delete remove a grapheme/selection. Paste is bounded sanitized text and never executes, including embedded newline/slash. Single-line viewport scrolls to caret; selection survives help/resize. Rejected input leaves existing draft intact with a reason. |
| Slash shelf | Prefix filter, stable registry order, Up/Down selects. Enter or Tab inserts the selected command and closes discovery. It sets caret to inserted end and starts zero operations. A later explicit Enter with discovery closed validates/submits. No match retains draft. |
| Tab order | Composer -> selected block header -> enabled controls of that block -> Latest (when present) -> Help -> Exit -> composer. Shift+Tab reverses. Inside an overlay: fields in labelled order -> primary action -> Back -> Help; then wrap within the top overlay. Disabled actions explain why and are skipped. |
| Lists/Tree | Up/Down selects a stable item. Tree Right expands, Left collapses or selects parent. Enter opens full details/snippet; Back/Escape restores item and anchor. Focus `>` and selection `*` are distinct text markers. Selection stays when focus moves. |
| Block header | Left/Right selects previous/next retained block, without changing draft or running work. Home/End selects oldest/latest retained block only when header focused. Latest explicitly enables follow-latest. |
| Result/detail scroll | PageUp/PageDown moves a page minus one overlap row (minimum one). Home/End in a detail scroll surface means content start/end. Other arrow bindings remain local to their control. Resize clamps bounds and reveals selection. |
| Help | F1 or visible Help saves invoking state and opens context help. `/help` is explicit general help. Close restores exact draft selection/caret, form values/focus, block/item/anchor. Typing a help command itself naturally edits the draft; F1 does not. |
| Escape | Close top help/review/form/detail, then discovery, otherwise return focus to composer. It never implicitly clears draft or stops an operation. Form Back retains values for reopening during this session. |
| Edit/Retry | Edit restores safe parameters into a form. A nonempty unrelated draft requires Keep draft/Replace review before replacement. Retry revalidates effects/targets and partial-output state; no automatic retry. |
| Copy / Exit | Ctrl+C with an active textual selection in the key-owning surface requests clean copy, never exit/cancel (including copy failure). A selected row/node alone is not a textual selection. Without active text selection, Ctrl+C or visible Exit follows the job-aware exit flow. If idle, restore terminal and exit. If working without proven cooperative stop, default Stay; offer Wait then exit. Waiting keeps UI responsive and allows Stay. No forced worker kill or rollback claim. |

Focus and selection are separate. Worker completion updates its own block only,
never moves focus, closes an overlay or changes draft/inspection. New-result notice
stays until Latest; no timed dismissal. Item removal selects next surviving item,
then previous, then the empty-state action. A removed control falls to the next
enabled control in the same surface, then its header, then composer. Selected-block
eviction follows the existing nearest-survivor rule with an explicit notice.
These are application acceptance requirements; authored snapshot continuity is
not a runtime test of focus management or Unicode input.

### Accepted clean-copy contract (2026-10-09)

The maintainer explicitly accepted copy priority for active text selection and
clean content copying in this #303 continuation. This is a scoped UX decision;
clipboard transport and real-host behavior remain unimplemented and unverified.

Copy uses the canonical safe textual content before terminal layout, bound to
content identity/revision and logical selection offsets. Never reconstruct it from
screen cells, screenshots, ANSI output, wrapped rows or padded table columns.
Markdown is copied as its original Markdown source; a code snippet is copied as
its source text. Copy content and Copy snippet name the exact bounded payload.
A selection copies only its logical range, including original line breaks.
Structured results need an explicit stable plain-text representation from their
typed data; cell-aligned rendering is not that representation.

Exclude renderer-added margins, stems, borders, focus markers, line-number gutters,
column alignment spaces, soft wraps, ellipses, spinner frames, terminal color/style
sequences and clipboard rich formatting. Preserve source indentation, tabs, blank
lines, intentional leading/trailing spaces, Markdown hard-break spaces and code
fences that belong to Markdown. Do not use blanket strip/dedent or collapse runs
of whitespace. Clean means free of presentation artifacts, not removal of syntax.
Use the existing safe-text/redaction boundary before retention/copy; this contract
does not authorize exporting raw hidden control sequences or secret diagnostic data.

Active text selection belongs to the current key-owning surface. A preserved but
inactive selection in another input does not intercept its Ctrl+C. A selected
result row/tree node is navigation: use explicit Copy content/snippet to copy it,
or create a textual range first. During textual selection, pin the inspected
content revision and selection anchor within the existing bounded retention budget.
New domain output/completion can continue; it must not replace the selected text
or shift its offsets. Keep animation/redraw from modifying the selected region.
If that snapshot can no longer be retained, explain the limit and invalidate the
selection explicitly instead of silently copying different content.

| Copy condition | Observable behavior |
| --- | --- |
| Active text selection + Ctrl+C | Copy selected canonical text as plain text; preserve draft/caret/range, result identity/focus/scroll and active operation. Never fall through to exit. |
| Explicit Copy content/snippet | Copy the named retained payload without visual decorations; no hidden source fetch, implicit whole-file access or file export. |
| Clipboard unavailable/denied/failure | Explain Copy unavailable/failed, retain selection/state and operation; do not report Copied or invoke exit. Keep text inspectable for the host's native copy fallback. |
| Copy succeeds | Copied appears only after the supported backend acknowledges the actual write. No focus steal or automatic deselection; plaintext only, no ANSI/HTML/RTF styling. |
| Payload truncated/not fully retained | Name the copy scope as retained snippet/content and show the omission outside the copied payload. Do not insert warning text into code/Markdown or claim full-file copying. |

The clean guarantee applies to the application's explicit canonical-text copy on
supported, tested clipboard backends. Copying terminal cells with the emulator's
mouse selection remains host behavior and can include margins/soft-wrap artifacts.
The [Win32 selection API](https://learn.microsoft.com/en-us/windows/console/getconsoleselectioninfo)
has no VT equivalent; it does not establish Windows Terminal/ConPTY/SSH support.
[Windows Terminal copy](https://learn.microsoft.com/en-us/windows/terminal/customize-settings/actions#copy)
operates on its selected terminal content. Host integrations must be
capability-specific. No clipboard reading/polling, silent remote-to-local clipboard
write, automatic copy or OSC 52/native backend is selected by this UX decision.

Acceptance requires comparing real plain clipboard text with independently defined
expected Markdown/code/range fixtures at all three sizes, no-color/ASCII/Motion off,
including tabs, nested indentation, blank lines, Markdown trailing spaces, long
wrapped lines and redacted content. Check focus/selection/scroll preservation,
completion during selection, denied/failed writes and unavailable local/SSH hosts.
The review viewer shows expected payloads and authored outcomes without writing
the real clipboard. These examples do not prove a future clipboard backend.

Existing #308/#310/#313 contracts and #321 acceptance receive this traceability
input through #303; no implementation, backlog execution or #306 modification
is authorized by recording it here.

### Forms and exact-target review

Required fields are labelled `*`; defaults and bounds are visible. Failed validation
retains other values, puts focus on the first invalid field, reveals its error and
starts no job. URL/userinfo/query diagnostics are redacted. Full exact local target
remains inspectable across pages before consent. UI checks give early feedback;
authoritative domain validation and publication safety remain separate.

| Form | Field order and primary action |
| --- | --- |
| System | Basic non-sensitive scope, optional section, Load/Refresh. Full detail is explicit; identifiers off. |
| Tree | Path*, Depth (candidate 3), visible traversal/retention bounds, Load. No implied cwd/root or link descent. |
| Context | Roots* (explicit list), Query*, Extensions, max results 10, max file 1 MiB, snippets 2, snippet chars 240, Search. Cache off; result cap is not a scan bound. |
| Archives | Compress/Decompress, File/Directory, Source*, Destination*, supported format/policy and limits, Review. Encryption/password options are not selected. |
| Download | HTTP(S) URL*, Destination*, visible service/budget policy, Review. No general HTTP editor or assumed resume. |

Read-only System/Tree/Context submit after valid explicit input. Archives/Download
review exact source/action/output kind/destination/effects before a separate Run.
Existing output is refused by default. Replacement confirmation is available only
for a supported tested policy; otherwise offer Edit destination/Back. A review
screen is not permission to use the unsafe existing directory extractor.

Consent is bound to a validated tuple: operation kind, source identity, canonical
destination identity, output kind, intended effect, relevant policy and observed
target state/version. Any changed field/source/target state invalidates consent.
Default focus is Back/Keep existing. Enter activates only the focused action.
Recheck race-sensitive state immediately before effects/publication; change returns
to review/refusal. A modal cannot establish atomic no-clobber or replacement safety.
Exact-target review pages keep fixed actions and target identity available, with
the effect/source/details reachable via pager; do not enable destructive consent
while required target details remain unavailable to inspect.

Archive stages remain distinct: (1) validate explicit inputs/kind/target,
(2) collect source using the directory/link/ignore policy, (3) validate format and
member names/containment/collisions/types, (4) enforce member/depth/per-member and
aggregate expansion budgets during decoding into owned staging, (5) validate full
outcome, (6) publish under the supported no-clobber/replacement policy, (7) report
omissions, partial effects and owned cleanup failures. File stages use their own
limits/publication checks. #323 owns directory domain safety; #324 owns UI
integration after #318's file flow. No automatic merge or source deletion.

### L1-L6 outcomes and review specimens

| Flow | Specimens and recovery to review |
| --- | --- |
| L1 System | Explicit load, known-section Working, Success with Unavailable fields, refresh failure retaining prior timestamp/snapshot, Retry. No invented hardware values in live UI. |
| L2 Tree | Explicit path/depth form, bounded hierarchy, collapsed/expanded/selected node, full sanitized path, Back restores selection, missing/permission/incomplete state. No file mutation. |
| L3 Context | Roots/query form, field error, results and bounded literal `[match]` snippet, Back, Empty within limits and skipped reasons, incomplete/error with Edit. No global absence claim. |
| L4 Archives | Both modes and both output kinds, effects review, existing-target refusal, supported-policy-only confirmation, rejected traversal/link/budget, indeterminate Working, success and cleanup/partial warning. Real safety work remains pending. |
| L5 Download | URL/destination review, captured known/unknown-total byte snapshot, network failure with target/partial state, Edit/explicit Retry. Progress never means committed. No speed/ETA or Cancel in this baseline. |
| L6 Reference/discovery | Synthetic table/input/feedback examples, help roundtrip preserving an edited draft and inspected older block, catalogue with accurate CLI/API and Planned UI labels, diagnostics without secret retention. |
| Shared lifecycle | Ordered completed + active blocks, completion during help/editing, refused second start with Return to current, Latest notice, selected-block eviction, compact paged form, below-minimum resize restoration and active-job exit. |

Loading/Empty/Error/Success/Warning remain inline outcomes attached to command
identity and parameters. Success requires domain completion/publication, not 100%
bytes. Partial/cleanup failure and Outcome unknown are explicit, never relabelled
as success or canceled. Unknown total uses actual bytes plus Working; absence of
byte callbacks uses Working only. One operation, no queued Run, no disk history.
Twenty completed summaries and 2 MiB sanitized payload remain calibration candidates,
with bounded active detail and independent domain/event limits.

### Hierarchy, capabilities and motion disposition

Identity -> command/state -> useful result -> detail -> pager -> composer/action
-> job status. Use one-cell clearance, sparse headings, whitespace between blocks
when space permits, optional bold and textual `>`, `*`, Error/Warning/Done markers.
Borders are for overlays/rules, not every result. Compact density removes gaps,
not required labels/actions. Terminal-default palette is conservative; Ledger dark
tokens remain specified in the visual language. Optional light tokens use the
existing foreground #202020/background #FAFAFA/focus #004B87 candidates. Truecolor,
256/16 mappings, no-color and ASCII retain the same semantic words and focus
markers. Host palette contrast and assistive technology require actual trials.

The existing motion effect table above remains the complete disposition: spinner
or dots for known activity (one indicator), determinate only from real totals,
indeterminate bar as synthetic optional demonstration, pulse deferred, shimmer off
pending benefit, skeleton only known labelled slots, optional 800 ms highlight,
host cursor rather than a second blink, immediate transitions, persistent textual
success/warning/error. Share scheduler/invalidation/rendering, ceilings 30/4 Hz
overall and 8/2 Hz indicators. Reduced-motion/Motion off has zero timer-driven
visual changes; meaningful domain updates remain. Hidden/disposed/completed
indicators release deadlines; idle has no periodic rendering. No fake percentages,
speed, ETA or cooperative Cancel. ASCII/no-color are independent from motion.

Noninteractive launch remains a future app requirement: short static guide to
existing CLI/API, no raw mode, alternate screen, prompt loop or animation. Exact
CLI launch/exit implementation belongs to #313. Do not claim screen-reader
accessibility from this fallback or browser screenshots.

### Verification and #306 preparation boundary

The viewer and generator verify authored cell budgets, paged content/action access
and selected snapshot continuity. The [review record](cereja-ui-visual-review.md#ledger-ux-303-review-2026-10-09)
records commands, actual inspection and gaps. Production key traces, Unicode
editing/width, focus manager, real retention/memory, responsiveness and domain
safety are unimplemented application acceptance, not passes from these specimens.
Real emulator/SSH/ConPTY trials and human task/accessibility review remain pending.

The original traceability is retained for the authorized incremental #306 delivery:

| Contract | Existing slice |
| --- | --- |
| Cell layout/clip/scroll/hierarchy | #307 |
| Editing/focus/selection/discovery | #308 |
| Help/forms/exact-target overlays | #309 |
| Tree/list/table/result collections | #310 |
| Inline feedback/shared motion | #311 |
| One active operation, truthful lifecycle | #312 |
| Ledger shell/catalogue/official command | #313 |
| L1 / L2 / L3 | #314 / #315+#316 / #317 |
| L4 file / directory safety / directory integration | #318 / #323 / #324 |
| L5 / optional instrumentation / real acceptance | #319 / #320 / #321 |

The #303 specimen checkpoint did not include backlog execution. The maintainer's
2026-10-09 approval now authorizes #306 by increments, with #307 geometry first
and #308 input/focus/selection next. #304 optimization, #305 alteration, File I/O
2.0 and legacy migration remain outside this delivery. Real task and terminal
acceptance are still pending; design approval does not replace them.
