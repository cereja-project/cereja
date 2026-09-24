# Windows screen capture

`ScreenCapture` captures an attached monitor, a rectangular region within one
monitor, or one selected window, with no third-party runtime dependencies. It requires Windows 10
version 1703 or newer. The public classes are available from `cereja` and
`cereja.system` on Windows only.

```python
from cereja.system import ScreenCapture

with ScreenCapture(include_cursor=True) as capture:
    monitors = capture.list_monitors()
    frame = capture.grab(monitor=monitors[0].id)
    # frame.bgra contains width * height * 4 bytes, with no BMP header.
```

`list_monitors()` returns a tuple of immutable `ScreenMonitor` values. Each has
`id` (the Windows display device string), `name`, `left`, `top`, `width`, `height`
and `is_primary`. The primary monitor is listed first. Positions use physical
pixels in the virtual desktop and can be negative.

`grab()` defaults to the primary monitor. Specify `monitor`, accepting
an id or a `ScreenMonitor`, `region=(left, top, width, height)`, or `window`,
accepting a positive integer Windows HWND. The selectors
are mutually exclusive. Region values must be integers, dimensions must be
positive, and the region must fit entirely within one attached monitor. Monitor
objects are resolved against current device bounds on each grab, so a stale
object does not silently reuse old coordinates. Invalid selectors raise
`TypeError` or `ValueError`; native failures raise `OSError`.

## Capture a background window

```python
with ScreenCapture() as capture:
    frame = capture.grab(window=selected_hwnd, only_window_content=True)
```

`only_window_content=True` captures the client area. Set it to `False` to include
the complete window bounds. Window coordinates and dimensions also use physical
pixels. A window can remain behind another application; capture does not change
focus or activation. The new API rejects minimized, closed and already
unresponsive windows instead of restoring them. Cursor inclusion is ignored in
window mode: the desktop pointer can belong to a different foreground window.

Window capture calls `PrintWindow` and never falls back to copying desktop
pixels, even when the target cannot render. The destination is cleared before
every call so partial painting cannot expose pixels from an earlier frame.
Failure raises `OSError`. Whether a particular application supplies useful
pixels depends on its rendering implementation; some applications can return
success with blank or incomplete content. This cannot be reliably inferred
from the pixel colors, since a black window can be valid content.

The capture instance records the HWND's process and thread identifiers on its
first use and verifies them before and after every capture. An observed closed
or replaced target is rejected for the remainder of that instance's lifetime.
A resize during a frame is rejected; movement is allowed. These checks cannot
prove instance identity if Windows recycles the same handle within the same
process and thread between checks. Applications should stop recording after an
error and require explicit window selection for a new recording.

`PrintWindow` is synchronous. The preflight rejects an already unresponsive
target, but the target can become unresponsive during the native call. Run
capture on a worker thread, not the UI thread; cancellation cannot interrupt a
native call in progress. See Microsoft's [PrintWindow documentation](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-printwindow)
and [window handle lifetime warning](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-iswindow).

## Frames and lifetime

The immutable `ScreenFrame` has `left`, `top`, `width`, `height` and `bgra`.
Pixels run from the top row to the bottom row, then left to right, with four
bytes per pixel in blue, green, red, alpha order. Alpha is always 255 and there
is no row padding. Each frame owns its bytes and remains usable after another
grab or after capture is closed. Cereja performs no encoding or file writes.
Consumers such as Calango can convert these bytes to their own image arrays.

Construct, use and close each capture instance on the same thread. A context
manager is recommended; `close()` is also available and idempotent. Native
resources are allocated on the first grab and reused for unchanged dimensions.
Calls temporarily select a per-monitor DPI context for the calling thread and
restore its previous context. Importing the classes neither changes process
DPI awareness nor initializes the existing keyboard, mouse or window module.

The default includes the visible system cursor, with its hotspot and native
alpha or monochrome composition. Hidden or suppressed cursors are omitted.
Animated cursors use their first image; animation timing is not reproduced.
Set `include_cursor=False` to omit the cursor.

Monitor and region mode capture the visible desktop. Window mode captures the
selected application's rendering instead. Neither mode supports audio,
protected video, the secure desktop, or HDR color data.
Monitor changes during a grab can cause an error. Test mixed DPI setups and
target display drivers when validating a recording application. Unit tests use
synthetic buffers and cursor images and do not establish desktop performance.

## Existing Window API

`Window.capture_image_bmp()` and `Window.capture_image_ppm()` delegate to this
same capture core, sharing native bindings, DIB buffers, pixel copying, DPI
handling and resource cleanup. `capture_image_bmp()` still returns raw BGRA
without a header, while an optional `filepath` writes a complete BMP file.
`capture_image_ppm()` still returns a P6 header and RGB pixels and optionally
writes them to `ppm_path`. Both support client-area and entire-window capture.
Capture errors now propagate instead of silently returning a black frame.

The legacy `Window` methods retain their existing restoration of a minimized
target before capture. Use `ScreenCapture.grab(window=...)` when capture must
not restore or activate the selected application. Window management, mouse
and keyboard methods remain separate from pixel capture.

The private Windows implementation is grouped in `cereja.system._windows`:
`constants` groups native values into operation-specific enums and flags;
`types` owns ABI types, structures and callbacks using Windows header names;
`api` owns typed DLL bindings and lazy loading; `capture` owns frames, buffers
and capture sessions.
Window, mouse and keyboard helpers consume that same native API. The existing
`_win32` and `_screen_capture` import paths remain compatibility shims. The
legacy `_win32` entrypoint retains its process DPI initialization; importing the
shared types, native API or capture implementation does not initialize DLLs or
change DPI awareness.

Keyboard timing reuses `cereja.Timer`. The legacy `_win32.Time` accessor remains
available as a compatibility adapter over that same timer.
