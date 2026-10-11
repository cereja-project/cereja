# Cereja shell visual comparison review

Status: the maintainer explicitly selected A: Ledger after this bounded review.
The review is not actual-terminal, usability or release validation.
Artifact: [interactive comparison](cereja-ui-visual-comparison.html).
The earlier [73 functional references](cereja-ui-wireframes.html) are preserved.
No production toolkit/application code, dependency, commit or push is included.

## Brief and exact scope

Two visual languages share a persistent bottom composer, slash discovery,
autocomplete/context help, rich inline content and keyboard overlays. Ledger
uses open result sections and a fine cherry stem. Workbench uses a framed
current-result canvas, wide contextual column and modular System data. Difference
is spatial organization and reading hierarchy, not only dark versus light color.
Both use a typographic Cereja signature; neither claims a new official logo,
assistant identity, chat behavior, AI capability or copied product appearance.

The comparison has shared controls for initial/slash/System/known progress/
indeterminate activity/error/empty, plus useful secondary states, at 120x40,
80x24 and 40x12. Full Truecolor/256/16/monochrome palettes and a plain snapshot
are included. Motion defaults off. The optional shimmer changes only a bounded
placeholder and respects reduced motion; no progress timer changes byte counts.
The determinate specimen uses a fixed captured 768/1536-byte snapshot. Speed
and ETA are omitted because the probe has no timestamp samples.

## Review method and limits

The executor used the composition and typography skills for terminal-cell
layout; poster margins/font hierarchies were not imposed on a terminal.
A separate source reviewer applied visual-qa hard gates. The coordinating
reviewer inspected actual browser output and replayed interactions. Reviewers
share task context; this is not a blinded study or independent user research.

The reviewed HTML is code-native, not an image-generation output. No photo,
human anatomy, Arabic glyph, packaging or existing-logo edit category applies.
No visual winner can be inferred from these review activities.

## Findings corrected before this checkpoint

| Finding | Correction | Evidence scope |
| --- | --- | --- |
| Suggestion Enter opened a view immediately | First Enter inserts and closes; second Enter submits. Completion caret moves to the inserted command end. | Actual browser replay passed for both alternatives with `/sys`. |
| Compact pager overwrote an OS value | Reserve an independent result row before slicing visible content. | Both compact monochrome System views rechecked; no overwritten value. |
| Unknown command showed destination error | Dedicated Command not found state, no operation-start claim. | Source review and corrected state path; not a real operation. |
| Partial capability recoloring | Map all semantic tokens for 16/256 and neutralize all mono/plain tokens. Plain removes interactive input. | Source token review; compact monochrome and plain DOM checked. Actual emulator palettes untested. |
| Static selection affordances | Bounded Tree/Context/Examples arrow/Enter fixture interactions. | Source contract check; not a complete production widget test. |
| Help lost prior context | Overlay preserves the underlying current view; Escape returns. | Source correction; not exhaustive caret/state restoration testing. |
| Browser Tab trap | F6 returns to external review controls. Product input and browser review controls are explicitly separate. | Source behavior check; full assistive-technology testing pending. |
| Workbench inspector could cover text | Reserve inspector width before clipping main content. | Source geometry and sampled wide render. |

## Rendered and interaction checks actually performed

- Both alternatives: reset Initial, type `/sys`, first Enter leaves Home with
  `/system` inserted, second Enter opens the System fixture.
- Required seven states were inspected in browser DOM with the composer present
  for both alternatives: initial, slash, System, determinate, indeterminate,
  error and empty. This is not every state x size x palette combination.
- Plain snapshot removes interactive composer and motion.
- Screenshots inspected: Ledger System wide; both small monochrome variants;
  Workbench System 120x40 full frame; Workbench Working 80-column shimmer.
- Earlier functional-reference review covered sampled Dashboard, Archives,
  Download and Activity views. Those do not substitute for current-shell review.
