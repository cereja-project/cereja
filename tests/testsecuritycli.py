import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from cereja.security._cli import main


class SecurityCliTest(unittest.TestCase):
    def test_analyze_json_outputs_structured_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.txt"
            path.write_text("powershell -c whoami", encoding="utf-8")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(["analyze", str(path), "--format", "json"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["path"], "sample.txt")
        self.assertIn("risk_level", payload)
        self.assertIn("hashes", payload)

    def test_analyze_can_write_markdown_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.txt"
            output = Path(directory) / "report.md"
            path.write_text("powershell -c whoami", encoding="utf-8")
            exit_code = main(["analyze", str(path), "--output", str(output)])
            rendered = output.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn("Cereja Security Analysis", rendered)
        self.assertIn("command.execution", rendered)

    def test_missing_input_returns_error_code_without_traceback(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = main(["analyze", "does-not-exist.bin"])

        self.assertEqual(exit_code, 1)
        self.assertIn("Error:", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
