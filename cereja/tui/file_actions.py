"""Explicit actions on observed ordinary files, for use by a TUI worker.

Identity checks catch ordinary changes since selection. Like the scanner's path
checks, separate OS calls do not provide containment against hostile concurrent
ancestor replacement. Copies publish atomically without replacing a destination.
Moves preserve the original file on the same volume and refuse copying fallback.
"""
from dataclasses import dataclass
import errno
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

from cereja.system._safe_paths import new_destination, ordinary_path
from cereja.transfers.sinks import AtomicFileSink


@dataclass(frozen=True, slots=True)
class FileSelection:
    path: str
    size_bytes: int
    device: int
    inode: int
    modified_ns: int
    ctime_ns: int


def _identity(path, metadata):
    return FileSelection(str(path), metadata.st_size, metadata.st_dev,
                         metadata.st_ino, metadata.st_mtime_ns, metadata.st_ctime_ns)


def capture_selection(path, *, expected_size=None):
    """Capture fresh metadata in the scan worker; never open the file content."""
    path = ordinary_path(path)
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or getattr(metadata, 'st_file_attributes', 0) & 0x400:
        raise ValueError('Expected ordinary file')
    if expected_size is not None and metadata.st_size != expected_size:
        raise ValueError('Selected file changed; scan again before acting')
    return _identity(path, metadata)


def _revalidate(selection, *, linked=False):
    if type(selection) is not FileSelection:
        raise TypeError('Expected FileSelection')
    observed = capture_selection(selection.path)
    # Creating our POSIX hard link changes ctime on the selected inode.
    if not _same_file(observed, selection, ignore_ctime=linked):
        raise ValueError('Selected file changed; scan again before acting')
    return Path(selection.path)


def _check_descriptor(stream, selection):
    metadata = os.fstat(stream.fileno())
    observed = _identity(selection.path, metadata)
    # Windows stat/fstat can expose creation and change times respectively as
    # ctime. Compare that field only between path checks there, not to the fd.
    same_file = _same_file(observed, selection, ignore_ctime=os.name == 'nt')
    if not stat.S_ISREG(metadata.st_mode) or not same_file:
        raise ValueError('Selected file changed; scan again before acting')


def _same_file(observed, selection, *, ignore_ctime=False):
    same = (observed.size_bytes, observed.device, observed.inode, observed.modified_ns) == (
        selection.size_bytes, selection.device, selection.inode, selection.modified_ns)
    return same and (ignore_ctime or observed.ctime_ns == selection.ctime_ns)


def _move(selection, destination, context):
    source = _revalidate(selection)
    target = new_destination(destination)
    if context is not None:
        context.committing()
    _revalidate(selection)
    new_destination(target)
    try:
        if os.name == 'nt':
            # Unlike POSIX rename, Windows rename refuses existing targets.
            os.rename(source, target)
        else:
            os.link(source, target, follow_symlinks=False)
    except OSError as error:
        if error.errno == errno.EXDEV or getattr(error, 'winerror', None) == 17:
            raise ValueError('Cross-volume moves are unsupported; copy, verify the destination, then delete the source') from None
        raise
    if os.name != 'nt':
        try:
            _revalidate(selection, linked=True)
            if not _same_file(capture_selection(target), selection, ignore_ctime=True):
                raise ValueError('Selected file changed; scan again before acting')
            source.unlink()
        except (OSError, ValueError):
            # The new link is already published. Do not delete either path on
            # failure, including a destination replaced by a concurrent actor.
            raise ValueError('Destination was linked, but source was not removed; inspect both paths before retrying') from None
    return target


def _copy(selection, destination, context):
    source = _revalidate(selection)
    target = new_destination(destination)
    sink = AtomicFileSink(target, overwrite=False)
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    try:
        with os.fdopen(os.open(source, flags), 'rb') as stream:
            _check_descriptor(stream, selection)
            output = sink.open()
            remaining = selection.size_bytes
            while remaining:
                chunk = stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError('Selected file changed; scan again before acting')
                output.write(chunk)
                remaining -= len(chunk)
            if stream.read(1):
                raise ValueError('Selected file changed; scan again before acting')
            _check_descriptor(stream, selection)
        _revalidate(selection)
        new_destination(target)
        if context is not None:
            context.committing()
        sink.commit()
    except BaseException:
        sink.abort()
        raise
    return target


def execute(action, selection, destination=None, context=None):
    """Run one already-reviewed action. UI owns confirmation and operation slot.

    Copy/move destinations are complete new file paths in existing ordinary
    directories. No source recursion, replacement, shell interpolation, queue,
    cancellation or whole-operation deadline is supplied by this adapter.
    """
    if action not in ('copy', 'move', 'delete', 'open-directory'):
        raise ValueError('Unsupported file action')
    if action in ('copy', 'move') and (type(destination) is not str or not destination.strip()):
        raise ValueError('Explicit destination file path required')
    source = _revalidate(selection)
    if context is not None:
        context.running()
    if action in ('copy', 'move'):
        target = (_move if action == 'move' else _copy)(selection, destination, context)
        return ('Moved to: ' if action == 'move' else 'Copied to: ') + json.dumps(str(target), ensure_ascii=True)
    if action == 'delete':
        if context is not None:
            context.committing()
        _revalidate(selection)
        source.unlink()
        return 'Deleted: ' + json.dumps(str(source), ensure_ascii=True)
    ordinary_path(source.parent, directory=True)
    if os.name == 'nt':
        os.startfile(str(source.parent))
    else:
        command = 'open' if sys.platform == 'darwin' else 'xdg-open'
        subprocess.run([command, str(source.parent)], check=True, timeout=10,
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 'Requested directory opening: ' + json.dumps(str(source.parent), ensure_ascii=True)
