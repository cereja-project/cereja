# Structured repository traversal

Import `RepositoryTree` from `cereja.system.repository`. The API is independent
of widgets, terminal sessions, workers and persistent caches. Existing text-tree
and file-inventory APIs retain their behavior and limits.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from cereja.system.repository import RepositoryTree

with TemporaryDirectory() as directory:
    (Path(directory) / 'empty').mkdir()
    with RepositoryTree(directory, max_depth=3, max_nodes=128,
                        max_work=512, max_directory_entries=128) as tree:
        page = tree.children(page_size=32)
        while True:
            for node in page.nodes:
                print(node.relative_path, node.kind)
            print('Complete:', page.complete, page.reason)
            if page.next_offset is None:
                break
            page = tree.children(offset=page.next_offset, page_size=32)
```

Node identity hashes the canonical root and normalized relative path. Identity
is path identity, not inode identity; replacement at the same path retains its ID.
Nodes include parent identity, literal name/path, kind and depth. Links are shown
and never traversed. Link roots, including Windows reparse roots, are rejected.
The filters reuse the existing built-in and common `.gitignore` matcher. This
is not complete Git semantics. Ignore rules inherit from loaded parent nodes.
Linked ignore files fail closed rather than reading unrelated targets.

Each directory is scanned at most once per session. Retained entries are sorted
by directory-first, casefolded name and original name. With a complete scan that
is the complete listing order. If a budget is reached it is only the order of
the retained enumeration prefix, not a globally sorted partial listing. OS
`scandir` prefix order is not promised to repeat across sessions. Pagination of
the retained snapshot is deterministic and performs no additional scan. Mutation
between pages does not change the retained snapshot; reopening observes a new
non-atomic view. Loading a disappeared/replaced directory reports incompleteness.

Defaults: depth 8, 1,024 nodes including root, 8,192 entries examined across the
session, 2,048 entries examined per directory, 65,536 ignore bytes across the
session and 4,096 UTF-8 bytes per relative path. Pages contain at most 512 nodes.
An exact cap conservatively reports incomplete because no extra entry is read
to establish EOF. `next_offset=None` means no more retained nodes, not necessarily
a complete source. `complete` and `reason` carry that distinction. Omitted counts
are unknown. Filesystem failures are explicit and do not imply an empty directory.

Ignore decoding and matching use a bounded byte input. Retained nodes and rule
snapshots are bounded by these logical limits; they do not establish a process
RSS limit. Increasing limits increases CPU and retention costs. Values are
conservative candidate defaults, not demonstrated optimal settings. Calibration:
`python -m benchmarks.repository_traversal` uses only owned temporary fixtures.

The context manager closes all enumeration streams before returning each page
and drops retained state on exit. Explicit `close()` is also supported. OS calls
can block. Component link checks prevent ordinary link descent but cannot exclude
hostile concurrent ancestor replacement between filesystem calls; use owned,
trusted trees. No cancellation or deadline guarantee follows from entry budgets.
