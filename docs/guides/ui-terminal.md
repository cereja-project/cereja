# Independent terminal foundation (#295, #296, #297)

`cereja.ui` is a lightweight namespace. Import `cereja.ui.terminal` for capability
policies and transactional sessions, or `cereja.ui.testing` for the virtual
backend. Neither imports `cereja.display`, starts workers, installs handlers or
acquires modes during import. The existing root exports and CLI are unchanged.

This stage implements capability resolution, backend-neutral ownership and
lifecycle, acknowledged output, a plain stream transport and a deterministic
virtual backend and explicit POSIX/Win32 transports. `StreamBackend` remains
plain even when its streams are TTYs,
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
are provided by [UI text](ui-text.md). Unknown/dumb cursor support or unavailable native
acquisition selects plain. Every effective capability retains its source in an
immutable diagnostic mapping. Invalid typed options fail before acquisition.
Windows environment hints alone do not prove usable native console/VT modes.
Cursor, palette and alternate-screen hints are resolved separately. The
monochrome fixtures `linux-m` and `xterm-mono` follow the
[ncurses terminal descriptions](https://invisible-island.net/ncurses/terminfo.src.html);
they retain navigation without implicitly enabling color. Explicit per-run
assertions remain available when the backend can acquire the asserted mode.

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
[text policy](ui-text.md) before accepting their rendering contract.

The internal `_write_frame` hook is for the future encoder, not an arbitrary
ANSI drawing API. Each positive short acknowledgment advances only by that
character count and retries the suffix. Noninteger, zero, negative or oversized
counts fail. Only a complete acknowledgment and successful flush can commit
virtual cells. An empty frame makes zero writes and zero flushes. A failure closes
the session and requires full invalidation; a broken pipe stops output cleanly
when restoration succeeds. There is no timeout guarantee for an OS write that
blocks. Actual unchanged-frame comparison belongs to #299/#300.

## Native backends and input

Import `PosixBackend` from `cereja.ui.posix` on POSIX, or `WindowsBackend` from
`cereja.ui.windows` on Windows. The toolkit namespace and root package defer these
imports. Constructing a backend does not acquire modes or start a worker.
Use it with `TerminalSession`, then call `backend.wait(timeout)` on the owning
thread. `None` waits for input or wake; finite timeouts are seconds. A worker may
call `backend.wake()` to notify that consumer. Wake notifications may coalesce;
they carry no posted payload. The application queue and admission policy remain
with #301. Call `backend.close()` after use to release owned waiting resources.
Borrowed terminal streams/handles belong to the caller.

Native reads return immutable values from `cereja.ui.events`: `KeyEvent`,
`PasteEvent`, `ResizeEvent`, `WakeEvent`, `EOFEvent` and `InputErrorEvent`.
Key text retains ordinary characters, modifiers use `shift`/`ctrl`/`alt`, and
repeat counts remain explicit. Raw Ctrl+C is a key with `key='c'`, `ctrl` and
empty text. The future application must handle it explicitly; receiving a key
does not execute commands. Paste is one text value, never shortcut replay.
Input errors must be surfaced by that application. These values supply input,
not a widget event loop, composer or Ledger application.

POSIX uses captured termios attributes, file blocking state, a selector and a
nonblocking self-pipe. It preserves and restores installed signal handlers;
external SIGINT raises `KeyboardInterrupt` so the session unwinds. SIGWINCH
coalesces a resize notification and wakes the wait. Native descriptors and
handlers are acquired under the session journal, including partial failures.
Termios configuration and handlers are restored to their captured values. Darwin
can add the transient `PENDIN` state while restoring canonical input; its
[TTY implementation](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/kern/tty.c#L1313)
owns that indicator. Tests allow only that exact addition on Darwin and compare
all remaining attributes. Restoration uses `TCSANOW` and preserves queued input;
it does not flush or consume input to clear kernel state. ANSI screen/cursor/
paste protocols return to normal screen, visible cursor and paste disabled;
the backend cannot reconstruct arbitrary prior ANSI state or screen contents.

The POSIX parser retains fragmented UTF-8 and replaces malformed encoding.
Its Escape deadline is 30 ms, configurable from 10 through 100 ms. Arrival at
the deadline follows the expired Escape event. Navigation uses the documented
[xterm key and bracketed-paste sequences](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html).
The POSIX key subset includes navigation, F1-F12 and their supported modifiers;
Windows console records additionally expose F13-F24. Recognized CSI/SS3 prefixes
wait for completion or EOF without an Escape timer, so delayed sequence suffixes
cannot become shortcuts. Encoded escape sequences are limited to 4 KiB. Paste is limited to 1 MiB of
decoded UTF-8, including replacement characters. Oversized paste is rejected
atomically and consumed through its end delimiter. Unsupported control strings
and malformed/oversized sequences are consumed without shortcut replay.
No runtime terminal-description or Unicode data downloads occur.

Windows binds typed console and event APIs. A VT mode change is attempted only
after session ownership and capture, journaled before mutation. Successful
`SetConsoleMode` enables interactive capabilities before raw input acquisition;
unsupported VT selects plain without emitting controls. Unexpected API failures
unwind the journal. This follows Microsoft's
[console mode contract](https://learn.microsoft.com/en-us/windows/console/setconsolemode).
Waiting uses console records and an application event, without a socket selector.
UTF-16 surrogate pairs survive split reads; malformed pairs become U+FFFD.
Dimensions and resize notifications use the visible viewport. Ordinary legacy
console records cannot reliably identify paste; no paste-detection guarantee is
made and requesting that unsupported protocol fails before acquisition.

Plain streams acquire no raw input, alternate screen or signal handlers. The
Windows output probe is also suppressed for redirected/unavailable streams.
Native PTY/console tests establish OS transport and restoration within their
tested host; manual emulator and SSH validation remain separate. The focused
`UI terminal transports` workflow runs these stdlib-only tests on Python 3.11-3.14
across Linux, Windows and macOS. A configured matrix establishes coverage intent;
only a successful run at the delivered commit establishes the checked result.

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
