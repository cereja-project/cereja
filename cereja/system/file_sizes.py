"""Find large regular files using filesystem metadata only (Python 3.11+)."""

from dataclasses import dataclass
import errno
import heapq
import os
from pathlib import Path
import stat

__all__ = ['FileSize', 'FileSizeError', 'FileSizeReport', 'find_large_files']


@dataclass(frozen=True, slots=True)
class FileSize:
    path: str
    relative_path: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class FileSizeError:
    path: str
    operation: str
    errno: int | None


@dataclass(frozen=True, slots=True)
class FileSizeReport:
    root: str
    files: tuple[FileSize, ...]
    complete: bool
    reasons: tuple[str, ...]
    results_truncated: bool
    examined_entries: int
    scanned_files: int
    matched_files: int
    skipped_links: int
    skipped_special: int
    error_count: int
    errors: tuple[FileSizeError, ...]
    errors_truncated: bool


class _HeapFile:
    """The least desirable retained file comes first: smaller, then later path."""

    __slots__ = ('file',)

    def __init__(self, file):
        self.file = file

    def __lt__(self, other):
        if self.file.size_bytes != other.file.size_bytes:
            return self.file.size_bytes < other.file.size_bytes
        return self.file.relative_path > other.file.relative_path


def _is_link(metadata):
    # Reject all Windows reparse points, including junctions, conservatively.
    return (stat.S_ISLNK(metadata.st_mode)
            or bool(getattr(metadata, 'st_file_attributes', 0) & 0x400))


def _check_directory(path):
    # Check lexical ancestors too: lstat of the final component alone would
    # still follow a linked parent. These separate OS calls are not race-proof.
    for component in (*reversed(path.parents), path):
        metadata = os.stat(component, follow_symlinks=False)
        if _is_link(metadata) or not stat.S_ISDIR(metadata.st_mode):
            raise NotADirectoryError(errno.ENOTDIR, 'Not a plain directory (links unsupported)', str(component))


def find_large_files(
        root: str | os.PathLike[str], *, min_size_bytes: int = 0,
        max_results: int = 20, max_entries: int = 1_000_000,
        max_depth: int = 64, max_errors: int = 32,
) -> FileSizeReport:
    """Return the largest observed regular files, without opening file content.

    Include hidden/binary files and ignore no repository paths or rules. Sizes
    are logical bytes, not allocated disk space. Sort by descending size, then
    case-sensitive relative path (``/`` separators). Hard links count per path.

    Root is explicit and must have no linked/reparse ancestors. Root validation
    errors raise OSError; subsequent filesystem errors yield a partial report.
    Skip child links/reparse points and special files. ``max_depth=0`` examines
    root entries but does not descend. Reaching the entry cap conservatively
    marks the scan incomplete, including at exact EOF. Result retention alone
    does not mark a scan incomplete; see ``results_truncated`` separately.

    Keep at most max_results candidates, max_errors error details and one open
    directory iterator per active level. Close iterators on every exit. OS calls
    may block; there is no deadline, cancellation API or atomic snapshot. Use
    trusted trees: concurrent hostile ancestor replacement can defeat the
    component checks between calls. Metadata can change during or after a scan.
    """
    for name, value, minimum in (
        ('min_size_bytes', min_size_bytes, 0), ('max_results', max_results, 1),
        ('max_entries', max_entries, 1), ('max_depth', max_depth, 0),
        ('max_errors', max_errors, 0),
    ):
        if type(value) is not int or value < minimum:
            raise ValueError(f'{name} must be an integer >= {minimum}')
    native_root = Path(os.path.abspath(root))
    _check_directory(native_root)
    heap, errors, stack = [], [], []
    reasons = set()
    examined = scanned = matched = links = special = error_count = 0

    def record_error(path, operation, error):
        nonlocal error_count
        error_count += 1
        reasons.add('filesystem_error')
        if len(errors) < max_errors:
            errors.append(FileSizeError(str(path), operation, error.errno))

    def enter(path, relative, depth):
        try:
            entries = os.scandir(path)
        except OSError as error:
            record_error(path, 'scandir', error)
        else:
            stack.append((path, relative, depth, entries))

    try:
        enter(native_root, '', 0)
        while stack:
            if examined >= max_entries:
                reasons.add('max_entries')
                break
            directory, relative, depth, entries = stack[-1]
            try:
                entry = next(entries)
            except StopIteration:
                entries.close()
                stack.pop()
                continue
            except OSError as error:
                record_error(directory, 'scandir', error)
                entries.close()
                stack.pop()
                continue
            examined += 1
            try:
                metadata = entry.stat(follow_symlinks=False)
            except OSError as error:
                record_error(entry.path, 'stat', error)
                continue
            if _is_link(metadata):
                links += 1
                continue
            child_relative = relative + '/' + entry.name if relative else entry.name
            if stat.S_ISDIR(metadata.st_mode):
                if depth >= max_depth:
                    reasons.add('max_depth')
                    continue
                child = Path(entry.path)
                try:
                    _check_directory(child)
                except OSError as error:
                    record_error(child, 'stat', error)
                    continue
                enter(child, child_relative, depth + 1)
            elif stat.S_ISREG(metadata.st_mode):
                scanned += 1
                if metadata.st_size < min_size_bytes:
                    continue
                matched += 1
                item = _HeapFile(FileSize(entry.path, child_relative, metadata.st_size))
                if len(heap) < max_results:
                    heapq.heappush(heap, item)
                elif heap[0] < item:
                    heapq.heapreplace(heap, item)
            else:
                special += 1
    finally:
        for _, _, _, entries in reversed(stack):
            entries.close()
    files = tuple(sorted((item.file for item in heap), key=lambda f: (-f.size_bytes, f.relative_path)))
    return FileSizeReport(str(native_root), files, not reasons, tuple(sorted(reasons)),
                          matched > len(files), examined, scanned, matched, links, special,
                          error_count, tuple(errors), error_count > len(errors))
