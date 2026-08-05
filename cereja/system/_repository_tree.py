"""Render filesystem trees while honoring common ``.gitignore`` rules."""

from dataclasses import dataclass
from fnmatch import fnmatchcase
import os
from pathlib import Path as NativePath

from cereja.system._path import Path

__all__ = ["render_repository_tree"]

BUILTIN_IGNORED_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
    }
)
BUILTIN_IGNORED_SUFFIXES = frozenset({".pyc", ".pyo"})


@dataclass(frozen=True, slots=True)
class _IgnoreRule:
    pattern: str
    negated: bool
    directory_only: bool
    anchored: bool
    base_parts: tuple[str, ...]


def render_repository_tree(
        path: str | os.PathLike[str] | Path = ".",
        *,
        depth: int | None = None,
) -> str:
    """Render a filtered Unicode tree for a directory."""
    root = path if isinstance(path, Path) else Path(path)
    if not root.exists:
        raise FileNotFoundError(f"Path not found: {root.path}")
    if not root.is_dir or root.is_link:
        raise NotADirectoryError(f"Path is not a directory: {root.path}")
    if depth is not None and depth < 0:
        raise ValueError("depth must be non-negative")

    lines = [f"{root.name}/"]
    _render_directory(root, root, (), 0, depth, "", lines)
    return "\n".join(lines)


def _render_directory(
        directory: Path,
        root: Path,
        inherited_rules: tuple[_IgnoreRule, ...],
        level: int,
        depth: int | None,
        prefix: str,
        lines: list[str],
) -> None:
    if depth is not None and level >= depth:
        return
    rules = inherited_rules + _load_ignore_rules(directory, root)
    entries: list[tuple[Path, bool]] = []
    for entry in directory.list_dir(include_hidden=True, raise_errors=True):
        is_directory = entry.is_dir and not entry.is_link
        if _is_builtin_ignored(entry, is_directory):
            continue
        relative_parts = _relative_parts(entry, root)
        if _is_ignored(relative_parts, is_directory, rules):
            continue
        entries.append((entry, is_directory))

    entries.sort(key=lambda item: (not item[1], item[0].name.casefold(), item[0].name))
    for index, (entry, is_directory) in enumerate(entries):
        is_last = index == len(entries) - 1
        connector = "└── " if is_last else "├── "
        suffix = "/" if is_directory else ""
        lines.append(f"{prefix}{connector}{entry.name}{suffix}")
        can_descend = depth is None or level < depth
        if is_directory and can_descend:
            child_prefix = prefix + ("    " if is_last else "│   ")
            _render_directory(entry, root, rules, level + 1, depth, child_prefix, lines)


def _load_ignore_rules(directory: Path, root: Path) -> tuple[_IgnoreRule, ...]:
    ignore_file = directory.join(".gitignore")
    if not ignore_file.exists:
        return ()

    base_parts = _relative_parts(directory, root)
    rules = []
    with open(ignore_file.path, encoding="utf-8", errors="replace") as file:
        for line in file:
            rule = _parse_ignore_rule(line, base_parts)
            if rule is not None:
                rules.append(rule)
    return tuple(rules)


def _parse_ignore_rule(line: str, base_parts: tuple[str, ...]) -> _IgnoreRule | None:
    pattern = line.strip()
    if not pattern or pattern.startswith("#"):
        return None

    negated = pattern.startswith("!")
    if negated:
        pattern = pattern[1:]
    directory_only = pattern.endswith("/")
    pattern = pattern.rstrip("/")
    anchored = pattern.startswith("/")
    if anchored:
        pattern = pattern[1:]
    if not pattern:
        return None
    return _IgnoreRule(pattern, negated, directory_only, anchored, base_parts)


def _is_builtin_ignored(entry: Path, is_directory: bool) -> bool:
    if is_directory:
        return entry.name in BUILTIN_IGNORED_DIRS
    return entry.name.lower().endswith(tuple(BUILTIN_IGNORED_SUFFIXES))


def _relative_parts(entry: Path, root: Path) -> tuple[str, ...]:
    if entry == root:
        return ()
    relative = NativePath(entry.path).relative_to(NativePath(root.path))
    return relative.parts


def _is_ignored(
        relative_parts: tuple[str, ...],
        is_directory: bool,
        rules: tuple[_IgnoreRule, ...],
) -> bool:
    ignored = False
    for rule in rules:
        if _rule_matches(rule, relative_parts, is_directory):
            ignored = not rule.negated
    return ignored


def _rule_matches(
        rule: _IgnoreRule,
        relative_parts: tuple[str, ...],
        is_directory: bool,
) -> bool:
    if rule.directory_only and not is_directory:
        return False
    if rule.base_parts and relative_parts[:len(rule.base_parts)] != rule.base_parts:
        return False
    candidate = relative_parts[len(rule.base_parts):]
    pattern_parts = tuple(part for part in rule.pattern.split("/") if part)
    if "/" not in rule.pattern and not rule.anchored:
        return bool(candidate) and _match_segments(pattern_parts, (candidate[-1],))
    return _match_segments(pattern_parts, candidate)


def _match_segments(pattern: tuple[str, ...], candidate: tuple[str, ...]) -> bool:
    if not pattern:
        return not candidate
    if pattern[0] == "**":
        return _match_segments(pattern[1:], candidate) or (
            bool(candidate) and _match_segments(pattern, candidate[1:])
        )
    return bool(candidate) and fnmatchcase(candidate[0], pattern[0]) and _match_segments(
        pattern[1:], candidate[1:]
    )
