import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cereja.system import RepositoryFile, iter_repository_files
from cereja.system._path import Path as CerejaPath
from cereja.system import _repository_files as repository_files_module


class FakeDirectoryEntry:
    def __init__(
            self,
            path,
            *,
            directory=False,
            symlink=False,
            file_attributes=0,
            metadata_error=None,
    ):
        self.path = os.fspath(path)
        self.name = Path(path).name
        self._directory = directory
        self._symlink = symlink
        self._file_attributes = file_attributes
        self._metadata_error = metadata_error
        self.calls = []

    def is_symlink(self):
        self.calls.append(("is_symlink",))
        if self._metadata_error is not None:
            raise self._metadata_error
        return self._symlink

    def is_dir(self, *, follow_symlinks=True):
        self.calls.append(("is_dir", follow_symlinks))
        if self._metadata_error is not None:
            raise self._metadata_error
        return self._directory

    def stat(self, *, follow_symlinks=True):
        self.calls.append(("stat", follow_symlinks))
        if self._metadata_error is not None:
            raise self._metadata_error
        return SimpleNamespace(st_file_attributes=self._file_attributes)


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

    def test_honors_nested_ignore_bases_negation_and_final_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
            (root / "root.tmp").write_text("ignored", encoding="utf-8")
            src = root / "src"
            src.mkdir()
            (src / ".gitignore").write_text(
                "*.secret\n!important.secret\n",
                encoding="utf-8",
            )
            (src / "hidden.secret").write_text("ignored", encoding="utf-8")
            (src / "important.secret").write_text("kept", encoding="utf-8")
            (src / "Zulu.txt").write_text("z", encoding="utf-8")
            (src / "alpha.txt").write_text("a", encoding="utf-8")

            files = list(iter_repository_files([root]))

            self.assertEqual(
                [item.relative_path for item in files],
                [
                    ".gitignore",
                    "src/.gitignore",
                    "src/Zulu.txt",
                    "src/alpha.txt",
                    "src/important.secret",
                ],
            )

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

    def test_walk_uses_direntry_metadata_and_defers_path_construction(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = CerejaPath(temp_dir)
            child_path = Path(temp_dir) / "child"
            entries = [
                FakeDirectoryEntry(Path(temp_dir) / ".git", directory=True),
                FakeDirectoryEntry(Path(temp_dir) / "ignored.tmp"),
                FakeDirectoryEntry(Path(temp_dir) / "linked.txt", symlink=True),
                FakeDirectoryEntry(Path(temp_dir) / "wrong.md"),
                FakeDirectoryEntry(child_path, directory=True),
                FakeDirectoryEntry(Path(temp_dir) / "keep.TXT"),
            ]
            child_entry = FakeDirectoryEntry(child_path / "inside.txt")
            by_directory = {
                root.path: entries,
                CerejaPath(child_path).path: [child_entry],
            }
            created = []

            def scan(path, **kwargs):
                self.assertEqual(kwargs, {
                    "include_hidden": True,
                    "raise_errors": True,
                })
                return iter(by_directory[CerejaPath(path).path])

            def make_path(path):
                created.append(CerejaPath(path).path)
                return CerejaPath(path)

            ignore = repository_files_module._IgnoreRule(
                "*.tmp", False, False, False, root.path
            )
            with patch.object(
                    repository_files_module,
                    "iter_directory_entries",
                    side_effect=scan,
            ), patch.object(
                    repository_files_module,
                    "Path",
                    side_effect=make_path,
            ):
                found = repository_files_module._walk_files(
                    root,
                    (ignore,),
                    frozenset({".txt"}),
                )

            self.assertEqual(
                [
                    Path(item.path).relative_to(temp_dir).as_posix()
                    for item in found
                ],
                ["child/inside.txt", "keep.TXT"],
            )
            self.assertEqual(
                [Path(path).relative_to(temp_dir).as_posix() for path in created],
                ["child", "child/inside.txt", "keep.TXT"],
            )
            for entry in entries:
                self.assertIn(("is_symlink",), entry.calls)
            self.assertNotIn(("is_dir", False), entries[2].calls)
            for entry in (*entries[:2], *entries[3:], child_entry):
                self.assertIn(("is_dir", False), entry.calls)

    def test_walk_propagates_direntry_metadata_errors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = CerejaPath(temp_dir)
            failed = FakeDirectoryEntry(
                Path(temp_dir) / "vanished.txt",
                metadata_error=OSError("metadata unavailable"),
            )
            with patch.object(
                    repository_files_module,
                    "iter_directory_entries",
                    return_value=iter((failed,)),
            ):
                with self.assertRaisesRegex(OSError, "metadata unavailable"):
                    repository_files_module._walk_files(root, (), None)

    def test_windows_reparse_point_is_treated_as_link(self):
        entry = FakeDirectoryEntry(
            "junction",
            directory=True,
            file_attributes=0x400,
        )

        with patch.object(repository_files_module.os, "name", "nt"):
            is_link = repository_files_module._directory_entry_is_link(entry)

        self.assertTrue(is_link)
        self.assertEqual(
            entry.calls,
            [("is_symlink",), ("stat", False)],
        )


if __name__ == "__main__":
    unittest.main()
