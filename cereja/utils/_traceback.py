"""Exception formatting with explicit, best-effort redaction."""

from __future__ import annotations

import os
import re
import traceback
from collections.abc import Iterable, Mapping


def _literal_pattern(values):
    values = sorted(set(values), key=lambda value: (-len(value), value))
    return re.compile('|'.join(map(re.escape, values))) if values else None


def format_safe_traceback(
    exc: BaseException,
    *,
    secrets: Iterable[str] = (),
    path_prefixes: Mapping[str, str] | None = None,
    include_source: bool = False,
) -> str:
    r"""Return a sanitized traceback without modifying the exception.

    Frame and SyntaxError filenames use basenames, except configured prefixes
    preserve suffixes (e.g. {r'C:\project': '<project>'}). Home and cwd prefixes
    are included automatically. Explicit entries override equivalent defaults;
    slash styles are equivalent, matching is case-sensitive, longest prefix wins.
    Filesystem roots are ignored. Messages and notes use literal prefix matching.

    Non-empty literal ``secrets`` are case-sensitive and take priority over path
    replacements. Replacement labels are not recursively expanded. Source lines
    (including SyntaxError text) are omitted unless ``include_source`` is true;
    local variables are never captured. Standard chain suppression and exception
    group truncation apply.

    This is best-effort redaction, not automatic sensitive-data detection:
    unknown paths in messages and unspecified or encoded secrets may remain.
    """
    if not isinstance(exc, BaseException):
        raise TypeError('exc must be a BaseException')
    if isinstance(secrets, str):
        raise TypeError('secrets must be an iterable of strings, not a string')
    secret_values = tuple(secrets)
    if any(not isinstance(value, str) or not value for value in secret_values):
        raise ValueError('secrets must contain only non-empty strings')
    if path_prefixes is not None and not isinstance(path_prefixes, Mapping):
        raise TypeError('path_prefixes must be a mapping')

    entries = [(os.path.expanduser('~'), '<home>'), (os.getcwd(), '<cwd>')]
    if path_prefixes is not None:
        entries.extend(path_prefixes.items())
    prefixes = {}
    for prefix, label in entries:
        if not isinstance(prefix, str) or not prefix or not isinstance(label, str):
            raise ValueError('path_prefixes must map non-empty strings to strings')
        prefix = prefix.replace('\\', '/').rstrip('/')
        if prefix and not re.fullmatch(r'[A-Za-z]:', prefix):
            prefixes[prefix] = label
    ordered_prefixes = sorted(prefixes, key=lambda value: (-len(value), value))
    replacements = {}
    for prefix, label in prefixes.items():
        replacements[prefix] = label
        replacements[prefix.replace('/', '\\')] = label
    path_pattern = _literal_pattern(replacements)
    secret_pattern = _literal_pattern(secret_values)

    def redact_paths(value):
        if path_pattern is None:
            return value
        return path_pattern.sub(lambda match: replacements[match.group()], value)

    def redact(value):
        # Protect secret spans before matching paths: an earlier path match must
        # not consume the start of a secret and expose its remaining suffix.
        if secret_pattern is None:
            return redact_paths(value)
        parts = []
        start = 0
        for match in secret_pattern.finditer(value):
            parts.extend((redact_paths(value[start:match.start()]), '<redacted>'))
            start = match.end()
        parts.append(redact_paths(value[start:]))
        return ''.join(parts)

    def filename(value):
        # Redact secrets before shortening a path, which could otherwise leave
        # part of a secret that crosses a directory separator.
        if secret_pattern is not None:
            value = secret_pattern.sub('<redacted>', value)
        normalized = value.replace('\\', '/')
        for prefix in ordered_prefixes:
            if normalized == prefix or normalized.startswith(prefix + '/'):
                # Apply the label only in the final redaction pass.
                return normalized
        return normalized.rsplit('/', 1)[-1]

    snapshot = traceback.TracebackException.from_exception(
        exc, capture_locals=False, lookup_lines=include_source
    )
    pending = [snapshot]
    visited = set()
    while pending:
        current = pending.pop()
        if id(current) in visited:
            continue
        visited.add(id(current))
        current.stack = traceback.StackSummary.from_list([
            traceback.FrameSummary(
                filename(frame.filename), frame.lineno, frame.name,
                lookup_line=False, line=frame.line if include_source else '',
            )
            for frame in current.stack
        ])
        # SyntaxError stores these outside StackSummary, even without a traceback.
        if getattr(current, 'filename', None) is not None:
            current.filename = filename(current.filename)
        if not include_source and hasattr(current, 'text'):
            current.text = None
        pending.extend(child for child in (
            current.__cause__, current.__context__, *(current.exceptions or [])
        ) if child is not None)
    return redact(''.join(snapshot.format()))
