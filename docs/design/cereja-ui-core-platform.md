# Independent UI core platform acceptance (#305)

Scope: terminal sessions, Unicode text, cell buffers, rendering and scheduling.
Ledger remains the selected application direction. This report does not accept
the application CLI, domain integration, legacy display migration or application
performance. The [design section 7](cereja-ui.md#7-evidence-budgets-and-release-gates)
and [#305](https://github.com/cereja-project/cereja/issues/305) own acceptance.
The issue records the final tested/self-reviewed tree, published commit, CI run
and unresolved human acceptance. Publication never closes that gate.

## Evidence and effective coverage

The existing [CI 37897559557](https://github.com/cereja-project/cereja/actions/runs/37897559557)
passed at `1747a3d650aaf93fca142806ba3f72d7eeb4f1a9`, tree
`bb5767f48b02aeec0e7069890c8e570e4c7371d9`: 208 discovered UI cases per job
(Windows: eight POSIX skips; Linux: Darwin-reference and Windows-console skips;
macOS: Windows-console skip). Its logs confirm actual Linux/macOS PTYs and
Windows hidden-console execution, not just a configured matrix. Reuse this
baseline; #305 adds six contract cases and expands the existing console probe.
The final run and its 12 per-job artifacts are linked from the issue.

| Layer / host | What its checks establish | What remains unverified |
| --- | --- | --- |
| Virtual contracts, Python 3.11-3.14 | Text conformance/safety, buffers, reference vs dirty diff, output/failure journal, ordered input, bounded queues/payloads, generations/cooperative cancellation, idle and 10,000-event fairness | OS integration, emulator presentation and human interaction |
| Linux CI (Ubuntu 24.04) and local Ubuntu 26.04 WSL2 (kernel 6.18.33.2, Python 3.14.4) | Real PTY input, fragmented UTF-8/paste, resize/SIGWINCH, rendering bytes, Ctrl+C key and external SIGINT, termios/flags/handlers, partial setup, queued input, wake/pressure/shutdown | Linux emulator/font rendering, human keyboard, SSH and real disconnection |
| macOS CI (macOS 26 arm64), Python 3.11-3.14 | Same POSIX integration, including Darwin's narrowly permitted kernel-owned PENDIN bit on canonical restoration | macOS Terminal walkthrough and human keyboard |
| Windows CI and local Windows 11 build 26200, Python 3.11.15/3.12.13/3.13.15/3.14.5 | Real separately created hidden console, Win32 input records, UTF-16, Ctrl+C record, VT writes, modes/cursor/position restoration, wake/pressure/shutdown, acknowledged rendering and static fallbacks | Visible Windows Terminal, human keyboard, ConPTY, OS Ctrl+C delivery and real disconnection |
| OS files, pipes and null device on each CI platform | Native backend selects plain despite explicit capability assertions; sanitized ASCII output, no repeated frame output, consumer reads real EOF; closed-reader failure preserves previous front and closes session | Plain backend does not become a pipe input reader; official CLI exit behavior remains outside scope |

Final discovery is 214 UI cases per job. Expected platform exclusions are nine
on Windows, two on Linux and one on macOS. Skips are exclusions, not passes.
The full four-version local Windows run and WSL run are recorded in the issue;
the CI matrix validates the final commit, including clean distribution installs.

Local WSL runs at trees `25909660c011c746215f40bd3a7f8aa3d0aa1523` and
`e71c00888665e706d504763d9fc39aa85299f799` failed the existing native pressure
probe's next-turn assertion. One sequential repeat passed; a 1,000-write OS-only
check found no immediate-readiness delay. Neither observation resolved the cause.
A bounded selector-instrumented pressure replay then reproduced two failures in
three attempts: injected turn 2, inspected turn 4, admission pauses 0; actual
selector results after injection were `[]`, then `['input']`. This establishes
that those next-turn native checks had no ready input, even after the master
write was acknowledged. It does not identify the kernel's underlying delay cause.

The corrected PTY test observes slave readiness with an independent selector
(0.5 s test watchdog), without consuming the key, before returning from injection.
The shared probe still requires inspection by the next turn and 10,000 ordered
results. Its failure now includes turn/admission diagnostics. Runtime code and
the fairness requirement are unchanged. This corrects the test's demonstrated
master-write/readiness assumption; it does not establish an OS delivery latency
bound. Earlier failures and the negative OS-only observation remain recorded.

## Native procedures and limits

The [Windows probe](../../tests/ui_windows_console_probe.py) creates no visible
window and borrows only its own `CONIN$`/`CONOUT$` handles. It records OS/Python,
viewport, UTF-8 stream encoding and effective capabilities in `windows-console.json`.
Emulator name/version remain null: none was inspected. At the local collection,
the viewport was 120x30, with VT/cursor/alternate-screen and wide-console Unicode;
legacy console paste detection is unavailable. Input is OS-injected, not typed.
The probe renders styled combining/CJK/emoji text and visible escaped source
controls, checks zero writes/flushes for an unchanged frame/cursor/session, then
uses NO_COLOR, ASCII and reduced-motion in a separately restored session.
Decorative timers are rejected; normal work is not disabled.

The resize attempt uses `SetConsoleWindowInfo` to request 119x29 and independently
reads the viewport. On this hidden host the API acknowledged it but the observed
size stayed 120x30. This is recorded as unavailable for changed-viewport validation,
not a resize pass or a demonstrated product defect. The cause is unresolved.
Other hosts retain their own measured outcome. Injected resize records validate
normalization/order only. Visible resize acceptance still needs a real walkthrough.

The [POSIX integration](../../tests/test_ui_posix.py) uses `pty.openpty`, UTF-8
streams, `TERM=xterm-256color`, and actual 40x12 -> 32x10 window sizes. It signals
SIGWINCH, checks normalized dimensions, reads flushed renderer bytes from the
master, then checks unchanged-output counters and restoration. It repeats with
NO_COLOR plus explicit ASCII/reduced-motion. `posix-pty.json` records conditions
and marks presentation unverified. Unicode cell semantics come from the pinned
policy; receiving bytes never proves the emulator displays those cells.

[Stream checks](../../tests/test_ui_streams.py) exercise actual redirected files,
subprocess pipes/EOF and null streams with `PYTHONIOENCODING=utf-8`. Consumer-owned
reads are explicit. A real anonymous pipe first confirms a front, then closes its
reader and attempts a changed frame. POSIX BrokenPipeError ends cleanly. The local
Windows CRT surfaced OSError(EINVAL), which remains observable and also ends the
session with an unknown screen and unchanged confirmed front. Virtual tests still
cover both write and flush failure, invalid/partial acknowledgements and cleanup
failures. These observations do not establish forced-disconnection restoration.

## Distribution and import isolation

Run [the distribution check](../../tools/check_ui_distribution.py) with the tested
Git tree. It exports that tree to an owned temporary build source, builds wheel
and sdist with existing build tools, rebuilds the sdist wheel offline, and installs
each into a fresh `venv --without-pip` using host pip with `--no-index --no-deps`.
Build tools (pip/setuptools/wheel) never enter the installed environments. The
probe runs with `-I` outside the checkout and requires exactly one installed
distribution, `cereja`, no Requires-Dist and Requires-Python >=3.11.

It verifies installed Unicode 17.0 generated data and Unicode License V3 byte
hashes, all raw Unicode source hashes in the sdist, deferred UI namespace imports,
no legacy/system initialization, and public renderer/scheduler examples. Imports
are guarded against attempted thread starts, process creation, signal handlers,
OS terminal opens, selector construction, termios mutation and Win32 DLL acquisition.
Silence and unchanged thread snapshots supplement those guards.

`distribution.json` preserves the source tree, artifact SHA-256, OS/interpreter,
build-tool versions and installed results. CI keeps it with the native report in
`ui-platform-<os>-py<version>`. The local Windows 3.14.5 collection passed wheel
and sdist; each final CI job repeats installation on its actual OS/interpreter.
No release or package-index installation is claimed.

```text
python -B -S -m unittest discover -s tests -p 'test_ui_*.py' -v
python -B -S tools/generate_ui_unicode.py --check
python -B tools/check_ui_distribution.py --revision TESTED_TREE --output NEW/distribution.json
```

Set `CEREJA_UI_EVIDENCE_DIR` to an owned output directory to retain native JSON.
Use a new distribution report path; the tool refuses to overwrite one. Existing
benchmark baselines, controls, profiles and negative timing results are preserved.
The 30 Hz / 4 Hz / spinner <=8 Hz policies remain policies; no sustained rate,
Ledger latency, callback preemption or OS-blocked-write timeout is established.
See [#304's report](cereja-ui-core-performance.md) for investigation budgets.

## Remaining acceptance and concrete resumption

The automated core checks support their stated conditions. Full platform
acceptance and human approval remain pending. #296/#297/#300/#301 implementations
are available in Reviewing; their human decisions remain unchanged.

Resume #305 when an authorized, visible terminal session and a human observer are
available on Windows Terminal, a Linux emulator, macOS Terminal, and an existing
SSH/ConPTY session. Use the existing public APIs/examples. For each record OS,
emulator/version, dimensions before/after, stream encoding, effective capabilities,
procedure, result and limitation. Walk through styled combining/CJK/emoji text,
resize, human input/Ctrl+C, normal/exception restoration, NO_COLOR, ASCII and
reduced-motion. Record unsupported capabilities and failures separately.
Real disconnection needs a disposable, already available test session; neither
forced termination nor a lost remote connection promises restoration.
Do not configure credentials, machines or services to fill these gaps.

This session cannot certify those observations through an OS-injected hidden
console, a PTY or CI. Keep their checkboxes open and the issue open. Review the
published automated evidence now, then record the real walkthroughs in this same
work item when the required sessions/observer are available. Application acceptance
and performance stay with their selected downstream tasks.
