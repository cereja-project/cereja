"""Deterministic virtual transport, without an ANSI parser or cell renderer."""

from collections import deque
from copy import deepcopy
from dataclasses import replace
import math
import threading
from typing import Callable, Iterable, Mapping

from ._capabilities import Capabilities, CapabilityOptions, detect_capabilities


_RESOURCES = ("output_mode", "input_mode", "alternate_screen", "cursor",
              "paste", "signal_handlers")


class _VirtualStream:
    encoding = "utf-8"

    def __init__(self, interactive: bool) -> None:
        self.interactive = interactive

    def isatty(self) -> bool:
        return self.interactive


class VirtualBackend:
    """Backend with caller-controlled inputs, dimensions, time and failures.

    Failure keys name operations, including ``acquire:cursor`` and
    ``restore:paste``. A failure may be a BaseException instance or class, a
    callable, or a sequence of those actions (None consumes a successful step).
    Values in ``write_counts`` simulate acknowledgements, including invalid ones
    for the session to reject. Integers in the ``write`` plan simulate partial writes.
    Faults occur before that operation mutates state; all attempts are logged.
    """

    supports_acquisition = True

    def __init__(self, *, capabilities: Capabilities | None = None,
                 input_interactive: bool = True, output_interactive: bool = True,
                 options: CapabilityOptions | None = None,
                 size: tuple[int, int] | Callable[[], tuple[int, int]] = (80, 24),
                 identity: object | None = None,
                 clock: Callable[[], float] | None = None,
                 input_events: Iterable[object] = (),
                 failures: Mapping[str, object] | None = None,
                 write_counts: Iterable[object] = ()) -> None:
        if type(input_interactive) is not bool or type(output_interactive) is not bool:
            raise TypeError("interactivity must be bool")
        if capabilities is not None and not isinstance(capabilities, Capabilities):
            raise TypeError("capabilities must be Capabilities or None")
        if capabilities is not None and options is not None:
            raise ValueError("pass capabilities or options, not both")
        if capabilities is None:
            if options is not None and not isinstance(options, CapabilityOptions):
                raise TypeError("options must be CapabilityOptions or None")
            virtual_options = options or CapabilityOptions()
            if virtual_options.paste is None:
                virtual_options = replace(virtual_options, paste=True)
            capabilities = detect_capabilities(
                _VirtualStream(input_interactive), _VirtualStream(output_interactive),
                virtual_options, {"TERM": "xterm-256color"}, supports_acquisition=True,
                platform="virtual")
            if not capabilities.plain and (options is None or options.paste is None):
                sources = dict(capabilities.sources)
                sources["paste"] = "virtual-known"
                capabilities = replace(capabilities, sources=sources)
        self.capabilities = capabilities
        self.identity = object() if identity is None else identity
        self.operations: list[tuple] = []
        self.resources = dict.fromkeys(_RESOURCES, False)
        self.failures = dict(failures or {})
        self._size = size
        if not callable(size):
            self._validate_dimensions(size)
        self._clock = clock
        self._elapsed = 0.0
        self._input = deque(input_events)
        self._wake = threading.Event()
        self._write_counts = deque(write_counts)
        self.writes: list[str] = []
        self.flush_count = 0
        self.invalidated = False
        self.invalidation_count = 0
        self._cells: tuple[tuple[object, ...], ...] = ()
        self._cell_frames: list[tuple[tuple[object, ...], ...]] = []

    def _step(self, operation: str, *args: object) -> object:
        if operation.startswith(("acquire:", "restore:")):
            name, resource = operation.split(":", 1)
            self.operations.append((name, resource, *args))
        else:
            self.operations.append((operation, *args))
        if operation not in self.failures:
            return None
        plan = self.failures[operation]
        if isinstance(plan, (list, tuple)):
            plan = self.failures[operation] = deque(plan)
        if isinstance(plan, deque):
            if not plan:
                return None
            action = plan.popleft()
        else:
            action = self.failures.pop(operation)
        if isinstance(action, type) and issubclass(action, BaseException):
            action = action()
        elif callable(action):
            action = action()
        if isinstance(action, BaseException):
            raise action
        return action

    @staticmethod
    def _validate_dimensions(size: object) -> tuple[int, int]:
        if not isinstance(size, (tuple, list)) or len(size) != 2:
            raise TypeError("size must be (columns, rows)")
        if any(type(value) is not int or value < 0 for value in size):
            raise ValueError("dimensions must be nonnegative integers")
        return tuple(size)

    def dimensions(self) -> tuple[int, int]:
        self._step("dimensions")
        size = self._size() if callable(self._size) else self._size
        return self._validate_dimensions(size)

    def capture(self) -> dict[str, bool]:
        self._step("capture")
        return self.resources.copy()

    def acquire(self, resource: str, snapshot: Mapping[str, bool]) -> None:
        self._step(f"acquire:{resource}")
        self.resources[resource] = True

    def restore(self, resource: str, snapshot: Mapping[str, bool]) -> None:
        self._step(f"restore:{resource}")
        self.resources[resource] = snapshot.get(resource, False)

    def write(self, text: str) -> object:
        if not isinstance(text, str):
            raise TypeError("text must be str")
        result = self._step("write", text)
        count = result if result is not None else (
            self._write_counts.popleft() if self._write_counts else len(text))
        if type(count) is int and 0 < count <= len(text):
            self.writes.append(text[:count])
        return count

    @property
    def output(self) -> str:
        return "".join(self.writes)

    def flush(self) -> None:
        self._step("flush")
        self.flush_count += 1

    def invalidate(self) -> None:
        self._step("invalidate")
        self.invalidated = True
        self.invalidation_count += 1

    def commit_cells(self, cells: Iterable[Iterable[object]]) -> None:
        rows = tuple(tuple(row) for row in cells)
        if rows and any(len(row) != len(rows[0]) for row in rows):
            raise ValueError("cells must be rectangular")
        owned = deepcopy(rows)
        self._step("commit_cells", owned)
        self._cells = owned
        self._cell_frames.append(deepcopy(owned))
        self.invalidated = False

    @property
    def cells(self) -> tuple[tuple[object, ...], ...]:
        return deepcopy(self._cells)

    @property
    def cell_frames(self) -> tuple[tuple[tuple[object, ...], ...], ...]:
        return deepcopy(tuple(self._cell_frames))

    def read_input(self) -> object | None:
        self._step("read_input")
        return self._input.popleft() if self._input else None

    def inject_input(self, *events: object) -> None:
        self._step("inject_input", *events)
        self._input.extend(events)

    @staticmethod
    def _duration(value: float) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("duration must be a number")
        if not math.isfinite(value) or value < 0:
            raise ValueError("duration must be finite and nonnegative")
        return float(value)

    def advance(self, seconds: float) -> None:
        seconds = self._duration(seconds)
        self._step("advance", seconds)
        self._elapsed += seconds

    def clock(self) -> float:
        return (self._clock() if self._clock is not None else 0.0) + self._elapsed

    def wait(self, timeout: float | None) -> bool:
        timeout = None if timeout is None else self._duration(timeout)
        self._step("wait", timeout)
        if self._input:
            return True
        if timeout is not None:
            self._elapsed += timeout
        return False

    def wake(self) -> bool:
        """Producer-safe virtual notification; wait_events consumes it."""
        self._wake.set()
        return True

    def wait_events(self, timeout: float | None, *, read_input=True) -> tuple:
        """Deterministic scheduler adapter. Existing wait/read_input stay intact.

        An infinite virtual wait records suspension and returns; real backends
        block. Use individual turns for idle fake-clock tests, not an idle run().
        """
        from .events import WakeEvent
        timeout = None if timeout is None else self._duration(timeout)
        self._step('wait_events', timeout, read_input)
        events = []
        if read_input:
            for _ in range(min(4096, len(self._input))):
                events.append(self._input.popleft())
        if self._wake.is_set():
            self._wake.clear()
            events.append(WakeEvent())
        if not events and timeout is not None:
            self._elapsed += timeout
        return tuple(events)
