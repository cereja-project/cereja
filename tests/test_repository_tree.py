import os
import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

from cereja.system import render_repository_tree


@contextmanager
def temporary_workspace_directory():
    temp_dir = Path.cwd() / f"test_repository_tree_{uuid.uuid4().hex}"
    temp_dir.mkdir()
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def write_text(path: Path, content: str = "content") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class RepositoryTreeTest(unittest.TestCase):
    def test_render_repository_tree_orders_directories_before_files(self):
        with temporary_workspace_directory() as temp_dir:
            root = temp_dir / "project"
            (root / "a-dir").mkdir(parents=True)
            write_text(root / "a-dir" / "nested.py", "pass")
            write_text(root / "z-file.txt")

            rendered = render_repository_tree(root)

            self.assertEqual(
                rendered,
                "project/\n├── a-dir/\n│   └── nested.py\n└── z-file.txt",
            )

    def test_render_repository_tree_depth_zero_shows_root_only(self):
        with temporary_workspace_directory() as temp_dir:
            root = temp_dir / "project"
            write_text(root / "child.txt")

            rendered = render_repository_tree(root, depth=0)

            self.assertEqual(rendered, "project/")

    def test_render_repository_tree_depth_one_hides_grandchildren(self):
        with temporary_workspace_directory() as temp_dir:
            root = temp_dir / "project"
            write_text(root / "child" / "grandchild.txt")

            rendered = render_repository_tree(root, depth=1)

            self.assertEqual(rendered, "project/\n└── child/")

    def test_render_repository_tree_includes_empty_directories(self):
        with temporary_workspace_directory() as temp_dir:
            root = temp_dir / "project"
            (root / "empty").mkdir(parents=True)

            rendered = render_repository_tree(root)

            self.assertEqual(rendered, "project/\n└── empty/")

    def test_render_repository_tree_hides_builtin_caches(self):
        with temporary_workspace_directory() as temp_dir:
            root = temp_dir / "project"
            write_text(root / "__pycache__" / "module.pyc")
            write_text(root / ".pytest_cache" / "cache.data")
            write_text(root / "module.pyc")
            write_text(root / "visible.py")

            rendered = render_repository_tree(root)

            self.assertEqual(rendered, "project/\n└── visible.py")

    def test_render_repository_tree_shows_nonignored_hidden_files(self):
        with temporary_workspace_directory() as temp_dir:
            root = temp_dir / "project"
            write_text(root / ".env")
            write_text(root / ".gitignore", "")

            rendered = render_repository_tree(root)

            self.assertEqual(rendered, "project/\n├── .env\n└── .gitignore")

    def test_render_repository_tree_applies_common_ignore_rules(self):
        with temporary_workspace_directory() as temp_dir:
            root = temp_dir / "project"
            write_text(
                root / ".gitignore",
                "# generated files\n*.log\nbuild/\n!keep.log\n/only-root.txt\n**/deep.txt\n",
            )
            write_text(root / "ignored.log")
            write_text(root / "keep.log")
            write_text(root / "only-root.txt")
            write_text(root / "nested" / "only-root.txt")
            write_text(root / "nested" / "deep.txt")
            write_text(root / "build" / "artifact.bin")

            rendered = render_repository_tree(root)

            self.assertEqual(
                rendered,
                "project/\n├── nested/\n│   └── only-root.txt\n├── .gitignore\n└── keep.log",
            )

    def test_render_repository_tree_applies_nested_ignore_rules(self):
        with temporary_workspace_directory() as temp_dir:
            root = temp_dir / "project"
            write_text(root / ".gitignore", "*.tmp\n")
            write_text(root / "root.tmp")
            write_text(root / "src" / ".gitignore", "*.secret\n!important.secret\n")
            write_text(root / "src" / "hidden.secret")
            write_text(root / "src" / "important.secret")
            write_text(root / "src" / "note.txt")

            rendered = render_repository_tree(root)

            self.assertEqual(
                rendered,
                "project/\n├── src/\n│   ├── .gitignore\n│   ├── important.secret\n│   └── note.txt\n└── .gitignore",
            )

    def test_render_repository_tree_supports_question_and_bracket_patterns(self):
        with temporary_workspace_directory() as temp_dir:
            root = temp_dir / "project"
            write_text(root / ".gitignore", "file?.txt\n[ab]-*.txt\n")
            write_text(root / "file1.txt")
            write_text(root / "file10.txt")
            write_text(root / "a-one.txt")
            write_text(root / "c-one.txt")

            rendered = render_repository_tree(root)

            self.assertEqual(rendered, "project/\n├── .gitignore\n├── c-one.txt\n└── file10.txt")

    def test_render_repository_tree_rejects_invalid_roots_and_depth(self):
        with temporary_workspace_directory() as temp_dir:
            file_path = temp_dir / "file.txt"
            write_text(file_path)

            with self.assertRaises(FileNotFoundError):
                render_repository_tree(temp_dir / "missing")
            with self.assertRaises(NotADirectoryError):
                render_repository_tree(file_path)
            with self.assertRaises(ValueError):
                render_repository_tree(temp_dir, depth=-1)

    def test_render_repository_tree_does_not_traverse_directory_symlinks(self):
        with temporary_workspace_directory() as temp_dir:
            root = temp_dir / "project"
            write_text(root / "real" / "inside.txt")
            link = root / "linked"
            try:
                os.symlink(root / "real", link, target_is_directory=True)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f"directory symlinks unavailable: {error}")

            rendered = render_repository_tree(root)

            self.assertEqual(rendered, "project/\n├── linked\n└── real/\n    └── inside.txt")


if __name__ == "__main__":
    unittest.main()
