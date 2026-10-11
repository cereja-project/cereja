"""Immutable native-input values; importing them acquires no terminal state."""

from dataclasses import dataclass


@dataclass(frozen=True)
class KeyEvent:
    key: str
    text: str = ''
    modifiers: frozenset[str] = frozenset()
    repeat: int = 1

    def __post_init__(self):
        if not isinstance(self.key, str) or not isinstance(self.text, str):
            raise TypeError('key and text must be strings')
        if type(self.repeat) is not int or self.repeat < 1:
            raise ValueError('key repeat must be a positive integer')
        modifiers = frozenset(self.modifiers)
        if not modifiers <= {'shift', 'ctrl', 'alt'}:
            raise ValueError('unsupported key modifiers')
        object.__setattr__(self, 'modifiers', modifiers)


@dataclass(frozen=True)
class PasteEvent:
    text: str

    def __post_init__(self):
        if not isinstance(self.text, str):
            raise TypeError('paste must be text')


@dataclass(frozen=True)
class ResizeEvent:
    width: int
    height: int

    def __post_init__(self):
        if any(type(value) is not int or value < 0 for value in (self.width, self.height)):
            raise ValueError('dimensions must be nonnegative integers')


@dataclass(frozen=True)
class WakeEvent:
    pass


@dataclass(frozen=True)
class EOFEvent:
    pass


@dataclass(frozen=True)
class InputErrorEvent:
    message: str

    def __post_init__(self):
        if not isinstance(self.message, str):
            raise TypeError('input error message must be text')


@dataclass(frozen=True)
class FocusEvent:
    focused: bool


@dataclass(frozen=True)
class ProgressEvent:
    source: str
    completed: int
    total: int | None = None
    message: str = ''
    generation: int = 0


@dataclass(frozen=True)
class ResultEvent:
    source: str
    generation: int
    value: str | bytes | int | float | bool | None = None


@dataclass(frozen=True)
class TimerEvent:
    owner: str
    timer_id: int
    deadline: float
    now: float


@dataclass(frozen=True)
class QuitEvent:
    reason: str = ''


@dataclass(frozen=True)
class OperationStartedEvent:
    source: str
    generation: int
    name: str
    cancellable: bool = False


@dataclass(frozen=True)
class OperationPhaseEvent:
    source: str
    generation: int
    phase: str


@dataclass(frozen=True)
class OperationResultEvent:
    source: str
    generation: int
    state: str
    value: str | bytes | int | float | bool | None = None


@dataclass(frozen=True)
class OperationErrorEvent:
    source: str
    generation: int
    state: str
    message: str
    primary_error: str = ''
    phase: str = 'Validating'
    value: str | bytes | int | float | bool | None = None
    result_available: bool = False
