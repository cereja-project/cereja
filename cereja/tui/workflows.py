"""Explicit Cereja TUI domain adapters; no service calls at discovery/import time."""
import os
from pathlib import Path
import time
from urllib.parse import urlsplit

from cereja.ui.overlays import FormField, ParameterForm, ReviewTarget
from .model import bounded_text


def forms():
    from .large_files import form as large_files_form
    return {
        'large-files': large_files_form(),
        'context': ParameterForm('context-form', 'Context: owned stable root, cache off', (
            FormField('root', 'Root directory', '', required=True),
            FormField('query', 'Query (AND terms)', '', required=True),
        ), primary='Run', max_input_bytes=1024),
        'compress': ParameterForm('archive-form', 'Archives: new destination only, no replacement', (
            FormField('action', 'Action: compress or decompress', 'compress', required=True,
                      validator=lambda v: None if v in ('compress', 'decompress') else 'Use compress or decompress'),
            FormField('mode', 'Mode: file or directory', 'file', required=True,
                      validator=lambda v: None if v in ('file', 'directory') else 'Use file or directory'),
            FormField('source', 'Source', '', required=True),
            FormField('destination', 'New destination', '', required=True),
        ), primary='Review', max_input_bytes=1024),
        'download': ParameterForm('download-form', 'Download: HTTP(S), 16 MiB maximum', (
            FormField('url', 'URL (no credentials)', '', required=True),
            FormField('destination', 'New destination', '', required=True),
        ), primary='Review', max_input_bytes=1024),
    }


def _explicit_path(value):
    if type(value) is not str or not value.strip() or len(value.encode('utf-8')) > 1024:
        raise ValueError('Explicit path required (1024 bytes maximum)')
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('Control characters are unsupported in form paths')
    return os.path.abspath(value)


def prepare(name, values):
    """Pure lexical review preparation. Filesystem/network validation is worker-owned."""
    result = dict(values)
    if name == 'large-files':
        from .large_files import parse_limits
        return dict(root=_explicit_path(values['root']), **parse_limits(values)), None
    if name == 'context':
        result['root'] = _explicit_path(values['root'])
        if not values['query'].strip() or len(values['query']) > 256:
            raise ValueError('Query must contain 1..256 characters')
        return result, None
    result['destination'] = _explicit_path(values['destination'])
    if name == 'compress':
        if values['action'] not in ('compress', 'decompress') or values['mode'] not in ('file', 'directory'):
            raise ValueError('Unsupported archive action/mode')
        result['source'] = _explicit_path(values['source'])
        source = result['source']
        action = values['action'] + ' ' + values['mode']
        kind = 'directory' if values['mode'] == 'directory' and values['action'] == 'decompress' else 'file'
        policy = 'Bounded unencrypted zlib CJZ; directory output CJZD/3, input CJZD/2 or /3; no merge/replacement'
    elif name == 'download':
        url = values['url']
        parts = urlsplit(url)
        if (parts.scheme not in ('http', 'https') or not parts.hostname or parts.username is not None
                or parts.password is not None or parts.fragment or len(url) > 2048
                or any(ord(c) <= 32 or ord(c) == 127 for c in url)):
            raise ValueError('Use HTTP(S) URL without credentials, fragment or whitespace')
        source, action, kind = url, 'download', 'file'
        policy = '16 MiB maximum; 10s I/O timeout; TLS verified; at most 5 redirects; no replacement'
    else:
        raise ValueError('Unknown workflow')
    target = ReviewTarget(action, source, result['destination'], kind,
                          'Create exactly this destination after successful staging; preserve existing targets',
                          policy, 'bounded-v1', True)
    return result, target


def context_search(values, context):
    from cereja.system.repository import RepositoryTree
    from cereja.system import search_text_context
    from cereja.system._context.models import ContextResponse
    root = values['root']
    context.running()
    # Admission rejects broad/deep roots before invoking the existing API. This
    # does not turn that API into a hard-bound scanner under concurrent mutation.
    with RepositoryTree(root, max_depth=8, max_nodes=257,
                        max_work=2048, max_directory_entries=256) as tree:
        pending = [tree.root_node]
        files = total = 0
        while pending:
            node = pending.pop()
            page = tree.children(node.id, page_size=512)
            if not page.complete:
                raise ValueError('Context root exceeds admission bounds or is unavailable')
            for child in page.nodes:
                if child.kind == 'directory':
                    pending.append(child)
                elif child.kind == 'file':
                    files += 1
                    total += (Path(root) / child.relative_path).stat().st_size
                    if files > 64 or total > 16 * 1024 * 1024:
                        raise ValueError('Context supports up to 64 files / 16 MiB inventoried source bytes')
    response = search_text_context((root,), values['query'], max_results=8, max_snippets=2,
                                   max_snippet_chars=240, max_file_bytes=262144, cache=False)
    if type(response) is not ContextResponse:
        raise TypeError('Context adapter requires ContextResponse')
    lines = ['Context search | cache off | no file writes',
             'Admission checked; scan has no hard bound under concurrent source changes.',
             'Result/snippet caps do not imply complete search. Truncated: ' + str(response.truncated)]
    for hit in response.results:
        lines.append('\nPath: ' + hit.path)
        lines.append('Matches: ' + str(hit.match_count))
        lines.extend(str(snippet.line) + ': ' + snippet.text for snippet in hit.snippets)
    if not response.results:
        lines.append('No matches')
    lines.extend('Skipped: ' + item.path + ' (' + item.reason + ')' for item in response.skipped[:32])
    if len(response.skipped) > 32:
        lines.append('Skipped list truncated')
    return bounded_text('\n'.join(lines), 12288)[0]