- JavaScript syntax was checked with the available Node runtime. Source geometry
  reserves the bottom four rows; pager and suggestions remain inside content.

These checks establish a concrete reviewable prototype with the reported defects
addressed. They do not establish actual terminal Unicode width, input handling,
restoration, performance, screen-reader support or observed user usability.

## Qualitative checkpoint verdict

READY FOR USER REVIEW ONLY. This is not design approval or final signoff.
No numerical threshold was predefined for this exploration; retrospective
scoring would imply more assurance than the sampled renderings support. The
reported critical interaction/layout findings were corrected and rechecked,
with no remaining critical defect observed in that bounded review. Actual
terminal behavior, host color rendering and user usability remain unvalidated.
The maintainer subsequently selected A: Ledger. This is a product direction
decision, separate from the limited assurance of these review checks.

## Acceptance boundary

A: Ledger is selected. Consolidate the five capability flows and derive
traceable high-level widget/application planning tasks from that direction.
Files and directories are accepted v1 archive scope with their own safety stages. The independent terminal/rendering work is not blocked.
No change to those boundaries follows from a polished browser prototype.

## Accepted directory scope update

The maintainer explicitly selected **files and directories in v1, with their own
safety stages and criteria**. This decision replaces earlier pending/conditional
directory language. Directory traversal/format safety, bounded extraction, owned
staging and truthful publication/cleanup outcomes are separate domain and UI
integration tasks. Existing API behavior is not thereby certified safe.

Ledger retains ordered result blocks within a bounded ephemeral session. The
resource policy and state restoration are specified in the selected visual-language
document; the current-result-only comparison prototype does not implement that
retention extension and is not evidence that it has been runtime validated.

## Ledger UX #303 review (2026-10-09)

Disposition: specification and concrete review artifact ready for human review.
This is the initial #303 checkpoint; the clean-copy continuation below updates it.
The earlier sections describe the historical comparison.
No comparison was reopened. No application, widget or domain integration was built.
The consumer is #303 review and the next #306 readiness assessment; maintain this
bounded fixture generator with the UX document, not with domain/runtime contracts.

