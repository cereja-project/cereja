"""Ledger Tree adapter: bounded JSON publication and UI-owned hierarchy."""
import json
from pathlib import Path

from cereja.ui.collections import TreeNode, TreeView, CollectionLimits
from cereja.ui.editing import TextContent
from cereja.ui.text import normalize_text

MAX_NODES = 64
MAX_PUBLICATION_BYTES = 48000


def load(root, relative, depth, context):
    from cereja.system.repository import RepositoryTree
    context.running()
    with RepositoryTree(root, max_depth=depth, max_nodes=256,
                        max_work=2048, max_directory_entries=256) as tree:
        node = tree.root_node
        for part in Path(relative).parts:
            page = tree.children(node.id, page_size=256)
            node = next((n for n in page.nodes if n.name == part and n.kind == 'directory'), None)
            if node is None:
                raise ValueError('Directory unavailable within traversal budget')
        page = tree.children(node.id, page_size=MAX_NODES - 1)
        records = []
        complete = page.complete and page.next_offset is None
        for child in page.nodes:
            item = dict(id=child.id, parent=child.parent_id, name=child.name,
                        relative=child.relative_path, kind=child.kind)
            candidate = json.dumps(records + [item], ensure_ascii=True)
            if len(candidate.encode('utf-8')) > MAX_PUBLICATION_BYTES - 2048:
                complete = False
                break
            records.append(item)
        payload = dict(parent=node.id, relative=relative, nodes=records,
                       complete=complete, examined=tree.examined,
                       reason=page.reason if complete else page.reason or 'UI node/publication limit; omitted count unknown')
        result = json.dumps(payload, ensure_ascii=True)
        if len(result.encode('utf-8')) > MAX_PUBLICATION_BYTES:
            raise ValueError('Tree publication exceeds byte limit')
        return result


class TreeResult:
    def __init__(self, root, depth):
        # Root validation happens in the worker; derive the same lexical identity
        # only on receipt, rather than invoking filesystem APIs on the UI thread.
        self.root = root
        self.depth = depth
        self.records = {}
        self.view = TreeView('ledger-tree', (),
                             limits=CollectionLimits(max_items=MAX_NODES, max_bytes=48000, max_depth=8))

    def receive(self, text):
        payload = json.loads(text)
        parent = payload['parent']
        if not self.records:
            self.records[parent] = dict(id=parent, parent=None, name='Root', relative='', kind='directory',
                                        state='incomplete', message='Not loaded')
        if parent not in self.records:
            raise ValueError('Stale tree parent')
        record = self.records[parent]
        record['state'] = 'complete' if payload['complete'] else 'incomplete'
        record['message'] = payload['reason']
        for item in payload['nodes']:
            if item['id'] not in self.records and len(self.records) >= MAX_NODES:
                record['state'] = 'incomplete'
                record['message'] = 'Retained node limit; omitted count unknown'
                break
            item['state'] = 'incomplete' if item['kind'] == 'directory' else 'complete'
            item['message'] = 'Not loaded' if item['kind'] == 'directory' else ''
            self.records[item['id']] = item
        # Parent-before-child insertion order is stable across bounded loads.
        nodes = []
        for item in self.records.values():
            detail = item['relative'] or self.root
            nodes.append(TreeNode(item['id'], normalize_text(item['name']).replace('\n', ' ').replace('\t', ' '),
                                  item['parent'], item['kind'] == 'directory', item['state'], item['message'],
                                  TextContent(item['id'], 0, detail)))
        self.view.update(nodes)
        self.view.expand(parent)
        return ('Tree snapshot | read only | Right expand/load, Left collapse, Enter inspect\n'
                + f"{len(self.records)} retained nodes; {payload['examined']} entries examined in this load\n"
                + ('Complete directory' if payload['complete'] else 'Incomplete: ' + payload['reason']))
