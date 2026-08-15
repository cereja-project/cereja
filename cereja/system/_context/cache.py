"""Filesystem-backed cache orchestration for textual context search."""

import hashlib
import os
import sqlite3
from dataclasses import dataclass

from cereja.system._repository_files import iter_repository_files

from .cache_db import (
    SCHEMA_VERSION,
    DEFAULT_MAX_BYTES,
    DEFAULT_NAMESPACE,
    CacheDatabaseUnavailable,
    CachedFile,
    ContextCacheDatabase,
    FileSignature,
    default_cache_path,
)
from .models import (
    ContextCacheClearReport,
    ContextCacheInfo,
    ContextResult,
    SkippedFile,
)
from .query import (
    build_search_candidate,
    build_search_result,
    finalize_response,
    order_context_results,
    select_context_results,
)


@dataclass(frozen=True, slots=True)
class _PreparedFile:
    path: str
    root: str
    cached: CachedFile


def get_context_cache_info() -> ContextCacheInfo:
    """Return metadata for the default cache without exposing cached text."""
    path = default_cache_path()
    if not path.exists() and not ContextCacheDatabase._is_link(path):
        ContextCacheDatabase(path)._reject_orphan_sidecars()
        return ContextCacheInfo(
            path=path.absolute().as_posix(),
            schema_version=SCHEMA_VERSION,
            namespace=DEFAULT_NAMESPACE,
            database_bytes=0,
            wal_bytes=0,
            shm_bytes=0,
            roots=0,
            files=0,
            text_files=0,
            skipped_files=0,
            last_access_ns=None,
        )
    return ContextCacheDatabase.read_info(path)


def clear_context_cache() -> ContextCacheClearReport:
    """Clear only the default context-cache namespace."""
    path = default_cache_path()
    if not path.exists() and not ContextCacheDatabase._is_link(path):
        ContextCacheDatabase(path)._reject_orphan_sidecars()
        return ContextCacheClearReport(0, 0, 0, 0, 0)
    try:
        with ContextCacheDatabase(path) as database:
            return database.clear_default_namespace()
    except CacheDatabaseUnavailable:
        raise
    except (OSError, sqlite3.Error) as error:
        raise CacheDatabaseUnavailable(
            "context cache database is unavailable"
        ) from error


def _canonical_path(path):
    return os.path.normcase(os.path.realpath(os.fspath(path)))


def _path_is_within_root(path, canonical_root):
    canonical_path = _canonical_path(path)
    try:
        return os.path.commonpath((canonical_path, canonical_root)) == canonical_root
    except ValueError:
        return False


def _file_signature(path):
    stat_result = os.stat(path, follow_symlinks=False)
    return FileSignature(
        _sqlite_identifier(getattr(stat_result, "st_dev", None)),
        _sqlite_identifier(getattr(stat_result, "st_ino", None)),
        stat_result.st_size,
        stat_result.st_mtime_ns,
        stat_result.st_ctime_ns,
    )


def _sqlite_identifier(value):
    if value is None or -(2 ** 63) <= value < 2 ** 63:
        return value
    if 0 <= value < 2 ** 64:
        return value - 2 ** 64
    return None


def _read_cacheable_file(path, signature, max_file_bytes):
    """Return a verified signature and persistent content for one file."""
    signature, data = _read_stable_bytes(
        path, signature, max_file_bytes
    )
    if data is None or len(data) > max_file_bytes:
        return signature, "file_too_large", None, None
    digest = hashlib.sha256(data).hexdigest()
    state, text = _decode_file_data(data)
    return signature, state, None if text is None else text.casefold(), digest


def _cached_file_is_reusable(cached, signature, max_file_bytes):
    """Return whether cached content satisfies the current file constraints."""
    if cached is None or cached.signature != signature:
        return False
    if signature.size_bytes > max_file_bytes:
        return cached.state == "file_too_large"
    return cached.state != "file_too_large"


def _read_original_text(path, signature, max_file_bytes):
    """Return a verified signature and decoded original text."""
    signature, data = _read_stable_bytes(
        path, signature, max_file_bytes
    )
    if data is None or len(data) > max_file_bytes:
        return signature, "file_too_large", None
    state, text = _decode_file_data(data)
    return signature, state, text


