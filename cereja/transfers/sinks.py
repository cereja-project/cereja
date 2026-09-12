"""Atomic filesystem sinks for transfers."""

import os
from pathlib import Path
import tempfile


class AtomicFileSink:
    def __init__(self, destination):
        self.destination = Path(destination)
        self._path = None
        self._file = None

    def open(self):
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(
            mode="wb", delete=False, dir=self.destination.parent,
            prefix=f".{self.destination.name}.", suffix=".part",
        )
        self._file = handle
        self._path = Path(handle.name)
        return handle

    def commit(self):
        if self._file and not self._file.closed:
            self._file.flush()
            os.fsync(self._file.fileno())
            self._file.close()
        os.replace(self._path, self.destination)
        self._path = None

    def abort(self):
        if self._file and not self._file.closed:
            self._file.close()
        if self._path is not None:
            try:
                self._path.unlink()
            except FileNotFoundError:
                pass
            self._path = None
