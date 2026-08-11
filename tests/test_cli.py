import io
import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from contextlib import contextmanager
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cereja.cli import main


def compression_stats():
    return SimpleNamespace(
        strategy=SimpleNamespace(value="zlib"),
        original_size=10,
        compressed_size=5,
        ratio=2.0,
        savings_percent=50.0,
    )


@contextmanager
def temporary_workspace_directory():
    temp_dir = Path.cwd() / f"test_cli_{uuid.uuid4().hex}"
    temp_dir.mkdir()
    try:
        yield str(temp_dir)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@contextmanager
def working_directory(path):
    original_dir = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original_dir)


class CliTest(unittest.TestCase):
    """Test suite for the Cereja command-line interface."""

    def test_module_help_returns_success(self):
        result = subprocess.run(
            [sys.executable, "-m", "cereja", "--help"],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Cereja Tools.", result.stdout)
        self.assertIn("compress", result.stdout)
        self.assertIn("tree", result.stdout)

    def test_module_version_returns_success(self):
        result = subprocess.run(
            [sys.executable, "-m", "cereja", "--version"],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
        )

        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stdout.strip())

    def test_compress_and_decompress_file_restore_original_bytes(self):
        with temporary_workspace_directory() as temp_dir:
            source_path = Path(temp_dir) / "source.txt"
            compressed_path = Path(temp_dir) / "source.txt.cjz"
            restored_path = Path(temp_dir) / "restored.txt"
            source_path.write_bytes(b"Cereja CLI compression test.\n" * 50)

            with redirect_stdout(io.StringIO()):
                compress_code = main(["compress", str(source_path), "-o", str(compressed_path)])
                decompress_code = main(["decompress", str(compressed_path), "-o", str(restored_path)])

            self.assertEqual(compress_code, 0)
            self.assertEqual(decompress_code, 0)
            self.assertEqual(restored_path.read_bytes(), source_path.read_bytes())

    def test_compress_encrypt_and_decompress_file_restore_original_bytes(self):
        with temporary_workspace_directory() as temp_dir:
            source_path = Path(temp_dir) / "source.txt"
            compressed_path = Path(temp_dir) / "source.txt.cjz"
            restored_path = Path(temp_dir) / "restored.txt"
            source_path.write_bytes(b"Cereja encrypted compression test.\n" * 50)

            with patch("getpass.getpass", side_effect=["password", "password", "password"]):
                with redirect_stdout(io.StringIO()):
                    compress_code = main(["compress", str(source_path), "-o", str(compressed_path), "--encrypt"])
                    decompress_code = main(["decompress", str(compressed_path), "-o", str(restored_path)])

            self.assertEqual(compress_code, 0)
            self.assertEqual(decompress_code, 0)
            self.assertEqual(restored_path.read_bytes(), source_path.read_bytes())

    def test_compress_and_decompress_directory_restore_files(self):
        with temporary_workspace_directory() as temp_dir:
            source_dir = Path(temp_dir) / "source"
            nested_dir = source_dir / "nested"
            nested_dir.mkdir(parents=True)
            (source_dir / "root.txt").write_bytes(b"root content")
            (nested_dir / "child.txt").write_bytes(b"child content")
            archive_path = Path(temp_dir) / "source.cjz"
            restored_dir = Path(temp_dir) / "restored"

            with redirect_stdout(io.StringIO()):
                compress_code = main(["compress", str(source_dir), "-o", str(archive_path)])
                decompress_code = main(
                    ["decompress", str(archive_path), "-o", str(restored_dir), "--archive-type", "dir"]
                )

            self.assertEqual(compress_code, 0)
            self.assertEqual(decompress_code, 0)
            self.assertEqual((restored_dir / "root.txt").read_bytes(), b"root content")
            self.assertEqual((restored_dir / "nested" / "child.txt").read_bytes(), b"child content")

    def test_compress_directory_enables_progress_by_default(self):
        with temporary_workspace_directory() as temp_dir:
            source_dir = Path(temp_dir) / "source"
            source_dir.mkdir()
            archive_path = Path(temp_dir) / "archive.cjz"

            with patch("cereja.cli.compress_dir", return_value=(str(archive_path), compression_stats())) as compress_dir:
                with redirect_stdout(io.StringIO()):
                    exit_code = main(["compress", str(source_dir), "-o", str(archive_path)])

            self.assertEqual(exit_code, 0)
            compress_dir.assert_called_once_with(
                str(source_dir),
                str(archive_path),
                strategy="auto",
                verbose=True,
            )

    def test_compress_directory_quiet_disables_progress(self):
        with temporary_workspace_directory() as temp_dir:
            source_dir = Path(temp_dir) / "source"
            source_dir.mkdir()
            archive_path = Path(temp_dir) / "archive.cjz"

            with patch("cereja.cli.compress_dir", return_value=(str(archive_path), compression_stats())) as compress_dir:
                with redirect_stdout(io.StringIO()):
                    exit_code = main(["compress", str(source_dir), "-o", str(archive_path), "--quiet"])

            self.assertEqual(exit_code, 0)
            compress_dir.assert_called_once_with(
                str(source_dir),
                str(archive_path),
                strategy="auto",
                verbose=False,
            )

    def test_compress_current_directory_uses_resolved_directory_name(self):
        with temporary_workspace_directory() as temp_dir:
            workspace = Path(temp_dir)
            expected_archive = Path(workspace.name + ".cjz")

            with working_directory(workspace):
                with patch(
                    "cereja.cli.compress_dir",
                    return_value=(str(expected_archive), compression_stats()),
                ) as compress_dir:
                    with redirect_stdout(io.StringIO()):
                        exit_code = main(["compress", ".", "--quiet"])

            self.assertEqual(exit_code, 0)
            compress_dir.assert_called_once_with(
                ".",
                str(expected_archive),
                strategy="auto",
                verbose=False,
            )

    def test_compress_directory_output_without_suffix_adds_cjz(self):
        with temporary_workspace_directory() as temp_dir:
            source_dir = Path(temp_dir) / "source"
            source_dir.mkdir()
            output_path = Path(temp_dir) / "archive"
            expected_archive = Path(temp_dir) / "archive.cjz"

            with patch("cereja.cli.compress_dir", return_value=(str(expected_archive), compression_stats())) as compress_dir:
                with redirect_stdout(io.StringIO()):
                    exit_code = main(["compress", str(source_dir), "-o", str(output_path), "--quiet"])

            self.assertEqual(exit_code, 0)
            compress_dir.assert_called_once_with(
                str(source_dir),
                str(expected_archive),
                strategy="auto",
                verbose=False,
            )

    def test_compress_file_enables_progress_by_default(self):
        with temporary_workspace_directory() as temp_dir:
            source_path = Path(temp_dir) / "source.txt"
            archive_path = Path(temp_dir) / "source.txt.cjz"
            source_path.write_text("content", encoding="utf-8")

            with patch("cereja.cli.compress_file", return_value=(str(archive_path), compression_stats())) as compress_file:
                with redirect_stdout(io.StringIO()):
                    exit_code = main(["compress", str(source_path), "-o", str(archive_path)])

            self.assertEqual(exit_code, 0)
            compress_file.assert_called_once_with(
                str(source_path),
                str(archive_path),
                strategy="auto",
                verbose=True,
            )

    def test_compress_file_quiet_disables_progress(self):
        with temporary_workspace_directory() as temp_dir:
            source_path = Path(temp_dir) / "source.txt"
            archive_path = Path(temp_dir) / "source.txt.cjz"
            source_path.write_text("content", encoding="utf-8")

            with patch("cereja.cli.compress_file", return_value=(str(archive_path), compression_stats())) as compress_file:
                with redirect_stdout(io.StringIO()):
                    exit_code = main(["compress", str(source_path), "-o", str(archive_path), "--quiet"])

            self.assertEqual(exit_code, 0)
            compress_file.assert_called_once_with(
                str(source_path),
                str(archive_path),
                strategy="auto",
                verbose=False,
            )

    def test_compress_file_output_without_suffix_adds_cjz(self):
        with temporary_workspace_directory() as temp_dir:
            source_path = Path(temp_dir) / "source.txt"
            output_path = Path(temp_dir) / "archive"
            expected_archive = Path(temp_dir) / "archive.cjz"
            source_path.write_text("content", encoding="utf-8")

            with patch(
                "cereja.cli.compress_file",
                return_value=(str(expected_archive), compression_stats()),
            ) as compress_file:
                with redirect_stdout(io.StringIO()):
                    exit_code = main(["compress", str(source_path), "-o", str(output_path), "--quiet"])

            self.assertEqual(exit_code, 0)
            compress_file.assert_called_once_with(
                str(source_path),
                str(expected_archive),
                strategy="auto",
                verbose=False,
            )

    def test_decompress_directory_enables_progress_by_default(self):
        with temporary_workspace_directory() as temp_dir:
            archive_path = Path(temp_dir) / "archive.cjz"
            output_dir = Path(temp_dir) / "output"
            archive_path.write_bytes(b"archive")

            with patch("cereja.cli.decompress_dir", return_value=str(output_dir)) as decompress_dir:
                with redirect_stdout(io.StringIO()):
                    exit_code = main(
                        ["decompress", str(archive_path), "-o", str(output_dir), "--archive-type", "dir"]
                    )

            self.assertEqual(exit_code, 0)
            decompress_dir.assert_called_once_with(str(archive_path), str(output_dir), verbose=True)

    def test_decompress_directory_quiet_disables_progress(self):
        with temporary_workspace_directory() as temp_dir:
            archive_path = Path(temp_dir) / "archive.cjz"
            output_dir = Path(temp_dir) / "output"
            archive_path.write_bytes(b"archive")

            with patch("cereja.cli.decompress_dir", return_value=str(output_dir)) as decompress_dir:
                with redirect_stdout(io.StringIO()):
                    exit_code = main(
                        [
                            "decompress",
                            str(archive_path),
                            "-o",
                            str(output_dir),
                            "--archive-type",
                            "dir",
                            "--quiet",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            decompress_dir.assert_called_once_with(str(archive_path), str(output_dir), verbose=False)

    def test_encrypt_and_decrypt_file_restore_original_bytes(self):
        with temporary_workspace_directory() as temp_dir:
            source_path = Path(temp_dir) / "secret.bin"
            encrypted_path = Path(temp_dir) / "secret.enc"
            restored_path = Path(temp_dir) / "secret.restored"
            source_path.write_bytes(b"secret bytes\x00\x01\x02")

            with patch("getpass.getpass", side_effect=["password", "password"]), redirect_stdout(io.StringIO()):
                encrypt_code = main(["encrypt", str(source_path), "-o", str(encrypted_path)])
            with patch("getpass.getpass", return_value="password"), redirect_stdout(io.StringIO()):
                decrypt_code = main(["decrypt", str(encrypted_path), "-o", str(restored_path)])

            self.assertEqual(encrypt_code, 0)
            self.assertEqual(decrypt_code, 0)
            self.assertEqual(restored_path.read_bytes(), source_path.read_bytes())

    def test_encrypt_fails_when_password_confirmation_differs(self):
        with temporary_workspace_directory() as temp_dir:
            source_path = Path(temp_dir) / "secret.txt"
            encrypted_path = Path(temp_dir) / "secret.enc"
            source_path.write_text("secret", encoding="utf-8")
            stderr = io.StringIO()

            with patch("getpass.getpass", side_effect=["password", "different"]):
                with redirect_stderr(stderr):
                    exit_code = main(["encrypt", str(source_path), "-o", str(encrypted_path)])

            self.assertEqual(exit_code, 1)
            self.assertFalse(encrypted_path.exists())
            self.assertIn("Password confirmation does not match", stderr.getvalue())

    def test_compress_encrypt_fails_when_password_confirmation_differs(self):
        with temporary_workspace_directory() as temp_dir:
            source_path = Path(temp_dir) / "source.txt"
            archive_path = Path(temp_dir) / "source.cjz"
            source_path.write_text("secret", encoding="utf-8")
            stderr = io.StringIO()

            with patch("getpass.getpass", side_effect=["password", "different"]):
                with redirect_stderr(stderr):
                    exit_code = main(["compress", str(source_path), "-o", str(archive_path), "--encrypt"])

            self.assertEqual(exit_code, 1)
            self.assertFalse(archive_path.exists())
            self.assertIn("Password confirmation does not match", stderr.getvalue())

    def test_existing_output_fails_without_force(self):
        with temporary_workspace_directory() as temp_dir:
            source_path = Path(temp_dir) / "source.txt"
            output_path = Path(temp_dir) / "source.cjz"
            source_path.write_text("content", encoding="utf-8")
            output_path.write_bytes(b"existing")
            stderr = io.StringIO()

            with redirect_stderr(stderr), redirect_stdout(io.StringIO()):
                exit_code = main(["compress", str(source_path), "-o", str(output_path)])

            self.assertEqual(exit_code, 1)
            self.assertEqual(output_path.read_bytes(), b"existing")
            self.assertIn("Output already exists", stderr.getvalue())

    def test_tree_command_renders_explicit_path(self):
        with temporary_workspace_directory() as temp_dir:
            root = Path(temp_dir) / "project"
            root.mkdir()
            (root / "README.md").write_text("readme", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(["tree", str(root)])

            self.assertEqual(exit_code, 0)
            self.assertEqual(output.getvalue(), "project/\n└── README.md\n")

    def test_tree_command_defaults_to_current_directory(self):
        with temporary_workspace_directory() as temp_dir:
            root = Path(temp_dir) / "project"
            root.mkdir()
            (root / "README.md").write_text("readme", encoding="utf-8")
            output = io.StringIO()

            with working_directory(root), redirect_stdout(output):
                exit_code = main(["tree"])

            self.assertEqual(exit_code, 0)
            self.assertEqual(output.getvalue(), "project/\n└── README.md\n")

    def test_tree_command_reports_missing_path(self):
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            exit_code = main(["tree", "missing-tree-root"])

        self.assertEqual(exit_code, 1)
        self.assertIn("Path not found", stderr.getvalue())

    def test_tree_command_rejects_negative_depth(self):
        result = subprocess.run(
            [sys.executable, "-m", "cereja", "tree", "--depth", "-1"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("must be non-negative", result.stderr)

    def test_tree_command_reconfigures_legacy_console_encoding(self):
        with temporary_workspace_directory() as temp_dir:
            root = Path(temp_dir) / "project"
            root.mkdir()
            (root / "README.md").write_text("readme", encoding="utf-8")
            buffer = io.BytesIO()
            stream = io.TextIOWrapper(buffer, encoding="cp1252")

            with patch("sys.stdout", stream):
                exit_code = main(["tree", str(root)])
                stream.flush()

            self.assertEqual(exit_code, 0)
            output = buffer.getvalue().decode("utf-8").replace("\r\n", "\n")
            self.assertEqual(output, "project/\n└── README.md\n")

    def test_context_search_emits_stable_json(self):
        with temporary_workspace_directory() as temp_dir:
            root = Path(temp_dir) / "docs"
            root.mkdir()
            (root / "guide.md").write_text("auth cache", encoding="utf-8")
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                exit_code = main([
                    "context", "search", "--root", str(root),
                    "--query", "auth cache", "--format", "json",
                ])

            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["mode"], "search")
            self.assertEqual(payload["results"][0]["relative_path"], "guide.md")

    def test_context_search_supports_multiple_roots_and_extensions(self):
        with temporary_workspace_directory() as temp_dir:
            first = Path(temp_dir) / "first"
            second = Path(temp_dir) / "second"
            first.mkdir()
            second.mkdir()
            (first / "one.md").write_text("needle", encoding="utf-8")
            (second / "two.TXT").write_text("needle", encoding="utf-8")
            (second / "ignored.py").write_text("needle", encoding="utf-8")
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                exit_code = main([
                    "context", "search", "--root", str(first),
                    "--root", str(second), "--query", "needle",
                    "--extension", "md", "--extension", ".txt",
                    "--format", "json",
                ])

            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(
                [item["relative_path"] for item in payload["results"]],
                ["one.md", "two.TXT"],
            )

    def test_context_list_emits_text_metadata_without_content(self):
        with temporary_workspace_directory() as temp_dir:
            root = Path(temp_dir) / "docs"
            root.mkdir()
            (root / "guide.md").write_text("private full content", encoding="utf-8")
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                exit_code = main(["context", "list", "--root", str(root)])

            self.assertEqual(exit_code, 0)
            self.assertIn("guide.md", stdout.getvalue())
            self.assertIn("bytes", stdout.getvalue())
            self.assertNotIn("private full content", stdout.getvalue())

    def test_context_reports_missing_root_only_to_stderr(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main([
                "context", "list", "--root", "missing-context-root",
                "--format", "json",
            ])

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Path not found", stderr.getvalue())

    def test_context_translates_api_value_error_to_cli_error(self):
        stderr = io.StringIO()

        with patch(
            "cereja.cli.search_text_context", side_effect=ValueError("invalid context")
        ), redirect_stderr(stderr):
            exit_code = main([
                "context", "search", "--root", ".", "--query", "needle"
            ])

        self.assertEqual(exit_code, 1)
        self.assertIn("invalid context", stderr.getvalue())

    def test_non_context_value_error_is_not_translated(self):
        with patch("cereja.cli._handle_tree", side_effect=ValueError("unrelated")):
            with self.assertRaisesRegex(ValueError, "unrelated"):
                main(["tree", "."])

    def test_context_rejects_zero_limit(self):
        result = subprocess.run(
            [
                sys.executable, "-m", "cereja", "context", "search",
                "--root", ".", "--query", "needle", "--max-results", "0",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("must be greater than zero", result.stderr)

    def test_context_search_requires_query(self):
        result = subprocess.run(
            [sys.executable, "-m", "cereja", "context", "search", "--root", "."],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("--query", result.stderr)


if __name__ == "__main__":
    unittest.main()
