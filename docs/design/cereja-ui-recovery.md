# Cereja UI planning recovery

This record reconciles the approved planning from local session
`01a0c28e-15d6-76d3-a9a7-e4927e64d1fd` and the two variants in
`cereja-ui-withdrawn.zip`. It preserves product decisions and UI-00 freeze v1;
it does not restart product planning or establish native terminal acceptance.

## Sources and selection

The archive contains 54 payloads with verified SHA-256 hashes, 27 per variant.
There are 18 identical pairs, seven differing pairs, two publication-only source
files and two original-only generated interpreter caches. The complete inventory,
archive fingerprint and per-file selection are in
[the recovery manifest](cereja-ui-recovery.json).

The publication variant is selected because its changes preserve the contract
and improve replay portability, publication history and evidence limits. Every
differing original is retained under `recovery/original_checkout/`. The withdrawn
visual fingerprint receipt is also retained, because its newline conclusion is
corrected below. Generated `.pyc` files are excluded from the repository; their
archive hashes remain recorded. None was executed.

The planning was originally reviewed on 2026-09-21 against
`ed7fbfa5bc08f3e5814602f1cb3f09e3d6ad5d87`. A later publication replay used
`f54f600668c1370dc414bff8cdcf975324888a30`. Historical
[PR #330](https://github.com/cereja-project/cereja/pull/330) was closed without
merge (head `22fcfaa1578255b0572a59e35e7df8ebdede3952`). Restoring the artifacts
does not imply that withdrawn publication was merged. The current recovery began
on `develop` at `c98f3318dc3325bf15da29e37c525daaa92c66a9`, with a clean tree.

## Visual fingerprint correction

The old publication receipt incorrectly said the HTML fingerprints disagreed
even after newline normalization. Both supplied HTML files contain LF newlines.
Converting LF to CRLF reproduces the original recorded hashes exactly. The
[current receipt](cereja-ui-visual-artifacts.json) records both representations
and retains the earlier values. This resolves a byte-provenance discrepancy;
it is not a new browser inspection, usability result or real-terminal validation.

The historical visual review, prototype limitations and human Ledger selection
remain separate evidence. No claim of current visual acceptance is added.

## Recovered decisions and current boundary

The selected product direction remains Ledger: bounded sequential inline results,
persistent command composer, slash discovery, contextual help and keyboard
overlays. The five executable areas remain System, explicit-path Tree,
explicit-root Context Search, Compress/Decompress and Download. Archives include
files and directories with dedicated safety criteria. Progress and cancellation
must reflect real domain capabilities. The product is a Cereja shell and a
toolkit consumer; it is not a chatbot or a generic file browser.

UI-00 retains Python 3.11+, standard-library runtime, independent lazy UI modules,
Unicode 17.0, conservative capability precedence, a single terminal owner,
transactional cleanup/output and explicit bounded-resource policies. Public
signatures remain implementation choices. This delivery implements only #295.
Native adapters, Unicode tables, rendering, scheduling, the application and
File I/O 2.0 are not activated by recovering this plan.

The [architecture](cereja-ui.md), [task manifest](cereja-ui-tasks.json),
[delivery plan](cereja-ui-plan.md) and existing issues retain their owners.
Historical publication and board-access fields in `cereja-ui-github.json` describe
their recorded date; they do not prove current remote permissions or delivery.
