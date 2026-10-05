# Cereja UI exploratory experience evidence

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
| Help | Discoverability and key explanations | Dedicated screen versus contextual hints; return-focus behavior and maintained content. |
| Settings | Session accessibility and capability overrides | Inputs, state lifetime and precedence; may instead be launch options or About/Diagnostics controls. |
| Further Tools integrations | Discover, inspect and execute another existing capability | Require a separate inclusion decision and evidence; no arbitrary command shell is implied. |

Tree accepts a user-provided path and exposes its hierarchy; it is not a full filesystem browser. Search requires explicit roots and is bounded context retrieval, not a generic search product. Download accepts a user URL and destination; it is not a full HTTP client. HTTP, encrypt, decrypt, protect, privacy, security, module and registry entries remain discovery/documentation links to their actual CLI or Python API, not runnable TUI actions.

## Capability execution flow under the shell grammar

This shared flow is proposed for the selected initial areas; it is not final design acceptance:

1. **Discover:** focus the bottom composer -> type `/` -> filter and select an eligible existing capability. Selection inserts its slash command without execution. The list states purpose and availability without loading unrelated subsystems. A missing host capability has a reason, not an unexplained disabled row.
2. **Inspect:** show what the capability does, its accepted input, expected result and known effects (read-only, file write, network or other operation-specific effects). Show the existing CLI/API equivalent only where accurate, without exposing secret values.
3. **Configure:** edit typed parameters with visible defaults and required markers. Validation explains the specific field error, retains other entries and performs no execution. Selecting a capability or moving focus never runs it.
4. **Review and run:** show effective nonsecret parameters and targets. An explicit Run action initiates parameter validation and effects review. Execution begins only after any required confirmation bound to the exact target and effect. Read-only operations without additional effects execute after validation without a blanket second confirmation. Default behavior refuses an existing target. Explicit overwrite is a proposal only where safe output publication supports it, not blanket consent. A changed target invalidates any previous effect review.
5. **Observe:** retain the operation identity and parameters while reporting Working and bounded output. Use a percentage only when the service supplies a reliable denominator. Keep input/navigation responsive. A Cancel action exists only with verified safe cooperative interruption. Leaving the view or stopping observation is navigation, never a cancellation substitute. Do not label unacknowledged work Canceled.
6. **Inspect result:** distinguish successful domain completion, partial completion, cancellation and failure. Show useful structured results or bounded safe text. Preserve source/target provenance and indicate truncated output. Export, clipboard and file writes are not implied by the presence of a result panel.
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

Activity proposal: track operation ID, state, start time, safe parameters and bounded messages. The single current operation has states running, cancel requested only if supported, succeeded, failed, canceled only with acknowledgment, and outcome unknown. There is no implicit queue or persistent history; completed inline blocks follow the bounded ephemeral Ledger policy. Leaving a view does not cancel work. Closing the app with active work invokes an explicit job-aware exit decision; the UI never claims forced thread termination or rollback. If safe cooperative interruption is unavailable, omit Cancel and explain that work continues when leaving the view. Stop observing is not a cancellation action. Ctrl+C routes through the same lifecycle and restores terminal modes.

## Reference wireframes and review scope

The [reference sheet](cereja-ui-wireframes.html) contains all five areas, navigation screens, parameter forms, result details, activity, confirmation and error/empty/loading specimens at 120x40, 80x24 and 40x12, plus below-minimum recovery. Download includes both known-total and unknown-total TransferProgress fixtures; byte/time samples in the sheet are fictional inputs illustrating supported data, not live measurements. Fictional values are labelled. This is a concrete proposal, not a runnable TUI or observed usability. Compact forms use a scrolled field body with fixed actions and visible position so fields are reachable rather than silently discarded.

Examples retain synthetic Text/layout, Input/selection and Progress/feedback scenarios. They exercise toolkit behavior independently of service limitations. A deterministic synthetic job may show 6/20 steps, but that does not establish progress support in compression, tree, search or System services.

## Questions for later interaction validation

Candidate keys to evaluate: Tab/Shift+Tab for focus, Enter/Space for buttons, arrows for focused lists or preview scroll, PageUp/PageDown for a page minus one overlap row, Escape for cancellation/back, and q to quit outside text inputs. Literal q and pasted text must remain text in inputs. Ctrl+C must restore terminal state on exit. Visible actions remain available when a host intercepts function keys.

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
