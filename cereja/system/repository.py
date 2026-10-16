"""Bounded, UI-independent repository snapshots. Links are never descended."""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path as NativePath

from ._path import Path
from ._repository_files import (
    _validate_root, _directory_entry_is_link, _is_builtin_ignored,
    _is_ignored, _parse_ignore_rule,
)


@dataclass(frozen=True, slots=True)
class RepositoryNode:
    id: str
    parent_id: str | None
    relative_path: str
    name: str
    kind: str
    depth: int


@dataclass(frozen=True, slots=True)
class ChildrenPage:
    nodes: tuple[RepositoryNode, ...]
    next_offset: int | None
    complete: bool
    examined: int
    reason: str = ''


class RepositoryTree:
    """One bounded snapshot session, explicitly closed by its owner.

    A directory is scanned once, up to remaining work/node budgets, then its
    retained prefix is sorted directories-first. Pages use that immutable prefix.
    Incomplete prefixes are NOT globally ordered directory listings. Reopen a
    session to observe changes. No disk history, global cache or live snapshot
    guarantee. Blocking filesystem calls have no wall-clock deadline.
    """

    def __init__(self, root, *, max_depth=8, max_nodes=1024,
                 max_work=8192, max_directory_entries=2048,
                 max_ignore_bytes=65536, max_path_bytes=4096):
        for name, value, minimum in (
            ('max_depth', max_depth, 0), ('max_nodes', max_nodes, 1),
            ('max_work', max_work, 1),
            ('max_directory_entries', max_directory_entries, 1),
            ('max_ignore_bytes', max_ignore_bytes, 1),
            ('max_path_bytes', max_path_bytes, 1),
        ):
            if type(value) is not int or not minimum <= value <= 1_000_000:
                raise ValueError(name + ' outside supported bounds')
        self.root = Path(root)
        _validate_root(self.root)
        self._native = NativePath(os.path.abspath(self.root.path))
        self.max_depth = max_depth
        self.max_nodes = max_nodes
        self.max_work = max_work
        self.max_directory_entries = max_directory_entries
        self.max_ignore_bytes = max_ignore_bytes
        self.max_path_bytes = max_path_bytes
        self.examined = 0
        self._ignore_bytes = 0
        self._closed = False
        self._identity = os.path.normcase(os.path.realpath(self.root.path))
        self.root_node = self._node('', None, 'directory', 0)
        self._nodes = {self.root_node.id: self.root_node}
        self._rules = {self.root_node.id: ()}
        self._snapshots = {}

    def _node(self, relative, parent, kind, depth):
        identity = hashlib.sha256(
            (self._identity + '\0' + relative).encode('utf-8', 'surrogatepass')
        ).hexdigest()
        name = NativePath(relative).name if relative else self._native.name
        return RepositoryNode(identity, parent, relative, name, kind, depth)

    def children(self, node_id=None, *, offset=0, page_size=128):
        if self._closed:
            raise RuntimeError('RepositoryTree is closed')
        if type(offset) is not int or offset < 0:
            raise ValueError('offset must be non-negative')
        if type(page_size) is not int or not 1 <= page_size <= 512:
            raise ValueError('page_size must be 1..512')
        node_id = self.root_node.id if node_id is None else node_id
        node = self._nodes[node_id]
        if node_id not in self._snapshots:
            self._snapshots[node_id] = self._scan(node)
        nodes, complete, examined, reason = self._snapshots[node_id]
        if offset > len(nodes):
            raise ValueError('offset exceeds retained snapshot')
        end = min(len(nodes), offset + page_size)
        return ChildrenPage(nodes[offset:end], end if end < len(nodes) else None,
                            complete, examined, reason)

    def _scan(self, node):
        if node.kind != 'directory':
            return (), True, 0, ''
        if node.depth >= self.max_depth:
            return (), False, 0, 'depth limit; omitted count unknown'
        path = self._native / node.relative_path
        # Revalidate every component before descent. This is not protection
        # against hostile concurrent path replacement between OS calls.
        current = self._native
        for part in ('', *NativePath(node.relative_path).parts):
            current = current / part
            if Path(current).is_link or not current.is_dir():
                return (), False, 0, 'directory disappeared, changed or is a link'
        rules = self._rules[node.id]
        count = 0
        try:
            ignore = path / '.gitignore'
            if ignore.exists():
                if Path(ignore).is_link:
                    return (), False, 0, 'linked ignore file is unsupported'
                remaining = self.max_ignore_bytes - self._ignore_bytes
                with open(ignore, 'rb') as stream:
                    data = stream.read(remaining + 1)
                self._ignore_bytes += min(len(data), remaining)
                if len(data) > remaining:
                    return (), False, 0, 'ignore byte budget; omitted count unknown'
                rules += tuple(rule for line in data.decode('utf-8', 'replace').splitlines()
                               if (rule := _parse_ignore_rule(line, str(path))) is not None)
            retained = []
            count = 0
            complete = False
            reason = 'entry/work/node budget; omitted count unknown'
            with os.scandir(path) as entries:
                while (count < self.max_directory_entries and self.examined < self.max_work
                       and len(self._nodes) < self.max_nodes):
                    try:
                        entry = next(entries)
                    except StopIteration:
                        complete, reason = True, ''
                        break
                    count += 1
                    self.examined += 1
                    link = _directory_entry_is_link(entry)
                    directory = not link and entry.is_dir(follow_symlinks=False)
                    if _is_builtin_ignored(entry, directory) or _is_ignored(entry, directory, rules):
                        continue
                    relative = (NativePath(node.relative_path) / entry.name).as_posix()
                    if len(relative.encode('utf-8', 'surrogatepass')) > self.max_path_bytes:
                        return (), False, count, 'path byte budget; omitted count unknown'
                    child = self._node(relative, node.id,
                                       'link' if link else 'directory' if directory else 'file',
                                       node.depth + 1)
                    self._nodes[child.id] = child
                    if directory:
                        self._rules[child.id] = rules
                    retained.append(child)
            retained.sort(key=lambda item: (item.kind != 'directory', item.name.casefold(), item.name))
            return tuple(retained), complete, count, reason
        except OSError:
            return (), False, count, 'filesystem read failed; omitted count unknown'

    def close(self):
        self._closed = True
        self._snapshots.clear()
        self._nodes.clear()
        self._rules.clear()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