def _read_stable_bytes(path, signature, max_file_bytes):
    """Read one signature-consistent file version, retrying once."""
    for attempt in range(2):
        if signature.size_bytes > max_file_bytes:
            data = None
        else:
            with open(path, "rb") as file:
                data = file.read(max_file_bytes + 1)
        post_read_signature = _file_signature(path)
        if post_read_signature == signature:
            return signature, data
        if attempt:
            raise FileNotFoundError(path)
        signature = post_read_signature
    raise AssertionError("unreachable")


def _decode_file_data(data):
    if b"\x00" in data:
        return "binary_file", None
    try:
        return "text", data.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        return "invalid_utf8", None


def _collect_cached_context(
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
        refresh_cache,
):
    """Collect context using signature-validated persistent file content."""
    root_values = tuple(roots)
    normalized_roots = tuple(_normalized_path(root) for root in root_values)
    canonical_roots = tuple(dict.fromkeys(_canonical_path(root) for root in root_values))
    cache_path = default_cache_path()
    if any(
            _path_is_within_root(cache_path, canonical_root)
            for canonical_root in canonical_roots
    ):
        raise CacheDatabaseUnavailable(
            "context cache path is inside a searched root"
        )

    # Traversal can fail for invalid roots and must complete before any scan can
    # remove stale associations.
    inventory = tuple(iter_repository_files(root_values, extensions=extensions))

    try:
        with ContextCacheDatabase(cache_path) as database:
            if _database_call(
                    database.aggregate_size_bytes
            ) > DEFAULT_MAX_BYTES:
                _database_call(
                    database.enforce_quota,
                    canonical_roots,
                    DEFAULT_MAX_BYTES,
                )
            inventory_roots = {root: False for root in canonical_roots}
            for repository_file in inventory:
                inventory_roots[_canonical_path(repository_file.root.path)] = True
            roots_to_sync = _database_call(
                database.roots_requiring_scan,
                DEFAULT_NAMESPACE,
                inventory_roots.items(),
            )
            scan_tokens = _database_call(
                database.begin_scans_if_admitted,
                DEFAULT_NAMESPACE,
                roots_to_sync,
                DEFAULT_MAX_BYTES,
            )
            prepared, transient_skips = _synchronize_inventory(
                database,
                inventory,
                canonical_roots,
                max_file_bytes,
                refresh_cache,
                DEFAULT_MAX_BYTES,
                scan_tokens,
            )
            _database_call(
                database.enforce_quota,
                canonical_roots,
                DEFAULT_MAX_BYTES,
            )
            return _query_prepared_files(
                prepared,
                transient_skips,
                mode=mode,
                query=query,
                terms=terms,
                roots=normalized_roots,
                max_results=max_results,
                max_snippets=max_snippets,
                max_snippet_chars=max_snippet_chars,
                max_file_bytes=max_file_bytes,
            )
    except sqlite3.Error as error:
        raise CacheDatabaseUnavailable(
            "context cache database is unavailable"
        ) from error


def _synchronize_inventory(
        database,
        inventory,
        canonical_roots,
        max_file_bytes,
        refresh_cache,
        max_cache_bytes,
        scan_tokens,
):
    by_root = {root: [] for root in canonical_roots}
    prepared = []
    skipped = []
    signed_files = []
    for repository_file in inventory:
        path = repository_file.path.path
        normalized_path = _normalized_path(path)
        canonical_path = _canonical_path(path)
        canonical_root = _canonical_path(repository_file.root.path)
        try:
            signature = _file_signature(path)
        except PermissionError:
            skipped.append(SkippedFile(normalized_path, "permission_denied"))
            continue
        except FileNotFoundError:
            skipped.append(SkippedFile(normalized_path, "disappeared"))
            continue
        signed_files.append((
            repository_file,
            path,
            normalized_path,
            canonical_path,
            canonical_root,
            signature,
        ))

    cached_by_path = {}
    if not refresh_cache and signed_files:
        cached_by_path = _database_call(
            database.get_cached_contents,
            (item[3] for item in signed_files),
        )

    for (
            repository_file,
            path,
            normalized_path,
            canonical_path,
            canonical_root,
            signature,
    ) in signed_files:
        try:
            cached = cached_by_path.get(canonical_path)
            if not _cached_file_is_reusable(
                    cached, signature, max_file_bytes
            ):
                signature, state, folded_text, digest = _read_cacheable_file(
                    path, signature, max_file_bytes
                )
                cached = CachedFile(
                    canonical_path=canonical_path,
                    relative_path=repository_file.relative_path,
                    signature=signature,
                    state=state,
                    folded_text=folded_text,
                    content_sha256=digest,
                )
            else:
                cached = CachedFile(
                    canonical_path=canonical_path,
                    relative_path=repository_file.relative_path,
                    signature=signature,
                    state=cached.state,
                    folded_text=cached.folded_text,
                    content_sha256=cached.content_sha256,
                )
        except PermissionError:
            skipped.append(SkippedFile(normalized_path, "permission_denied"))
            continue
        except FileNotFoundError:
            skipped.append(SkippedFile(normalized_path, "disappeared"))
            continue

        by_root[canonical_root].append(cached)
        prepared.append(_PreparedFile(
            path=normalized_path,
            root=_normalized_path(repository_file.root.path),
            cached=cached,
        ))

    if scan_tokens is None:
        return prepared, skipped
    for canonical_root, cached_files in by_root.items():
        if canonical_root not in scan_tokens:
            continue
        admitted = _database_call(
            database.commit_scan,
            scan_tokens[canonical_root],
            cached_files,
            max_bytes=max_cache_bytes,
        )
        if admitted is None:
            break
    return prepared, skipped


