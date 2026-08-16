import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cereja.system._directory_entries import iter_directory_entries


class DirectoryEntriesTest(unittest.TestCase):
    def test_lists_one_directory_and_filters_dotfiles_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "Zulu.txt").write_text("z", encoding="utf-8")
            (root / "árvore.txt").write_text("a", encoding="utf-8")
            (root / ".hidden.txt").write_text("hidden", encoding="utf-8")
            (root / "child").mkdir()

            names = [entry.name for entry in iter_directory_entries(root)]

            self.assertCountEqual(names, ["Zulu.txt", "árvore.txt", "child"])

    def test_can_include_hidden_entries(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".hidden.txt").write_text("hidden", encoding="utf-8")

            names = [
                entry.name
                for entry in iter_directory_entries(root, include_hidden=True)
            ]

            self.assertEqual(names, [".hidden.txt"])

    def test_permission_error_returns_no_entries_by_default(self):
        denied = PermissionError("denied")
        with self.assertLogs(
                "cereja.system._directory_entries", level="ERROR"
        ) as logs, patch("os.scandir", side_effect=denied):
            entries = list(iter_directory_entries("blocked"))

        self.assertEqual(entries, [])
        self.assertIn("denied", logs.output[0])

    def test_permission_error_is_raised_when_requested(self):
        denied = PermissionError("denied")
        with patch("os.scandir", side_effect=denied):
            with self.assertRaisesRegex(PermissionError, "denied"):
                list(iter_directory_entries("blocked", raise_errors=True))

    def test_os_errors_return_no_entries_by_default(self):
        errors = (
            FileNotFoundError("gone"),
            NotADirectoryError("replaced"),
            OSError("enumeration failed"),
        )
        for error in errors:
            with self.subTest(error=type(error).__name__):
                with self.assertLogs(
                        "cereja.system._directory_entries", level="ERROR"
                ), patch("os.scandir", side_effect=error):
                    entries = list(iter_directory_entries("broken"))

                self.assertEqual(entries, [])

    def test_non_permission_os_errors_are_raised_when_requested(self):
        failed = FileNotFoundError("gone")
        with patch("os.scandir", side_effect=failed):
            with self.assertRaisesRegex(FileNotFoundError, "gone"):
                list(iter_directory_entries("broken", raise_errors=True))


if __name__ == "__main__":
    unittest.main()
