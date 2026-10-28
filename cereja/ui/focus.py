"""Explicit UI-owned focus scopes; editing/selection remain in their owners."""

from dataclasses import dataclass
import threading

__all__ = ['FocusTarget', 'FocusScope', 'FocusManager', 'focus_markers']


def _identity(value):
    if not isinstance(value, str) or not value:
        raise ValueError('identity must be nonempty text')


def focus_markers(focused: bool, selected: bool) -> str:
    """Separate ASCII focus (>) and navigation/textual selection (*) markers."""
    if type(focused) is not bool or type(selected) is not bool:
        raise TypeError('marker states must be bool')
    return ('>' if focused else ' ') + ('*' if selected else ' ')


@dataclass(frozen=True, slots=True)
class FocusTarget:
    identity: str
    enabled: bool = True
    visible: bool = True

    def __post_init__(self):
        _identity(self.identity)
        if type(self.enabled) is not bool or type(self.visible) is not bool:
            raise TypeError('enabled and visible must be bool')


@dataclass(frozen=True, slots=True)
class FocusScope:
    identity: str
    targets: tuple[FocusTarget, ...]

    def __post_init__(self):
        _identity(self.identity)
        targets = tuple(self.targets)
        if any(not isinstance(target, FocusTarget) for target in targets):
            raise TypeError('scope targets must be FocusTarget')
        if len({target.identity for target in targets}) != len(targets):
            raise ValueError('target identities must be unique in a scope')
        object.__setattr__(self, 'targets', targets)

    @property
    def eligible(self):
        return tuple(target.identity for target in self.targets if target.enabled and target.visible)


def _restore(previous, scope, identity):
    eligible = scope.eligible
    if identity in eligible:
        return identity
    old = tuple(target.identity for target in previous.targets)
    if identity in old:
        index = old.index(identity)
        for candidate in old[index + 1:] + tuple(reversed(old[:index])):
            if candidate in eligible:
                return candidate
    return eligible[0] if eligible else None


class FocusManager:
    """Top scope exclusively owns traversal; popping restores stable identity.

    The stack retains focus identity, not widget/text/form/result state. Updating
    a covered scope does not capture keys or steal top focus. Removed invokers
    choose next surviving eligible target, previous, then first/empty. max_depth
    includes the base scope and bounds retained overlay focus records.
    """

    def __init__(self, scope: FocusScope, *, max_depth: int = 16):
        if not isinstance(scope, FocusScope):
            raise TypeError('scope must be FocusScope')
        if type(max_depth) is not int or max_depth < 1:
            raise ValueError('max_depth must be a positive integer')
        self._thread = threading.get_ident()
        self._max_depth = max_depth
        self._stack = [(scope, scope.eligible[0] if scope.eligible else None)]

    def _check_thread(self):
        if threading.get_ident() != self._thread:
            raise RuntimeError('focus belongs to the UI thread')

    @property
    def scope(self):
        return self._stack[-1][0]

    @property
    def focused(self):
        return self._stack[-1][1]

    def focus(self, identity: str) -> str:
        self._check_thread()
        if identity not in self.scope.eligible:
            raise ValueError('target is not enabled and visible in the active scope')
        self._stack[-1] = (self.scope, identity)
        return identity

    def traverse(self, *, backward: bool = False) -> str | None:
        self._check_thread()
        if type(backward) is not bool:
            raise TypeError('backward must be bool')
        eligible = self.scope.eligible
        if not eligible:
            return None
        index = eligible.index(self.focused) if self.focused in eligible else 0
        return self.focus(eligible[(index + (-1 if backward else 1)) % len(eligible)])

    def push(self, scope: FocusScope, *, initial: str | None = None) -> str | None:
        self._check_thread()
        if not isinstance(scope, FocusScope):
            raise TypeError('scope must be FocusScope')
        if len(self._stack) >= self._max_depth:
            raise ValueError('focus scope depth limit reached')
        if any(saved.identity == scope.identity for saved, _ in self._stack):
            raise ValueError('scope identity is already active')
        if initial is not None and initial not in scope.eligible:
            raise ValueError('initial target is not eligible')
        selected = initial if initial is not None else scope.eligible[0] if scope.eligible else None
        self._stack.append((scope, selected))
        return selected

    def pop(self) -> str | None:
        self._check_thread()
        if len(self._stack) == 1:
            raise ValueError('cannot pop the base focus scope')
        self._stack.pop()
        return self.focused

    def update(self, scope: FocusScope) -> None:
        """Update an existing scope, including one covered by an overlay."""
        self._check_thread()
        if not isinstance(scope, FocusScope):
            raise TypeError('scope must be FocusScope')
        for index, (previous, focused) in enumerate(self._stack):
            if previous.identity == scope.identity:
                self._stack[index] = (scope, _restore(previous, scope, focused))
                return
        raise ValueError('scope is not active')
