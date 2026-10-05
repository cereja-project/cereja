"""Conservative terminal capabilities and a plain stream transport."""

import codecs
from dataclasses import dataclass, field
import os
import sys
from types import MappingProxyType
from typing import Literal, Mapping, TextIO


ColorDepth = Literal[0, 16, 256, 24]


def _validate_color(value: object) -> None:
    if type(value) is not int or value not in (0, 16, 256, 24):
        raise ValueError("color depth must be 0, 16, 256 or 24 (truecolor)")


@dataclass(frozen=True)
class CapabilityOptions:
    """Per-run assertions; they never turn redirected streams into terminals."""

    color: ColorDepth | None = None
    unicode: bool | None = None
    cursor: bool | None = None
    alternate_screen: bool | None = None
    paste: bool | None = None
    reduced_motion: bool | None = None

    def __post_init__(self) -> None:
        if self.color is not None:
            _validate_color(self.color)
        for name in ("unicode", "cursor", "alternate_screen", "paste",
                     "reduced_motion"):
            value = getattr(self, name)
            if value is not None and type(value) is not bool:
                raise TypeError(f"{name} must be bool or None")


@dataclass(frozen=True)
class Capabilities:
    """Effective policies with an immutable copy of their diagnostic sources."""

    input_interactive: bool = False
    output_interactive: bool = False
    color_depth: ColorDepth = 0
    unicode: bool = False
    cursor: bool = False
    alternate_screen: bool = False
    paste: bool = False
    reduced_motion: bool = False
    plain: bool = True
    sources: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_color(self.color_depth)
        for name in ("input_interactive", "output_interactive", "unicode",
                     "cursor", "alternate_screen", "paste", "reduced_motion",
                     "plain"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")
        if not self.plain and not (self.input_interactive and self.output_interactive
                                   and self.cursor):
            raise ValueError("interactive mode requires interactive streams and cursor support")
        if self.plain and (self.color_depth or self.cursor or self.alternate_screen or self.paste):
            raise ValueError("plain mode cannot enable terminal controls or color")
        if not isinstance(self.sources, Mapping):
            raise TypeError("sources must be a mapping")
        if any(not isinstance(k, str) or not isinstance(v, str)
               for k, v in self.sources.items()):
            raise TypeError("sources must map strings to strings")
        object.__setattr__(self, "sources", MappingProxyType(dict(self.sources)))


def _interactive(stream: object) -> tuple[bool, str]:
    try:
        return bool(stream.isatty()), "stream.isatty"
    except (AttributeError, OSError, ValueError, TypeError):
        return False, "safe-default"


def _unicode_output(stream: object) -> tuple[bool, str]:
    encoding = getattr(stream, "encoding", None)
    if not isinstance(encoding, str):
        return False, "safe-default"
    try:
        encoding = codecs.lookup(encoding).name
        "é─".encode(encoding, errors="strict")
    except (LookupError, UnicodeError):
        return False, "output.encoding"
    return True, "output.encoding"


def detect_capabilities(input_stream: TextIO, output_stream: TextIO,
                        options: CapabilityOptions | None = None,
                        environ: Mapping[str, str] | None = None,
                        supports_acquisition: bool = False,
                        platform: str | None = None) -> Capabilities:
    """Resolve without probes or terminal mutation.

    Only nonempty NO_COLOR is an environment override. TERM and COLORTERM are
    detection hints. Native console/VT detection belongs to later adapters;
    on Windows these hints alone do not establish usable terminal modes.
    """
    if options is None:
        options = CapabilityOptions()
    if not isinstance(options, CapabilityOptions):
        raise TypeError("options must be CapabilityOptions or None")
    if type(supports_acquisition) is not bool:
        raise TypeError("supports_acquisition must be bool")
    env = os.environ if environ is None else environ
    platform = sys.platform if platform is None else platform
    values: dict[str, object] = {}
    sources: dict[str, str] = {}
    for name, stream in (("input_interactive", input_stream),
                         ("output_interactive", output_stream)):
        values[name], sources[name] = _interactive(stream)

    term = env.get("TERM", "").lower()
    family = term.split("-", 1)[0]
    known_cursor = family in {"xterm", "screen", "tmux", "rxvt", "vt100",
                             "vt102", "vt220", "linux", "ansi"}
    if platform == "win32":
        known_cursor = False
    if known_cursor:
        color = 256 if "256color" in term else 16
        if "truecolor" in term or env.get("COLORTERM", "").lower() in {
                "truecolor", "24bit"}:
            color = 24
        values["color_depth"], sources["color_depth"] = color, "terminal-hint"
    else:
        values["color_depth"], sources["color_depth"] = 0, "safe-default"
    if env.get("NO_COLOR", ""):
        values["color_depth"], sources["color_depth"] = 0, "NO_COLOR"
    if options.color is not None:
        values["color_depth"], sources["color_depth"] = options.color, "option"

    values["unicode"], sources["unicode"] = _unicode_output(output_stream)
    values["reduced_motion"], sources["reduced_motion"] = False, "safe-default"
    for name in ("cursor", "alternate_screen", "paste"):
        # TERM establishes cursor capability, but does not assert paste protocol.
        detected = known_cursor if name != "paste" else False
        values[name] = detected
        sources[name] = "terminal-hint" if detected else "safe-default"
    for name in ("unicode", "cursor", "alternate_screen", "paste",
                 "reduced_motion"):
        override = getattr(options, name)
        if override is not None:
            values[name], sources[name] = override, "option"

    if not values["input_interactive"] or not values["output_interactive"]:
        plain_source = "noninteractive"
    elif not supports_acquisition:
        plain_source = "backend-unavailable"
    elif not values["cursor"]:
        plain_source = "cursor-unsupported"
    else:
        plain_source = None
    values["plain"] = plain_source is not None
    sources["plain"] = plain_source or "cursor-supported"
    if plain_source is not None:
        for name in ("color_depth", "cursor", "alternate_screen", "paste"):
            values[name] = 0 if name == "color_depth" else False
            sources[name] = f"plain:{plain_source}"
    return Capabilities(**values, sources=sources)


def _stream_identity(stream: object) -> object:
    try:
        fd = stream.fileno()
        stat = os.fstat(fd)
        # A terminal path unifies separate opens and descriptor aliases.
        if hasattr(os, "ttyname"):
            try:
                stat = os.stat(os.ttyname(fd))
            except OSError:
                pass
        return ("descriptor", stat.st_dev, stat.st_ino, getattr(stat, "st_rdev", 0))
    except (AttributeError, OSError, ValueError, TypeError):
        return ("stream", id(stream))


class StreamBackend:
    """Plain transport only; it makes no claim of native mode acquisition."""

    supports_acquisition = False

    def __init__(self, input_stream: TextIO | None = None,
                 output_stream: TextIO | None = None, *,
                 options: CapabilityOptions | None = None,
                 environ: Mapping[str, str] | None = None,
                 platform: str | None = None) -> None:
        self.input_stream = sys.stdin if input_stream is None else input_stream
        self.output_stream = sys.stdout if output_stream is None else output_stream
        self.identity = _stream_identity(self.output_stream)
        self.capabilities = detect_capabilities(
            self.input_stream, self.output_stream, options, environ,
            supports_acquisition=False, platform=platform)
        self.invalidated = False

    def dimensions(self) -> tuple[int, int]:
        try:
            size = os.get_terminal_size(self.output_stream.fileno())
        except (AttributeError, OSError, ValueError, TypeError):
            return 80, 24
        return max(0, size.columns), max(0, size.lines)

    def capture(self) -> dict[str, object]:
        return {}

    def acquire(self, name: str, snapshot: Mapping[str, object]) -> None:
        raise RuntimeError("StreamBackend does not support terminal acquisition")

    def restore(self, name: str, snapshot: Mapping[str, object]) -> None:
        # The plain transport has no terminal state to restore.
        return None

    def write(self, text: str) -> int:
        return self.output_stream.write(text)

    def flush(self) -> None:
        self.output_stream.flush()

    def invalidate(self) -> None:
        self.invalidated = True
