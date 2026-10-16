import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cereja.system.repository import RepositoryTree


class RepositoryTraversalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_pages_filters_empty_directory_and_stable_identity(self):
        (self.root / 'empty').mkdir()
        (self.root / 'z.py').write_text('')
        (self.root / 'a.tmp').write_text('')
        (self.root / '.gitignore').write_text('*.tmp\n')
        with RepositoryTree(self.root) as tree:
            first = tree.children(page_size=1)
            self.assertEqual(first.nodes[0].name, 'empty')
            self.assertTrue(first.complete)
            rest = tree.children(offset=first.next_offset)
            self.assertEqual([n.name for n in rest.nodes], ['.gitignore', 'z.py'])
            self.assertTrue(tree.children(first.nodes[0].id).complete)
            node_id = rest.nodes[-1].id
        with RepositoryTree(self.root) as tree:
            self.assertEqual(tree.children().nodes[-1].id, node_id)

    def test_work_is_bounded_even_when_all_entries_ignored(self):
        for i in range(30):
            (self.root / (str(i) + '.pyc')).write_text('')
        with RepositoryTree(self.root, max_work=7) as tree:
            page = tree.children()
            self.assertEqual(tree.examined, 7)
            self.assertFalse(page.complete)
            self.assertEqual(page.nodes, ())
            self.assertIn('unknown', page.reason)

    def test_snapshot_paging_does_not_rescan_or_change(self):
        for i in range(5):
            (self.root / str(i)).touch()
        with RepositoryTree(self.root) as tree:
            first = tree.children(page_size=2)
            (self.root / 'new').touch()
            with patch('os.scandir', side_effect=AssertionError('rescan')):
                second = tree.children(offset=first.next_offset)
            self.assertEqual(len(second.nodes), 3)
            self.assertEqual(tree.examined, 5)

    def test_inherited_rules_and_depth(self):
        (self.root / '.gitignore').write_text('*.tmp\n')
        sub = self.root / 'sub'
        sub.mkdir()
        (sub / 'a.tmp').touch()
        (sub / 'b').touch()
        with RepositoryTree(self.root) as tree:
            child = next(n for n in tree.children().nodes if n.kind == 'directory')
            self.assertEqual([n.name for n in tree.children(child.id).nodes], ['b'])
        with RepositoryTree(self.root, max_depth=0) as tree:
            self.assertIn('depth', tree.children().reason)

    def test_node_budget_and_close(self):
        for i in range(20):
            (self.root / str(i)).touch()
        tree = RepositoryTree(self.root, max_nodes=4)
        self.assertEqual(len(tree.children().nodes), 3)
        self.assertFalse(tree.children().complete)
        tree.close()
        with self.assertRaises(RuntimeError):
            tree.children()

    def test_ignore_budget_fails_closed(self):
        (self.root / '.gitignore').write_text('secret\n' * 30)
        (self.root / 'secret').touch()
        with RepositoryTree(self.root, max_ignore_bytes=5) as tree:
            page = tree.children()
            self.assertFalse(page.complete)
            self.assertEqual(page.nodes, ())

    def test_failure_is_explicit(self):
        with RepositoryTree(self.root) as tree:
            with patch('os.scandir', side_effect=PermissionError()):
                page = tree.children()
            self.assertFalse(page.complete)
            self.assertIn('failed', page.reason)

    def test_link_root_rejected_and_child_not_descended(self):
        target = self.root / 'target'
        target.mkdir()
        link = self.root / 'link'
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest('symlink creation unavailable')
        with self.assertRaises(NotADirectoryError):
            RepositoryTree(link)
        with RepositoryTree(self.root) as tree:
            node = next(n for n in tree.children().nodes if n.name == 'link')
            self.assertEqual(node.kind, 'link')
            self.assertEqual(tree.children(node.id).nodes, ())

    def test_disappeared_directory(self):
        sub = self.root / 'sub'
        sub.mkdir()
        with RepositoryTree(self.root) as tree:
            node = tree.children().nodes[0]
            sub.rmdir()
            self.assertFalse(tree.children(node.id).complete)

    def test_unicode_and_controls_are_literal_data(self):
        name = 'café 界.txt'
        (self.root / name).touch()
        with RepositoryTree(self.root) as tree:
            self.assertEqual(tree.children().nodes[0].name, name)


if __name__ == '__main__':
    unittest.main()
