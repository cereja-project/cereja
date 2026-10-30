"""Metadata-only large-file search, projected to bounded Cereja TUI text in its worker."""
import json
from dataclasses import asdict

from cereja.ui.overlays import FormField


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


def form():
    from .paths import PathForm
    return PathForm('large-files-form', 'Large files: metadata only', (
        FormField('root', 'Root directory', '', required=True,
                  help='Tab completes directories; arrows choose, Enter accepts. Explicit trusted directory. '
                       'Includes hidden/binary/ignored files; no content reads or links. '
                       'Run starts one worker. No Cancel or whole-scan deadline.'),
        *(FormField(name, label, str(default), required=True,
                    validator=lambda value, minimum=minimum: _integer(value, minimum),
                    help='Same parameter and default as find_large_files. Entry/depth limits bound traversal; '
                         'result/error limits bound retention. UI text has a separate 12 KiB cap.')
          for name, label, default, minimum in LIMITS),
    ), primary='Run', max_input_bytes=1024)


def parse_limits(values):
    result = {}
    for name, _, _, minimum in LIMITS:
        value = values[name]
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
