"""Private non-recursive directory enumeration helpers."""

import logging
import os


logger = logging.getLogger(__name__)


def iter_directory_entries(
        path,
        *,
        include_hidden=False,
        raise_errors=False,
):
    """Yield os.DirEntry values for one directory without recursion."""
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                if include_hidden or not entry.name.startswith("."):
                    yield entry
    except OSError as error:
        if raise_errors:
            raise
        logger.error("%s", error)
