"""Bounded textual context search for explicit repository roots."""

from dataclasses import dataclass
import os
from pathlib import Path as NativePath

from cereja.system._repository_files import iter_repository_files

__all__ = [
    "ContextSnippet",
    "ContextResult",
    "SkippedFile",
    "ContextResponse",
    "search_text_context",
    "list_text_context",
    "context_response_to_dict",
]


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


def search_text_context(
        roots,
        query,
        *,
        extensions=None,
        max_results=10,
        max_snippets=2,
        max_snippet_chars=240,
        max_file_bytes=1_048_576,
):
    """Search UTF-8 text using AND terms and bounded result snippets."""
    terms = tuple(str(query).split())
    if not terms:
        raise ValueError("query must not be empty")
    _validate_limits(max_results, max_snippets, max_snippet_chars, max_file_bytes)
    normalized_terms = tuple(term.casefold() for term in terms)
    return _collect_context(
        roots,
        mode="search",
        query=str(query),
        terms=normalized_terms,
        extensions=extensions,
        max_results=max_results,
        max_snippets=max_snippets,
        max_snippet_chars=max_snippet_chars,
        max_file_bytes=max_file_bytes,
    )


def list_text_context(
        roots,
        *,
        extensions=None,
        max_results=10,
        max_file_bytes=1_048_576,
):
    """List bounded metadata for UTF-8 text files without returning content."""
    _validate_limits(max_results, 1, 1, max_file_bytes)
    return _collect_context(
        roots,
        mode="list",
        query=None,
        terms=(),
        extensions=extensions,
        max_results=max_results,
        max_snippets=1,
        max_snippet_chars=1,
        max_file_bytes=max_file_bytes,
    )


def _validate_limits(max_results, max_snippets, max_snippet_chars, max_file_bytes):
    values = {
        "max_results": max_results,
        "max_snippets": max_snippets,
        "max_snippet_chars": max_snippet_chars,
        "max_file_bytes": max_file_bytes,
    }
    for name, value in values.items():
        if value <= 0:
            raise ValueError(f"{name} must be greater than zero")


def _collect_context(
        roots,
        *,
        mode,
        query,
        terms,
        extensions,
        max_results,
        max_snippets,
        max_snippet_chars,
        max_file_bytes,
):
    root_values = tuple(roots)
    normalized_roots = tuple(_normalized_path(root) for root in root_values)
    results = []
    skipped = []
    snippets_truncated = False
    for repository_file in iter_repository_files(root_values, extensions=extensions):
        path = repository_file.path.path
        normalized_path = _normalized_path(path)
        try:
            size_bytes = os.path.getsize(path)
            if size_bytes > max_file_bytes:
                skipped.append(SkippedFile(normalized_path, "file_too_large"))
                continue
            with open(path, "rb") as file:
                data = file.read(max_file_bytes + 1)
        except PermissionError:
            skipped.append(SkippedFile(normalized_path, "permission_denied"))
            continue
        except FileNotFoundError:
            skipped.append(SkippedFile(normalized_path, "disappeared"))
            continue
        if len(data) > max_file_bytes:
            skipped.append(SkippedFile(normalized_path, "file_too_large"))
            continue
        if b"\x00" in data:
            skipped.append(SkippedFile(normalized_path, "binary_file"))
            continue
        try:
            text = data.decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError:
            skipped.append(SkippedFile(normalized_path, "invalid_utf8"))
            continue

        if mode == "search":
            folded_text = text.casefold()
            counts = tuple(folded_text.count(term) for term in terms)
            if not all(counts):
                continue
            match_count = sum(counts)
            filename = repository_file.path.name.casefold()
            filename_hits = sum(term in filename for term in terms)
            score = filename_hits * 1000 + match_count
            snippets, omitted = _extract_snippets(
                text, terms, max_snippets, max_snippet_chars
            )
            snippets_truncated = snippets_truncated or omitted
        else:
            match_count = 0
            score = 0
            snippets = ()

        results.append(ContextResult(
            path=normalized_path,
            root=_normalized_path(repository_file.root.path),
            relative_path=repository_file.relative_path,
            size_bytes=size_bytes,
            score=score,
            match_count=match_count,
            snippets=snippets,
        ))

    if mode == "search":
        results.sort(key=lambda item: (-item.score, item.path.casefold(), item.path))
    else:
        results.sort(key=lambda item: (item.path.casefold(), item.path))
    results_truncated = len(results) > max_results
    return ContextResponse(
        schema_version=1,
        mode=mode,
        query=query,
        roots=normalized_roots,
        results=tuple(results[:max_results]),
        skipped=tuple(sorted(skipped, key=lambda item: (item.path.casefold(), item.path))),
        truncated=results_truncated or snippets_truncated,
    )


def _extract_snippets(text, terms, max_snippets, max_snippet_chars):
    matching = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        folded_line = line.casefold()
        if any(term in folded_line for term in terms):
            matching.append(ContextSnippet(line_number, line[:max_snippet_chars]))
    return tuple(matching[:max_snippets]), len(matching) > max_snippets


def _normalized_path(value):
    return NativePath(os.fspath(value)).absolute().as_posix()


def context_response_to_dict(response):
    """Convert a context response into the stable JSON schema version 1."""
    return {
        "schema_version": response.schema_version,
        "mode": response.mode,
        "query": response.query,
        "roots": list(response.roots),
        "results": [
            {
                "path": item.path,
                "root": item.root,
                "relative_path": item.relative_path,
                "size_bytes": item.size_bytes,
                "score": item.score,
                "match_count": item.match_count,
                "snippets": [
                    {"line": snippet.line, "text": snippet.text}
                    for snippet in item.snippets
                ],
            }
            for item in response.results
        ],
        "skipped": [
            {"path": item.path, "reason": item.reason}
            for item in response.skipped
        ],
        "truncated": response.truncated,
    }
