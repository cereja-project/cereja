# UI planning spikes

These standard-library-only scripts provide bounded model and native-primitive
evidence for UI-00. They do not implement `cereja.ui` or certify a terminal host.
See [the evidence assessment](../../docs/design/cereja-ui-evidence.md) for the
measured results, exclusions, and outstanding implementation gates.

## Verify the saved evidence

Run from the repository root with Python 3.11 or newer:

```text
python -B -m unittest discover -s benchmarks/ui_spikes -p "test_*.py" -v
python -B benchmarks/ui_spikes/verify.py
```

`verify.py` checks the recorded source fingerprints, workload and sample counts,
raw-sample median/p95 consistency, and recorded native/download observations.
Python sources may match exactly or after LF/CRLF conversion; the report lists
the latter separately as `source_newline_variants`. Other whitespace and source
changes are rejected. This exception applies only to known Python source files,
never raw observations. The directory attributes preserve original JSON bytes
on checkout. Four tests exercise this portability boundary.
It reads the three original JSON files without changing them. Its optional
`--output NEW_FILE` creates a new report and refuses an existing destination.
`--root CHECKOUT` supports verification from a separately staged script.
The exit code is nonzero on a detected inconsistency or an unreadable artifact.
Passing verifies the recorded evidence's consistency, not the timing's accuracy
or the behavior of an unbuilt implementation.

## Reproduce without replacing the originals

Create a new empty directory named `ui-spike-replay` outside the checkout. Run
these commands from the repository root, replacing `REPLAY_DIR` with that
directory. The existing probe writers overwrite their output argument, so never
pass an original baseline filename or an existing replay file.

```text
python -B benchmarks/ui_spikes/run.py --output REPLAY_DIR/model.json
python -B benchmarks/ui_spikes/platform_probe.py --output REPLAY_DIR/platform.json
python -B benchmarks/ui_spikes/download_probe.py --output REPLAY_DIR/download.json
```

The renderer is memory-only. `run.py` measures five operations for each of 15
workloads, with five warmups and 31 raw samples per operation, followed by a
separate traced-memory observation. Its p95 estimator selects sorted sample
index `int(n * .95)`, index 29 for 31 samples. Nine child processes measure the
existing `cereja` import, excluding process startup. Compare raw distributions
on the same runner and protocol; no model timing is a production pass threshold.

`platform_probe.py` does not change modes or read terminal input. On Windows it
calls native wait/event APIs plus a socketpair selector. Other platforms run the
socketpair portion only. `download_probe.py` starts an owned loopback HTTP server
and temporary files to test progress and one callback-exception path. It needs
local socket access, not an external service. Do not treat it as full cancellation
or hostile-network acceptance. Production transfer sources are imported from
the checkout, so keep the revision and source fingerprints with any replay.

`run.py` embeds its revision and current spike-source hashes. The original
platform report embeds neither, and `download_probe.py` does not emit the source
metadata that was added to its saved report. Capture revision and SHA-256 values
alongside new reports before using them as comparison evidence. Do not infer
missing provenance from the JSON filename or overwrite an old report to repair it.

## UI-00 reconciliation record (2026-09-21)

Source revision: `ed7fbfa5bc08f3e5814602f1cb3f09e3d6ad5d87`, with the preexisting
untracked spike sources identified by the saved SHA-256 values. Python 3.14.5
on Windows ran all nine existing model tests successfully. The read-only
[verification record](ui00-verification.json) confirms all nine recorded source
entries match, all 2,325 renderer samples recompute to their stored summaries,
and the nine root-import observations have a median of 944,700 ns.
That historical record predates the publication verifier's newline-variant field.
Run the current verifier for the checkout-specific match classification.

The verification tooling was also checked against deliberate changes to a saved
median and a recorded source hash; each was rejected. This checks the verifier's
failure path without changing the original files. Original model, platform, and
download JSON files remain byte-for-byte unchanged, bound by hashes in the record.
No new benchmark timing, native probe, or real-terminal run was performed in
this reconciliation. The previously recorded native observations remain the
available runtime evidence, with their original limitations.
