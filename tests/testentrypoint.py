import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cereja.entrypoint import main


class EntrypointTest(unittest.TestCase):
    def test_legacy_cli_main_delegates_to_entrypoint(self):
        import cereja.cli as legacy_cli

        with patch("cereja.entrypoint.main", return_value=4) as entrypoint_main:
            result = legacy_cli.main(["tree", "."])

        self.assertEqual(result, 4)
        entrypoint_main.assert_called_once_with(["tree", "."])

    def test_importing_legacy_cli_facade_does_not_load_implementations(self):
        script = r'''
import json
import sys
import cereja.cli
blocked = [name for name in sys.modules if name.startswith((
    "cereja.hashtools._compress",
    "cereja.hashtools._crypto",
    "cereja.system._context.cache_db",
    "cereja.file._io",
))]
print(json.dumps(blocked))
'''
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])

    def test_security_analyze_dispatches_through_commands_module(self):
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

    def test_security_legacy_cli_delegates_to_commands_module(self):
        from cereja.security import _cli

        with patch("cereja.commands.security.main", return_value=6) as security_main:
            result = _cli.main(["analyze", "sample.bin"])

        self.assertEqual(result, 6)
        security_main.assert_called_once_with(["analyze", "sample.bin"])


if __name__ == "__main__":
    unittest.main()
