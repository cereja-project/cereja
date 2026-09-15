# General Utilities

Cereja includes small utility helpers for arrays, dictionaries, strings, time formatting, imports, and inspection.

## Arrays

```python
import cereja as cj

data = [[1, 2, 3], [3, 3, 3]]

print(cj.array.get_shape(data))
print(cj.array.flatten(data))
print(cj.array.dotproduct([1, 2], [1, 2]))
```

## Collections

```python
import cereja as cj

items = list(range(10))
print(cj.utils.chunk(items, batch_size=3))

mapping = {"key1": "value1", "key2": "value2"}
print(cj.utils.invert_dict(mapping))
```

## Strings and Imports

```python
import cereja as cj

print(cj.utils.truncate("Cereja is useful.", k=6))
print(cj.utils.string_to_literal("[1, 2, 3]"))
print(cj.utils.import_string("cereja.file._io.FileIO"))
```

## Time Formatting

```python
import cereja.utils.time

print(cereja.utils.time.time_format(3600))
```

## Sanitized Tracebacks

Use `cj.format_safe_traceback` (also available from `cereja.utils`) to format
an exception without modifying it or capturing local variables:

```python
import cereja as cj

try:
    raise ValueError("Request failed with token example-token")
except ValueError as exc:
    report = cj.format_safe_traceback(
        exc,
        secrets=["example-token"],
        path_prefixes={"/srv/application": "<app>"},
    )
    print(report)
```

- Frame and `SyntaxError` filenames default to basenames. Configured prefixes
  preserve useful suffixes, such as `<app>/service.py`.
- Home and current-directory prefixes are included automatically. Explicit
  mappings override equivalent defaults; slash styles are equivalent and matching
  is case-sensitive. Longer prefixes win; filesystem roots are ignored.
- Messages and notes also receive literal prefix redaction, without path-boundary
  matching. Secrets are non-empty literal strings, matched case-sensitively, and
  take priority over path replacements. Pass an iterable, not a single string.
- Source is excluded by default, including `SyntaxError` source text.
  `include_source=True` includes source lines and may expose additional data.
- Causes, contexts, notes and exception groups use Python's standard formatting,
  including suppressed contexts and default group width/depth truncation.

This helper performs best-effort redaction, not automatic sensitive-data
detection. Unknown paths in messages, unspecified secrets and encoded versions
of secrets may remain. Review the output before publishing it.
