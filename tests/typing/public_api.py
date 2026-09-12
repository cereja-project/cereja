"""Static consumer smoke test: exports must resolve to real types, not Any."""

from typing import assert_type

import cereja as cj
from cereja.concurrently import TaskList
from cereja.file import FileIO
from cereja.system import Path


def consume(path: cj.Path, file: cj.FileIO, tasks: cj.TaskList) -> None:
    assert_type(path, Path)
    assert_type(file, FileIO)
    assert_type(tasks, TaskList)


assert_type(cj.__version__, str)
cj.not_a_public_cereja_export  # type: ignore[attr-defined]