def _query_prepared_files(
        prepared,
        transient_skips,
        *,
        mode,
        query,
        terms,
        roots,
        max_results,
        max_snippets,
        max_snippet_chars,
        max_file_bytes,
):
    candidates = []
    candidate_signatures = {}
    skipped = list(transient_skips)
    snippets_truncated = False
    for item in prepared:
        cached = item.cached
        if cached.state != "text":
            skipped.append(SkippedFile(item.path, cached.state))
            continue
        if mode == "list":
            candidates.append(ContextResult(
                path=item.path,
                root=item.root,
                relative_path=cached.relative_path,
                size_bytes=cached.signature.size_bytes,
                score=0,
                match_count=0,
                snippets=(),
            ))
            continue

        candidate = build_search_candidate(
            path=item.path,
            root=item.root,
            relative_path=cached.relative_path,
            size_bytes=cached.signature.size_bytes,
            folded_text=cached.folded_text or "",
            terms=terms,
        )
        if candidate is not None:
            candidates.append(candidate)
            candidate_signatures[candidate.path] = cached.signature

    ordered_candidates = order_context_results(candidates, mode)
    selected = select_context_results(candidates, mode, max_results)
    if mode == "search":
        selected, reopen_skips, reopened_truncated = _reopen_winners(
            ordered_candidates,
            candidate_signatures,
            terms,
            max_snippets,
            max_snippet_chars,
            max_file_bytes,
            max_results,
        )
        skipped.extend(reopen_skips)
        snippets_truncated = snippets_truncated or reopened_truncated

    return finalize_response(
        mode=mode,
        query=query,
        roots=roots,
        results=list(selected),
        skipped=skipped,
        max_results=max_results,
        snippets_truncated=(
            snippets_truncated or len(candidates) > max_results
        ),
    )


def _reopen_winners(
        candidates,
        candidate_signatures,
        terms,
        max_snippets,
        max_snippet_chars,
        max_file_bytes,
        max_results,
):
    results = []
    skipped = []
    snippets_truncated = False
    for winner in candidates:
        if len(results) == max_results:
            break
        try:
            signature, state, text = _read_original_text(
                winner.path,
                candidate_signatures[winner.path],
                max_file_bytes,
            )
            if state != "text":
                skipped.append(SkippedFile(winner.path, state))
                continue
        except PermissionError:
            skipped.append(SkippedFile(winner.path, "permission_denied"))
            continue
        except FileNotFoundError:
            skipped.append(SkippedFile(winner.path, "disappeared"))
            continue
        result, omitted = build_search_result(
            path=winner.path,
            root=winner.root,
            relative_path=winner.relative_path,
            size_bytes=signature.size_bytes,
            text=text,
            terms=terms,
            max_snippets=max_snippets,
            max_snippet_chars=max_snippet_chars,
        )
        if result is not None:
            results.append(result)
            snippets_truncated = snippets_truncated or omitted
    return results, skipped, snippets_truncated


def _database_call(operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except (OSError, sqlite3.Error) as error:
        raise CacheDatabaseUnavailable(
            "context cache database is unavailable"
        ) from error


def _normalized_path(value):
    return os.path.abspath(os.fspath(value)).replace(os.sep, "/")