def archive(values, context):
    from cereja.hashtools.archive import (
        file_archive, create_directory_archive, extract_directory_archive,
    )
    context.running()
    started = time.monotonic()
    if values['mode'] == 'file':
        result = file_archive(values['source'], values['destination'],
                              extract=values['action'] == 'decompress', committing=context.committing)
    else:
        operation = create_directory_archive if values['action'] == 'compress' else extract_directory_archive
        result = operation(values['source'], values['destination'], committing=context.committing)
    return bounded_text(f"Published: {result.destination}\nMembers: {result.members}\n"
                        f"Reported bytes: {result.expanded_bytes}\nDuration: {time.monotonic() - started:.3f}s\n"
                        'New destination only. No source deletion, merge or replacement.', 12288)[0]


def download(values, context):
    from cereja.http import Client
    from cereja.transfers import download as transfer
    from cereja.system._safe_paths import new_destination
    destination = new_destination(values['destination'])
    context.running()
    started = time.monotonic()
    def progress(event):
        # Unknown/misleading totals do not produce a determinate percentage.
        context.progress(event.bytes_transferred, total=None, reliable_total=False,
                         message='Downloaded bytes; total not asserted')
    with Client(timeout=10, max_redirects=5, retries=0) as client:
        result = transfer(values['url'], destination, client=client, timeout=10,
                          max_bytes=16 * 1024 * 1024, overwrite=False,
                          progress=progress, before_commit=context.committing)
    return bounded_text(f"Published: {destination}\nDownloaded bytes: {result.bytes_transferred}\n"
                        f"Duration: {time.monotonic() - started:.3f}s\n"
                        'I/O timeouts are not a whole-operation deadline. No Cancel.', 12288)[0]


def execute(name, values, context):
    if name == 'large-files':
        from .large_files import scan
        return scan(dict(values, _interactive=True), context)
    if name == 'context':
        return context_search(values, context)
    if name == 'compress':
        return archive(values, context)
    if name == 'download':
        return download(values, context)
    raise ValueError('Unknown workflow')


_REFUSALS = frozenset((
    'Selected file changed; scan again before acting',
    'Explicit destination file path required',
    'Cross-volume moves are unsupported; copy, verify the destination, then delete the source',
    'Destination was linked, but source was not removed; inspect both paths before retrying',
    'Context root exceeds admission bounds or is unavailable',
    'Context supports up to 64 files / 16 MiB inventoried source bytes',
    'Destination exists; replacement is unsupported',
    'Links/reparse paths are unsupported',
    'Expected ordinary file', 'Expected ordinary directory',
    'Archive input byte limit', 'Source byte limit', 'Expanded byte limit',
    'Compressed output byte limit', 'Compressed byte limit',
    'Archive member-count limit', 'Member-count limit', 'Member byte limit',
    'Aggregate expanded byte limit', 'Archive depth limit',
    'Archive member path exceeds bounds', 'Unsupported archive member path',
    'Normalized archive collision', 'Normalized parent/member collision',
    'Links are unsupported', 'Special archive members are unsupported',
    'Destination must be outside source tree', 'Source changed during archiving',
    'Exclusive directory publication currently requires Windows',
    'Bounded file extraction supports unencrypted zlib CJZ only',
    'Bounded directory extraction supports zlib only',
    'Unsupported directory archive format', 'Unsupported archive member type',
    'Duplicate or normalized member collision', 'File/directory conflict',
    'Truncated stream or trailing compressed data', 'Trailing archive bytes',
    'Truncated stream or size mismatch', 'Download byte limit',
    'Negative response length', 'Response length mismatch',
))


def failure_text(message):
    # Only fixed domain refusals are safe to publish. HTTP/OS exception arguments
    # can contain credentials, paths or server-provided text and stay omitted.
    for kind in ('ValueError: ', 'FileExistsError: '):
        if message.startswith(kind) and message[len(kind):] in _REFUSALS:
            return 'Refused: ' + message[len(kind):] + '. No success is claimed.'
    return ('Operation failed. Review input, supported limits, destination and permissions. '
            'If failure occurred during publication or cleanup, inspect the exact destination; '
            'an output may exist. Diagnostic details omitted; no success is claimed.')



def highlight_spans(text, terms):
    """Map casefold matches back to safe display text offsets, never markup."""
    folded = []
    owners = []
    for index, char in enumerate(text):
        value = char.casefold()
        folded.append(value)
        owners.extend([index] * len(value))
    value = ''.join(folded)
    spans = []
    for term in terms:
        term = term.casefold()
        start = 0
        if not term:
            continue
        while (found := value.find(term, start)) >= 0:
            spans.append((owners[found], owners[found + len(term) - 1] + 1))
            start = found + len(term)
    return tuple(spans)
