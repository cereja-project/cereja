"""Render filesystem trees while honoring common ``.gitignore`` rules."""

import os

from cereja.system._path import Path
from cereja.system._repository_files import (
    _IgnoreRule,
    _is_builtin_ignored,
    _is_ignored,
    _load_ignore_rules,
)

__all__ = ["render_repository_tree"]

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
        if _is_ignored(entry, is_directory, rules):
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

