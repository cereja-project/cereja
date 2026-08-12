"""Direct orchestration for bounded textual context search."""

import os
import warnings
from pathlib import Path as NativePath

from cereja.system._context.cache_db import CacheDatabaseError
from cereja.system._context.models import (
    ContextCacheWarning,
    ContextResult,
    SkippedFile,
)
from cereja.system._context.query import build_search_result, finalize_response
from cereja.system._repository_files import iter_repository_files


def search_text_context(
        roots,
        query,
        *,
        extensions=None,
        max_results=10,
        max_snippets=2,
        max_snippet_chars=240,
        max_file_bytes=1_048_576,
        cache=False,
        refresh_cache=False,
):
    """Search UTF-8 text using AND terms and bounded result snippets."""
    if refresh_cache and not cache:
        raise ValueError("refresh_cache requires cache=True")
    terms = tuple(str(query).split())
    if not terms:
        raise ValueError("query must not be empty")
    _validate_limits(max_results, max_snippets, max_snippet_chars, max_file_bytes)
    return _collect_context(
        roots,
        mode="search",
        query=str(query),
        terms=tuple(term.casefold() for term in terms),
        extensions=extensions,
        max_results=max_results,
        max_snippets=max_snippets,
        max_snippet_chars=max_snippet_chars,
        max_file_bytes=max_file_bytes,
        cache=cache,
        refresh_cache=refresh_cache,
    )


def list_text_context(
        roots,
        *,
        extensions=None,
        max_results=10,
        max_file_bytes=1_048_576,
        cache=False,
        refresh_cache=False,
):
    """List bounded metadata for UTF-8 text files without returning content."""
    if refresh_cache and not cache:
        raise ValueError("refresh_cache requires cache=True")
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
        cache=cache,
        refresh_cache=refresh_cache,
    )


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
        cache,
        refresh_cache,
):
    root_values = tuple(roots)
    extension_values = None if extensions is None else tuple(extensions)
    if cache:
        from .cache import _collect_cached_context

        try:
            return _collect_cached_context(
                root_values,
                mode=mode,
                query=query,
                terms=terms,
                extensions=extension_values,
                max_results=max_results,
                max_snippets=max_snippets,
                max_snippet_chars=max_snippet_chars,
                max_file_bytes=max_file_bytes,
                refresh_cache=refresh_cache,
            )
        except CacheDatabaseError as error:
            warnings.warn(
                f"Context cache unavailable: {error}",
                ContextCacheWarning,
                stacklevel=3,
            )
    return _collect_direct_context(
        root_values,
        mode=mode,
        query=query,
        terms=terms,
        extensions=extension_values,
        max_results=max_results,
        max_snippets=max_snippets,
        max_snippet_chars=max_snippet_chars,
        max_file_bytes=max_file_bytes,
    )


def _collect_direct_context(
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
    """Inventory and read files without persistent cache."""
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


def _normalized_path(value):
    return NativePath(os.fspath(value)).absolute().as_posix()