Artifacts: [Ledger viewer](cereja-ui-ledger.html),
[final UX contract](cereja-ui-ux.md#final-ledger-review-contract-303),
[generator/checker](../../benchmarks/ui_ux/specimens.py).
The [fingerprint record](cereja-ui-visual-artifacts.json) identifies the generated
HTML/source Git blob bytes (canonical LF); Windows checkout line endings are
separate. It preserves earlier artifact provenance separately.

| Verification layer | Observed result and limitation |
| --- | --- |
| Structural | `python benchmarks/ui_ux/specimens.py --check` passed: 44 authored states, nine walkthroughs, 273 ASCII frames/pages at 120x40, 80x24, 40x12 and 32x10 recovery. Checked row/column budgets, unused last column, pager/dock separation, complete paged values, fixed overlay actions, visible result-action hint and immutable recorded state across generation/resize. Also checked insertion without a new job, safe default/invalidated consent, refused second start, help/completion and Tree/snippet return snapshot continuity. These are assertions about authored data, not a working app's behavior. |
| HTML/browser | Generated JavaScript parsed with Node. Chrome viewer replay passed all nine walkthroughs (49 authored steps), 15 size/palette samples, and all five compact Context form pages with Search/Back/Help fixed. Checked recorded caret/selection/block/item/anchor continuity during help/completion and below-minimum recovery. Palette/motion controls never modify state or telemetry. The viewer selects snapshots; it does not send terminal key events. |
| Visual inspection | Actual browser images inspected: initial 80x24, sequential completed/active blocks at 80x24, Context form and conditional confirmation at 40x12 monochrome, Tree at 120x40, active-job recovery at 32x10. Composer/pager remain separate; compact forms keep actions; confirmation starts on Keep; paths/effects are paged rather than lost. Screenshots establish sampled composition only, not all states/palettes. |
| Terminal/emulator | Not executed for this UX delivery. The application is absent. Existing core automated CI is separate; real emulators, SSH and ConPTY trials remain pending. ASCII/browser cells do not validate terminal Unicode widths, caret editing or input routing. |
| Human/accessibility/usability | No participant task review or assistive-technology trial conducted. No usability, accessibility or final human acceptance claim. #303's combined walkthrough/user-review criterion remains incomplete. |

Reproduction: generate with `python benchmarks/ui_ux/specimens.py`, serve
`docs/design` on loopback and open `cereja-ui-ledger.html` in a browser. External
Walkthrough/Step/Cells/Palette and content-page controls select authored specimens.
Replay discovery (first Enter insertion versus later submission), Refresh focus/error,
Tree detail return, Context validation/snippet return, all four archive modes and
safety/refusal cases, Download known/unknown captured events/error, references,
help/completion/return, second-start refusal and active-job exit. At 40x12 page the
Context form through all five pages; at 32x10 verify recovery, then return to 40x12.
Inspect recorded state alongside frames, without interpreting it as an app trace.

The first browser launch failed in the host sandbox; file-protocol navigation was
blocked. A scoped native Chrome test session and loopback-only static server enabled
the reported review. These are host execution limitations, not Cereja/EDD defects.
No dependency or credential installation was required.

Fixtures: System values, all paths/outcomes/policies and examples are synthetic.
Download 768/1536 bytes (50%) and 768 bytes with unknown total are fixed events read
from [the retained loopback report](../../benchmarks/ui_spikes/download-loopback.json),
not live activity or a new transfer measurement. No speed/ETA is inferred. The
conditional Replace specimen explicitly assumes a synthetic supported policy;
it does not certify current file/directory publication safety. No real operation
offers Cancel. Motion is static; rate ceilings are specified, not rebenchmarked.

One bounded source/diff assessment and geometry/browser review were performed.
Corrections made within that assessment: replace stale result budgets with an
independent pager, preserve the unfinished-draft selection visually, show a current
result-action hint, add a Refresh-focus snapshot without execution and fit slash
discovery into its separate three-row compact shelf. The scope
manifest now references these artifacts. No production-code or export change.

Next action: maintainer reviews selected Ledger L1-L6 and shared lifecycle in the
viewer, recording accepted flows or actionable corrections on #303. Then decide
#306 readiness explicitly. #302 records accepted scope; both issues remain open
in Reviewing at this checkpoint. Twenty results and 2 MiB, real retention/memory,
runtime focus/input, safe domain integration and real-terminal/human acceptance
remain outside the claims established here.

## Clean-copy continuation (2026-10-09)

The maintainer accepted active-selection copy priority and copying clean content
without terminal formatting. [The accepted contract](cereja-ui-ux.md#accepted-clean-copy-contract-2026-10-09)
now distinguishes canonical Markdown/code/range content from padded/rendered cells,
preserving semantic whitespace instead of trimming it. Failed/unavailable copy
retains selection and work and never falls through to exit. Native emulator copy
has a separate host-dependent limit. No production clipboard backend is implemented.

The viewer adds eight authored cases: Markdown with hard-break spaces/code fences,
code indentation/blank lines, tabs, a selected logical range, denied copy, unavailable
clipboard, completion during selection and row navigation versus explicit Copy.
Expected payloads appear outside the terminal-cell frame for direct inspection.
All eight are synthetic and acknowledge no real clipboard write.

Executed checks: generator and `--check` passed with 52 states, ten walkthroughs,
323 frames/pages and eight source/range copy expectations. Chrome replay passed
57 authored steps, 15 size/palette samples and the five compact form pages.
The new copy-specific replay checked eight cases at all three supported sizes
(24 samples), exact expected payload strings, Markdown trailing spaces, code
indentation/blank lines, literal tabs, dispatch priority and recorded state/revision
preservation across failure/unavailability/completion. Node syntax and diff checks
passed. Actual screenshots inspected: clean code at 40x12 monochrome and Markdown
at 80x24 monochrome, showing canonical content separately from the terminal layout.

No real clipboard read/write, terminal input, native-selection detection or
clipboard transport roundtrip was performed. These are authored/browser checks,
not proof of runtime copy fidelity, accessibility or overall UX acceptance. The
existing Git/LF artifact fingerprints retain the initial published checkpoint
and identify the updated generator/HTML. The accepted copy choice is narrower
than final human review of the entire Ledger experience, which remains pending.

Next action: review the clean-copy specimens with L1-L6 and the shared lifecycle
on #303. Real backends must later prove plain-text source fidelity and failure
behavior on supported local/remote hosts under #321. Existing #308/#310/#313
traceability is preparation only; no #306 or backlog execution occurred.

## Snippet surface refinement (2026-10-09)

The maintainer requested a slightly more distinct snippet region. The updated
viewer uses a restrained neutral surface on snippet rows and a muted surface/thin
edge on the external canonical-text preview. Color roles stay separate from focus,
selection and status. The no-color/16-color treatment retains explicit text labels.
Source line ranges drive semantic row metadata across wrapping/paging; they do not
insert decorations into the copied payload or allocate more terminal cells.

Executed: generator and `--check` passed for the same 52 states, ten walkthroughs,
323 frames/pages and eight copy expectations. Copy records were compared against
the prior published HTML and remained identical. Region rows stay within the result
body; JavaScript syntax, local links, Git/LF fingerprints and diff checks passed.

Current browser inspection was unavailable: the browser-use policy rejected reading
the open file-protocol tab. No alternate route/browser was used to bypass it. This
continuation establishes source/structural checks only, not a new visual inspection,
contrast/accessibility result or human acceptance. Earlier browser observations
remain bound to their previous published artifacts. Next action: refresh the viewer
and inspect the Context snippet and clean-copy cases for the requested subtlety.

## Design approval and implementation handoff (2026-10-09)

The maintainer approved the current design and explicitly authorized starting
#306 by increments. This accepts the selected design, including the snippet
surface and clean-copy decision, for implementation. No participant task
walkthrough or accessibility/assistive-technology test was reported; those
remain pending. The earlier source/browser observations keep their original
revision and scope. No new browser inspection is claimed.

The first implementation is [#307 geometry](../guides/ui-layout.md), independent
from keyboard/widgets/application/domain integration. Nineteen focused layout
tests cover exact allocations, wide/nested clipping, empty/undersized windows,
selected-target resize, lazy visible rows and bounded geometry damage. The
combined layout/import/buffer/rendering run passed 76 tests. The broader UI run
passed 233 tests with nine platform skips on Windows/Python 3.14. POSIX/macOS
checks skipped locally are not passes. Export-stub consistency and fatal lint
checks passed. The first sandbox import run failed only on the interpreter's
stderr location warning; the same unmodified tests passed outside that restriction.

[Frozen geometry baseline](../../benchmarks/ui_layout_samples/baseline-windows-py314.json):
31 samples of 100 iterations, seven separate memory samples, three warmups.
Resize median/p95 20.5/22.0 microseconds per iteration; long-content geometry
6.7/10.0 microseconds. Median peak traced Python memory 14376/12888 bytes.
Synthetic logical row dimensions are inputs; timings and traced bytes are real
measurements of the declared window. No content scan/rendering/terminal/input,
clipboard, RSS or application latency was measured; #304 budgets are unchanged.

The bounded ASCII/no-color example prints one frame or recovery; it has no
keyboard dispatch or domain actions. It is a runnable geometry example, not
the official Ledger application. `cereja ui` remains unimplemented. Next action:
review #307's API, then continue #308 under the approved input/focus/selection
contract. Terminal clipboard roundtrips and real task/human/accessibility
acceptance stay under #321.
