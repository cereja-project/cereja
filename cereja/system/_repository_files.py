"""Deterministic repository file traversal with ``.gitignore`` support."""

from dataclasses import dataclass
from fnmatch import fnmatchcase
import os
from pathlib import Path as NativePath

from cereja.system._path import Path

__all__ = ["RepositoryFile", "iter_repository_files"]

BUILTIN_IGNORED_DIRS = frozenset(
    {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".nox"}
)
BUILTIN_IGNORED_SUFFIXES = frozenset({".pyc", ".pyo"})


@dataclass(frozen=True, slots=True)
class RepositoryFile:
    root: Path
    path: Path
    relative_path: str


@dataclass(frozen=True, slots=True)
class _CanonicalRepositoryFile:
    root: Path
    path: Path
    relative_path: str
    canonical_path: str


@dataclass(frozen=True, slots=True)
class _IgnoreRule:
    pattern: str
    negated: bool
    directory_only: bool
    anchored: bool
    base_path: str


def iter_repository_files(roots, *, extensions=None):
    """Yield filtered files from explicit roots in deterministic order."""
    for item in _iter_repository_files_with_canonical_paths(
            roots, extensions=extensions
    ):
        yield RepositoryFile(item.root, item.path, item.relative_path)


def _iter_repository_files_with_canonical_paths(roots, *, extensions=None):
    """Yield repository files with one reusable canonical-path resolution."""
    normalized_extensions = _normalize_extensions(extensions)
    seen = set()
    seen_lexical_paths = set()
    for root_value in roots:
        root = root_value if isinstance(root_value, Path) else Path(root_value)
        _validate_root(root)
        inherited = _ancestor_ignore_rules(root)
        for file_path in _walk_files(root, inherited):
            if normalized_extensions is not None:
                if file_path.suffix.casefold() not in normalized_extensions:
                    continue
            lexical_path = os.path.normcase(os.path.abspath(file_path.path))
            if lexical_path in seen_lexical_paths:
                continue
            seen_lexical_paths.add(lexical_path)
            canonical = os.path.normcase(os.path.realpath(file_path.path))
            if canonical in seen:
                continue
            seen.add(canonical)
            relative = NativePath(file_path.path).relative_to(NativePath(root.path)).as_posix()
            yield _CanonicalRepositoryFile(
                root=root,
                path=file_path,
                relative_path=relative,
                canonical_path=canonical,
            )


def _validate_root(root):
    if not root.exists:
        raise FileNotFoundError(f"Path not found: {root.path}")
    if not root.is_dir or root.is_link:
        raise NotADirectoryError(f"Path is not a directory: {root.path}")


def _normalize_extensions(extensions):
    if extensions is None:
        return None
    normalized = set()
    for extension in extensions:
        value = str(extension).strip().casefold()
        if not value:
            raise ValueError("extensions must not contain empty values")
        normalized.add(value if value.startswith(".") else f".{value}")
    return frozenset(normalized)


def _ancestor_ignore_rules(root):
    native_root = NativePath(root.path).absolute()
    repository_root = None
    for candidate in (native_root, *native_root.parents):
        if (candidate / ".git").exists():
            repository_root = candidate
            break
    start = repository_root or native_root
    directories = [start]
    if start != native_root:
        current = start
        for part in native_root.relative_to(start).parts:
            current = current / part
            directories.append(current)
    rules = ()
    for directory in directories[:-1]:
        rules += _load_ignore_rules(Path(directory))
    return rules


def _walk_files(root, inherited_rules):
    found = []

    def visit(directory, rules):
        active_rules = rules + _load_ignore_rules(directory)
        entries = directory.list_dir(include_hidden=True, raise_errors=True)
        entries.sort(key=lambda entry: (entry.name.casefold(), entry.name))
        for entry in entries:
            is_directory = entry.is_dir and not entry.is_link
            if entry.is_link or _is_builtin_ignored(entry, is_directory):
                continue
            if _is_ignored(entry, is_directory, active_rules):
                continue
            if is_directory:
                visit(entry, active_rules)
            else:
                found.append(entry)

    visit(root, inherited_rules)
    found.sort(key=lambda item: NativePath(item.path).relative_to(NativePath(root.path)).as_posix())
    return found


def _load_ignore_rules(directory, root=None):
    ignore_file = directory.join(".gitignore")
    if not ignore_file.exists:
        return ()
    rules = []
    with open(ignore_file.path, encoding="utf-8", errors="replace") as file:
        for line in file:
            rule = _parse_ignore_rule(line, directory.path)
            if rule is not None:
                rules.append(rule)
    return tuple(rules)


def _parse_ignore_rule(line, base_path):
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
    return _IgnoreRule(pattern, negated, directory_only, anchored, base_path)


def _is_builtin_ignored(entry, is_directory):
    if is_directory:
        return entry.name in BUILTIN_IGNORED_DIRS
    return entry.name.lower().endswith(tuple(BUILTIN_IGNORED_SUFFIXES))


def _relative_parts(entry, root):
    if entry == root:
        return ()
    return NativePath(entry.path).relative_to(NativePath(root.path)).parts


def _is_ignored(entry, is_directory, rules):
    ignored = False
    entry_path = NativePath(entry.path).absolute()
    for rule in rules:
        try:
            candidate = entry_path.relative_to(NativePath(rule.base_path).absolute()).parts
        except ValueError:
            continue
        if _rule_matches(rule, candidate, is_directory):
            ignored = not rule.negated
    return ignored


def _rule_matches(rule, candidate, is_directory):
    if rule.directory_only and not is_directory:
        return False
    pattern_parts = tuple(part for part in rule.pattern.split("/") if part)
    if "/" not in rule.pattern and not rule.anchored:
        return bool(candidate) and _match_segments(pattern_parts, (candidate[-1],))
    return _match_segments(pattern_parts, candidate)


def _match_segments(pattern, candidate):
    if not pattern:
        return not candidate
    if pattern[0] == "**":
        return _match_segments(pattern[1:], candidate) or (
            bool(candidate) and _match_segments(pattern, candidate[1:])
        )
    return bool(candidate) and fnmatchcase(candidate[0], pattern[0]) and _match_segments(
        pattern[1:], candidate[1:]
    )
