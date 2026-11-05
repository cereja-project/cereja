"""Metadata-only large-file search, projected to bounded Cereja TUI text in its worker."""
import json
import re
from dataclasses import asdict


LIMITS = (
    ('min_size_bytes', 'Minimum size in bytes (>=0)', 0, 0),
    ('max_results', 'Retained files (>=1)', 20, 1),
    ('max_entries', 'Examined entries (>=1)', 1_000_000, 1),
    ('max_depth', 'Descent depth (>=0)', 64, 0),
    ('max_errors', 'Retained error details (>=0)', 32, 0),
)
MAX_TEXT_BYTES = 12288


def _integer(value, minimum):
    if not value.isascii() or not value.isdecimal() or int(value) < minimum:
        return f'Use an integer >= {minimum}'
    return None


def _size_bytes(value):
    error = 'Use a size such as 100 MiB or a whole number of bytes'
    if (type(value) is not str or len(value) > 1024 or not value.isascii()
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError(error)
    match = re.fullmatch(r'([0-9]+)(?:\.([0-9]+))? *(B|[KMGT]i?B)?', value.strip(' '), re.IGNORECASE)
    if match is None:
        raise ValueError(error)
    whole, fraction, unit = match.groups()
    unit = (unit or 'B').upper()
    power = 'KMGT'.index(unit[0]) + 1 if len(unit) > 1 else 0
    multiplier = (1024 if 'I' in unit else 1000) ** power
    numerator = int(whole + (fraction or '')) * multiplier
    denominator = 10 ** len(fraction or '')
    if numerator % denominator:
        raise ValueError(error)
    return numerator // denominator


def _size_error(value):
    try:
        _size_bytes(value)
    except ValueError as error:
        return str(error)
    return None


def form():
    from ._large_files_form import LargeFilesForm
    return LargeFilesForm()


def parse_limits(values):
    result = {}
    for name, _, _, minimum in LIMITS:
        value = values[name]
        if name == 'min_size_bytes':
            result[name] = _size_bytes(value)
            continue
        if _integer(value, minimum) is not None:
            raise ValueError('Invalid large-file limit')
        result[name] = int(value)
    return result


def scan(values, context):
    from cereja.system.file_sizes import find_large_files
    context.running()
    report = find_large_files(values['root'], **{name: values[name] for name, *_ in LIMITS})
    text = report_text(report)
    if not values.get('_interactive'):
        return text
    from .file_actions import capture_selection
    records, used = [], 0
    for item in report.files[:128]:
        try:
            selection = asdict(capture_selection(item.path, expected_size=item.size_bytes))
        except (OSError, ValueError):
            selection = None
        record = dict(relative=item.relative_path, size=item.size_bytes, selection=selection)
        size = len(json.dumps(record, ensure_ascii=True).encode('ascii'))
        if used + size > 28000:
            break
        records.append(record)
        used += size
    return json.dumps(dict(text=text, files=records, omitted=len(report.files) - len(records)), ensure_ascii=True)


def human_size(size):
    value = size
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB'):
        if value < 1024 or unit == 'EiB':
            return f'{value} B' if unit == 'B' else f'{value:.2f} {unit}'
        value /= 1024


def report_text(report):
    # Formatting and path escaping are worker-owned too. Do not build an
    # unbounded intermediate string from arbitrarily many retained records.
    lines = [
        'Large files | logical size (binary units) | metadata only',
        'Scan: ' + ('Complete' if report.complete else 'Incomplete: ' + ', '.join(report.reasons)),
        'Ranking covers ' + ('all observed eligible files.' if report.complete else
                             'only the examined portion; whole-root largest files are unknown.'),
        f'Examined entries: {report.examined_entries}; regular files: {report.scanned_files}; '
        f'matched files: {report.matched_files}',
        f'Results truncated: {report.results_truncated}; retained files: {len(report.files)}',
        f'Skipped links/reparse points: {report.skipped_links}; special files: {report.skipped_special}',
        f'Errors: {report.error_count}; retained details: {len(report.errors)}; '
        f'error details truncated: {report.errors_truncated}',
        'UI text cap: 12288 bytes, independent of scan and retention limits.',
        'Root: ' + json.dumps(report.root[:320], ensure_ascii=True)
        + (' [UI root display truncated]' if len(report.root) > 320 else ''),
        'Size | relative path (JSON escaped)',
    ]
    if not report.files:
        lines.append('No matching files observed.')
    marker = '\n[UI display truncated; additional file/error rows omitted. API report unchanged.]'
    size = len('\n'.join(lines).encode('utf-8'))

    def append(line):
        nonlocal size
        encoded_size = len(line.encode('utf-8')) + 1
        if size + encoded_size + len(marker) > MAX_TEXT_BYTES:
            return False
        lines.append(line)
        size += encoded_size
        return True

    for item in report.files:
        if not append(f'{human_size(item.size_bytes)} | ' + json.dumps(item.relative_path, ensure_ascii=True)):
            return '\n'.join(lines) + marker
    for error in report.errors:
        if not append(f'Error: {error.operation}; errno={error.errno}; path='
                      + json.dumps(error.path, ensure_ascii=True)):
            return '\n'.join(lines) + marker
    return '\n'.join(lines)
