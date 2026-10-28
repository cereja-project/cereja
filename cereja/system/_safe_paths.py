"""Shared ordinary-path admission for exclusive opt-in filesystem operations."""
import os
from pathlib import Path
import stat


def ordinary_path(path, *, directory=False):
    path = Path(os.path.abspath(path))
    for ancestor in (*reversed(path.parents), path):
        info = ancestor.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Links/reparse paths are unsupported')
    info = path.stat()
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise ValueError('Expected ordinary directory' if directory else 'Expected ordinary file')
    return path


def new_destination(destination):
    path = Path(os.path.abspath(destination))
    ordinary_path(path.parent, directory=True)
    if os.path.lexists(path):
        raise FileExistsError('Destination exists; replacement is unsupported')
    return path


