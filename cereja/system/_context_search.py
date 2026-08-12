"""Bounded textual context search for explicit repository roots."""

import os
from pathlib import Path as NativePath

from cereja.system._context.models import (
    ContextResponse,
    ContextResult,
    ContextSnippet,
    SkippedFile,
)
from cereja.system._context.query import (
    build_search_result,
    context_response_to_dict,
    finalize_response,
)
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
            result, omitted = build_search_result(
                path=normalized_path,
                root=_normalized_path(repository_file.root.path),
                relative_path=repository_file.relative_path,
                size_bytes=size_bytes,
                text=text,
                terms=terms,
                max_snippets=max_snippets,
                max_snippet_chars=max_snippet_chars,
            )
            if result is None:
                continue
            snippets_truncated = snippets_truncated or omitted
        else:
            result = ContextResult(
                path=normalized_path,
                root=_normalized_path(repository_file.root.path),
                relative_path=repository_file.relative_path,
                size_bytes=size_bytes,
                score=0,
                match_count=0,
                snippets=(),
            )

        results.append(result)

    return finalize_response(
        mode=mode,
        query=query,
        roots=normalized_roots,
        results=results,
        skipped=skipped,
        max_results=max_results,
        snippets_truncated=snippets_truncated,
    )


def _normalized_path(value):
    return NativePath(os.fspath(value)).absolute().as_posix()
