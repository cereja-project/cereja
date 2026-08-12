"""Data models for textual context search."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ContextSnippet:
    line: int
    text: str


@dataclass(frozen=True, slots=True)
class ContextResult:
    path: str
    root: str
    relative_path: str
    size_bytes: int
    score: int
    match_count: int
    snippets: tuple[ContextSnippet, ...]


@dataclass(frozen=True, slots=True)
class SkippedFile:
    path: str
    reason: str


@dataclass(frozen=True, slots=True)
class ContextResponse:
    schema_version: int
    mode: str
    query: str | None
    roots: tuple[str, ...]
    results: tuple[ContextResult, ...]
    skipped: tuple[SkippedFile, ...]
    truncated: bool


class ContextCacheWarning(RuntimeWarning):
    """Warn that context search continued without its optional cache."""
