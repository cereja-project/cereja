# Windows screen capture

`ScreenCapture` captures an attached monitor or a rectangular region within one
monitor, with no third-party runtime dependencies. It requires Windows 10
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

`grab()` defaults to the primary monitor. Specify either `monitor`, accepting
an id or a `ScreenMonitor`, or `region=(left, top, width, height)`. The selectors
are mutually exclusive. Region values must be integers, dimensions must be
positive, and the region must fit entirely within one attached monitor. Monitor
objects are resolved against current device bounds on each grab, so a stale
object does not silently reuse old coordinates. Invalid selectors raise
`TypeError` or `ValueError`; native failures raise `OSError`.

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

This API captures the visible desktop. It does not capture a hidden window's
private content, audio, protected video, the secure desktop, or HDR color data.
Monitor changes during a grab can cause an error. Test mixed DPI setups and
target display drivers when validating a recording application. Unit tests use
synthetic buffers and cursor images and do not establish desktop performance.
