# Persistent Context Cache

The `cereja context` commands can use an optional persistent SQLite cache to
avoid reading, decoding, and normalizing unchanged files on every call. The
cache is disabled by default, so existing commands retain their original
behavior unless `--cache` or `cache=True` is supplied.

The searched source files are opened read-only and are never modified. When
enabled, the feature writes a global per-user cache outside the searched
roots.

## Search with the Cache

Enable the cache with `--cache`:

```bash
cereja context search \
  --root path/to/project \
  --query "authentication token" \
  --cache
```

The first call populates the cache. Later calls reuse entries whose filesystem
signatures have not changed. Search results, scores, ordering, snippets, and
skipped-file reporting remain equivalent to a direct search.

Multiple roots and extension filters work normally:

```bash
cereja context search \
  --root docs \
  --root cereja \
  --query "context cache" \
  --extension md \
  --extension py \
  --cache
```

Use `--format json` when the result will be consumed by another command:

```bash
cereja context search \
  --root . \
  --query "context cache" \
  --cache \
  --format json
```

## List Files with the Cache

The list command supports the same opt-in cache:

```bash
cereja context list --root path/to/project --cache
```

It returns file metadata without exposing cached content.

## Refresh the Current Scope

Use `--refresh-cache` to ignore reusable entries and reprocess the roots and
extensions selected by the current command:

```bash
cereja context search \
  --root path/to/project \
  --query "authentication token" \
  --cache \
  --refresh-cache
```

`--refresh-cache` requires `--cache`. Refreshing one scope does not rebuild
unrelated cached roots.

## Inspect the Cache

Display the cache path, physical sizes, schema version, file counts, root
count, and last-access time:

```bash
cereja context cache info
```

For structured output:

```bash
cereja context cache info --format json
```

The information command reports metadata only. It does not expose cached file
content or provide arbitrary database access.

## Clear the Cache

Clear the default context-cache namespace:

```bash
cereja context cache clear
```

Request a structured removal and size report with:

```bash
cereja context cache clear --format json
```

The report includes removed associations, roots, files, and physical bytes
before and after maintenance. A lock or post-commit maintenance failure is
reported as an error instead of being presented as a complete success.

## Python API

Enable caching with `cache=True`:

```python
from cereja.system import search_text_context

response = search_text_context(
    ["path/to/project"],
    "authentication token",
    cache=True,
)

for result in response.results:
    print(result.relative_path, result.score)
```

Force reprocessing for the current scope with `refresh_cache=True`:

```python
response = search_text_context(
    ["path/to/project"],
    "authentication token",
    cache=True,
    refresh_cache=True,
)
```

The list API accepts the same cache options:

```python
from cereja.system import list_text_context

response = list_text_context(
    ["path/to/project"],
    cache=True,
)
```

Inspect or clear the cache programmatically:

```python
from cereja.system import clear_context_cache, get_context_cache_info

info = get_context_cache_info()
print(info.path, info.database_bytes)

report = clear_context_cache()
print(report.files_removed, report.after_bytes)
```

Passing `refresh_cache=True` without `cache=True` raises `ValueError`.

## Storage Location and Limit

The default database path depends on the operating system:

- Windows: `%LOCALAPPDATA%\Cereja\cache\context.sqlite3`
- Linux: `$XDG_CACHE_HOME/cereja/context.sqlite3`, or
  `~/.cache/cereja/context.sqlite3`
- macOS: `~/Library/Caches/Cereja/context.sqlite3`

The physical limit is 256 MiB across the main database, WAL, and shared-memory
files. Under pressure, the cache removes least-recently-used roots and
unreferenced file records. Roots involved in the current operation are
protected from eviction. If the active scope cannot be admitted within the
limit, the result remains complete by using the direct in-memory data for the
files that were not cached.

## Failure and Safety Behavior

Search and list operations treat the cache as an optimization. If it is
unavailable, Cereja emits `ContextCacheWarning` and repeats the operation using
the direct filesystem flow.

The cache refuses unsafe directories, symbolic links, unknown database
identities, unsupported schemas, recognized corruption, and observable SQLite
WAL or shared-memory sidecars. These cases are handled conservatively: Cereja
does not automatically replace, rename, remove, or repair the existing storage.

Administrative operations are stricter. For example, `clear` reports a cache
lock as an error because pretending that an explicit cleanup succeeded would
be misleading.

## When to Use It

The cache is useful for repeated searches over stable or moderately changing
repositories. Direct mode can be preferable for a one-off search, a very small
directory, or an environment where persistent per-user storage is unwanted.

