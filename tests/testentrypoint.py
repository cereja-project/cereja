import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cereja.entrypoint import main


class EntrypointTest(unittest.TestCase):
    def test_non_security_commands_delegate_to_existing_cli(self):
        with patch("cereja.entrypoint.legacy_main", return_value=4) as legacy_main:
            result = main(["tree", "."])

        self.assertEqual(result, 4)
        legacy_main.assert_called_once_with(["tree", "."])

    def test_security_analyze_dispatches_to_security_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.txt"
            path.write_text("powershell -c whoami", encoding="utf-8")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                result = main(["security", "analyze", str(path), "--format", "json"])

        self.assertEqual(result, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["path"], "sample.txt")
        self.assertIn("risk_score", payload)


if __name__ == "__main__":
    unittest.main()
