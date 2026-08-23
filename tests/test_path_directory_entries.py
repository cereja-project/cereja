import os
import tempfile
import unittest
from pathlib import Path as NativePath
from types import SimpleNamespace
from unittest.mock import patch

from cereja.system._path import Path


class PathDirectoryEntriesTest(unittest.TestCase):
    def test_simple_list_dir_matches_scandir_order_and_path_results(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = NativePath(temp_dir)
            (root / "Zulu.TXT").write_text("z", encoding="utf-8")
            (root / "alpha.txt").write_text("a", encoding="utf-8")
            (root / "árvore.md").write_text("unicode", encoding="utf-8")
            (root / ".hidden.txt").write_text("hidden", encoding="utf-8")
            (root / "child").mkdir()
            expected = [
                NativePath(entry.path).as_posix()
                for entry in os.scandir(root)
                if not entry.name.startswith(".")
            ]

            results = Path(root).list_dir()

            self.assertCountEqual([item.path for item in results], expected)
            self.assertTrue(all(isinstance(item, Path) for item in results))

    def test_simple_list_dir_preserves_primitive_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            emitted = [
                SimpleNamespace(path=root.join(name).path)
                for name in ("Zulu.txt", "alpha.txt", "árvore.txt")
            ]
            with patch(
                    "cereja.system._path.iter_directory_entries",
                    return_value=iter(emitted),
            ):
                results = root.list_dir()

            self.assertEqual(
                [item.name for item in results],
                ["Zulu.txt", "alpha.txt", "árvore.txt"],
            )

    def test_simple_list_dir_supports_hidden_and_only_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = NativePath(temp_dir)
            (root / ".archive.tar.gz").write_text("hidden", encoding="utf-8")
            (root / "visible.tar.gz").write_text("visible", encoding="utf-8")

            names = Path(root).list_dir(
                only_name=True,
                include_hidden=True,
            )

            self.assertCountEqual(names, [".archive.tar", "visible.tar"])

    def test_simple_list_dir_suppresses_enumeration_races_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            failed = FileNotFoundError("gone")
            with self.assertLogs(
                    "cereja.system._directory_entries", level="ERROR"
            ), patch("os.scandir", side_effect=failed):
                self.assertEqual(root.list_dir(), [])

            with patch("os.scandir", side_effect=failed):
                with self.assertRaisesRegex(FileNotFoundError, "gone"):
                    root.list_dir(raise_errors=True)

    def test_simple_list_dir_delegates_permission_policy_to_primitive(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            denied = PermissionError("denied")
            with self.assertLogs(
                    "cereja.system._path", level="ERROR"
            ) as logs, patch(
                "cereja.system._path.iter_directory_entries",
                side_effect=denied,
            ):
                self.assertEqual(root.list_dir(), [])
                with self.assertRaisesRegex(PermissionError, "denied"):
                    root.list_dir(raise_errors=True)
            self.assertIn("denied", logs.output[0])

    def test_patterns_and_recursive_calls_keep_glob_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            matched = root.join("match.txt").path
            cases = (("*.txt", False), ("*", True), ("**/*.txt", True))
            for search_match, recursive in cases:
                with self.subTest(search_match=search_match, recursive=recursive):
                    with patch(
                            "cereja.system._path.iter_directory_entries",
                            side_effect=AssertionError("unexpected scandir fast path"),
                    ), patch(
                            "cereja.system._path.glob.glob",
                            return_value=[matched],
                    ) as glob_call:
                        results = root.list_dir(
                            search_match,
                            recursive=recursive,
                            include_hidden=True,
                        )

                    self.assertEqual([item.path for item in results], [matched])
                    glob_call.assert_called_once_with(
                        root.join(search_match).path,
                        recursive=recursive,
                        include_hidden=True,
                    )

    def test_empty_directory_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertEqual(Path(temp_dir).list_dir(), [])


if __name__ == "__main__":
    unittest.main()
