# Independent terminal foundation (#295)

`cereja.ui` is a lightweight namespace. Import `cereja.ui.terminal` for capability
policies and transactional sessions, or `cereja.ui.testing` for the virtual
backend. Neither imports `cereja.display`, starts workers, installs handlers or
acquires modes during import. The existing root exports and CLI are unchanged.

This stage implements capability resolution, backend-neutral ownership and
lifecycle, acknowledged output, a plain stream transport and a deterministic
virtual backend. POSIX input/modes/wakeup belong to #296; Win32 input/modes/wakeup
belong to #297. `StreamBackend` remains plain even when its streams are TTYs,
because it does not implement native acquisition. There is no production renderer,
widget application or `cereja ui` command yet.

## Capability resolution

`detect_capabilities` observes stdin and stdout independently. An unavailable,
closed or redirected stream cannot become interactive through an override.
The resolution order is per-run `CapabilityOptions`, nonempty `NO_COLOR`,
conservative terminal/encoding hints, then safe defaults. `NO_COLOR` affects
color alone. An explicit color assertion wins over it but cannot enable cursor
movement, raw input or controls on pipes. Color depth is 0, 16, 256 or 24
(24 represents truecolor).

Unicode/ASCII and reduced-motion policies are independent of color and navigation.
They describe renderer policies; pinned Unicode segmentation and cell metrics
are delivered by #298. Unknown/dumb cursor support or unavailable native
acquisition selects plain. Every effective capability retains its source in an
immutable diagnostic mapping. Invalid typed options fail before acquisition.
Windows environment hints alone do not prove usable native console/VT modes.

## Sessions and output

```python
from cereja.ui.terminal import StreamBackend, TerminalSession

with TerminalSession(StreamBackend()) as session:
    session.write_text("Cereja terminal foundation\n")
```

`TerminalSession` reserves a backend's terminal identity and binds output to the
entering thread. A second owner, including an alias to the same terminal, is
rejected. The backend captures its resource state before acquisition. Each
restoration is journaled before applying a resource, so a failed step that
partially mutates state is also unwound. Cleanup proceeds in reverse order and
attempts every step, including after `KeyboardInterrupt` or another exception.
Plain mode acquires no resources and schedules no animation timers.

Restoration failures are retained as `cleanup_failures`. When another failure
initiated cleanup, it remains the raised exception and receives diagnostic notes.
Otherwise `TerminalCleanupError.failures` exposes the failed restorations.
Repeated cleanup makes no additional backend calls. Forced process termination,
terminal disconnect and failed native restoration cannot promise a restored host.

`session.suspend()` restores resources while reserving ownership for external
output. On success it captures fresh state, reacquires and invalidates the full
frame. Failed suspension/reacquisition ends the session. An exception in the
suspended body is propagated without reacquiring resources.

`write_text` treats controls as ordinary untrusted data: ESC, C0/C1 and DEL become
visible ASCII escapes, tab becomes spaces and newline remains a line separator.
Unpaired surrogates become U+FFFD. This transport helper performs no layout,
grapheme segmentation or bidi rendering. Source/path views must use the full
text policy delivered in #298 before accepting their rendering contract.

The internal `_write_frame` hook is for the future encoder, not an arbitrary
ANSI drawing API. Each positive short acknowledgment advances only by that
character count and retries the suffix. Noninteger, zero, negative or oversized
counts fail. Only a complete acknowledgment and successful flush can commit
virtual cells. An empty frame makes zero writes and zero flushes. A failure closes
the session and requires full invalidation; a broken pipe stops output cleanly
when restoration succeeds. There is no timeout guarantee for an OS write that
blocks. Actual unchanged-frame comparison belongs to #299/#300.

## Virtual backend and verification boundary

`VirtualBackend` supplies injected ordered input, dimensions, monotonic test time,
operation history, captured output/cells and faults for capture, every acquisition
and restoration, write, flush and invalidation. `write_counts` injects transport
acknowledgments, including invalid values. Virtual cells are owned copies supplied
by a renderer/test; output escape sequences are not parsed into cells.
Finite `wait` advances virtual time, and queued input wakes it immediately.
An infinite idle wait returns without consuming real wall time.

The virtual backend is a test fixture. It does not implement the bounded event
queue, timers or scheduling policies owned by #301. Virtual lifecycle tests prove
the session journal and failure behavior, not OS mode restoration or emulator
compatibility. Native/PTY/real-terminal evidence remains with #296/#297/#305.

The recovered [UI-00 contract](../design/cereja-ui.md) remains the normative
product reference for these boundaries. [Recovery provenance](../design/cereja-ui-recovery.md)
keeps historical evidence separate from the current implementation.
