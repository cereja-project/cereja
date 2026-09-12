import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from cereja.entrypoint import main
from http3._server import running_server


class DownloadCliTest(unittest.TestCase):
    def run_cli(self, *args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["download", *args])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_download_streams_to_explicit_destination(self):
        with tempfile.TemporaryDirectory() as directory, running_server() as (base, _):
            target = Path(directory) / "payload.bin"
            code, stdout, stderr = self.run_cli(base + "/large", "-o", str(target), "--quiet")
            self.assertEqual(target.stat().st_size, 65536)
            self.assertEqual(target.read_bytes(), b"x" * 65536)
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")

    def test_download_infers_filename_and_reports_completion(self):
        with tempfile.TemporaryDirectory() as directory, running_server() as (base, _):
            previous = os.getcwd()
            os.chdir(directory)
            try:
                code, stdout, stderr = self.run_cli(base + "/fixed")
                target = Path(directory) / "fixed"
                self.assertEqual(target.read_bytes(), b"hello")
            finally:
                os.chdir(previous)
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "")
        self.assertIn("Downloaded 5 bytes", stderr)
        self.assertIn("fixed", stderr)

    def test_download_follows_redirects_without_materializing_body(self):
        with tempfile.TemporaryDirectory() as directory, running_server() as (base, _):
            target = Path(directory) / "redirected.bin"
            code, _, stderr = self.run_cli(base + "/redirect", "-o", str(target), "--quiet")
            self.assertEqual(target.read_bytes(), b"hello")
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")

    def test_download_refuses_existing_destination_without_force(self):
        with tempfile.TemporaryDirectory() as directory, running_server() as (base, _):
            target = Path(directory) / "existing.bin"
            target.write_bytes(b"keep")
            code, _, stderr = self.run_cli(base + "/fixed", "-o", str(target), "--quiet")
            self.assertEqual(target.read_bytes(), b"keep")
            self.assertEqual(code, 1)
            self.assertIn("already exists", stderr)

            code, _, stderr = self.run_cli(base + "/fixed", "-o", str(target), "--force", "--quiet")
            self.assertEqual(target.read_bytes(), b"hello")
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")

    def test_download_http_error_leaves_no_destination(self):
        with tempfile.TemporaryDirectory() as directory, running_server() as (base, _):
            target = Path(directory) / "missing.bin"
            code, _, stderr = self.run_cli(base + "/not-found", "-o", str(target), "--quiet")
            self.assertFalse(target.exists())
        self.assertEqual(code, 1)
        self.assertIn("HTTP 404", stderr)

    def test_download_rejects_url_without_filename_when_output_is_missing(self):
        with running_server() as (base, _):
            code, _, stderr = self.run_cli(base + "/")
        self.assertEqual(code, 1)
        self.assertIn("Cannot infer destination filename", stderr)


if __name__ == "__main__":
    unittest.main()
