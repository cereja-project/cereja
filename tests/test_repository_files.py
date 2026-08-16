import os
import tempfile
import unittest
from pathlib import Path

from cereja.system import RepositoryFile, iter_repository_files


class RepositoryFilesTest(unittest.TestCase):
    def test_repository_file_constructor_remains_backward_compatible(self):
        item = RepositoryFile(
            root="root",
            path="path",
            relative_path="relative.txt",
        )

        self.assertEqual(
            (item.root, item.path, item.relative_path),
            ("root", "path", "relative.txt"),
        )

    def test_is_ordered_and_honors_parent_gitignore(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "repo"
            root = repo / "docs" / "project"
            (repo / ".git").mkdir(parents=True)
            (repo / ".gitignore").write_text("*.secret\n", encoding="utf-8")
            root.mkdir(parents=True)
            (root / "z.md").write_text("z", encoding="utf-8")
            (root / "a.md").write_text("a", encoding="utf-8")
            (root / "hidden.secret").write_text("secret", encoding="utf-8")

            files = list(iter_repository_files([root]))

            self.assertEqual([item.relative_path for item in files], ["a.md", "z.md"])

    def test_deduplicates_overlapping_roots_by_input_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            outer = Path(temp_dir) / "outer"
            inner = outer / "inner"
            inner.mkdir(parents=True)
            (inner / "note.md").write_text("note", encoding="utf-8")

            files = list(iter_repository_files([outer, inner]))

            self.assertEqual(len(files), 1)
            self.assertEqual(Path(files[0].root.path), outer)
            self.assertEqual(files[0].relative_path, "inner/note.md")

    def test_filters_extensions_case_insensitively(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "guide.MD").write_text("guide", encoding="utf-8")
            (root / "notes.txt").write_text("notes", encoding="utf-8")

            files = list(iter_repository_files([root], extensions=["md"]))

            self.assertEqual([item.relative_path for item in files], ["guide.MD"])

    def test_rejects_missing_root_and_file_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            file_path = root / "file.txt"
            file_path.write_text("file", encoding="utf-8")

            with self.assertRaises(FileNotFoundError):
                list(iter_repository_files([root / "missing"]))
            with self.assertRaises(NotADirectoryError):
                list(iter_repository_files([file_path]))

    def test_does_not_follow_file_or_directory_symlinks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "root"
            root.mkdir()
            target_file = root / "target.txt"
            target_file.write_text("target", encoding="utf-8")
            real_dir = root / "real"
            real_dir.mkdir()
            (real_dir / "inside.txt").write_text("inside", encoding="utf-8")
            try:
                os.symlink(target_file, root / "linked.txt")
                os.symlink(real_dir, root / "linked-dir", target_is_directory=True)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f"symlinks unavailable: {error}")

            files = list(iter_repository_files([root]))

            self.assertEqual(
                [item.relative_path for item in files],
                ["real/inside.txt", "target.txt"],
            )


if __name__ == "__main__":
    unittest.main()
