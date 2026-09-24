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
