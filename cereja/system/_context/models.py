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


@dataclass(frozen=True, slots=True)
class ContextCacheInfo:
    path: str
    schema_version: int
    namespace: str
    database_bytes: int
    wal_bytes: int
    shm_bytes: int
    roots: int
    files: int
    text_files: int
    skipped_files: int
    last_access_ns: int | None


@dataclass(frozen=True, slots=True)
class ContextCacheClearReport:
    associations_removed: int
    roots_removed: int
    files_removed: int
    before_bytes: int
    after_bytes: int


class ContextCacheWarning(RuntimeWarning):
    """Warn that context search continued without its optional cache."""
