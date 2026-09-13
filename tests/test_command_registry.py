import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import Mock, patch


EXPECTED_COMMANDS = (
    "compress",
    "decompress",
    "encrypt",
    "decrypt",
    "tree",
    "context",
    "security",
    "http",
    "download",
    "system",
    "module",
)


class CommandRegistryTest(unittest.TestCase):
    def test_registry_is_complete_and_unique(self):
        from cereja.commands.registry import COMMANDS

        self.assertEqual(tuple(command.name for command in COMMANDS), EXPECTED_COMMANDS)
        self.assertEqual(len({command.name for command in COMMANDS}), len(COMMANDS))
        self.assertTrue(all(command.help for command in COMMANDS))
        self.assertTrue(all(command.module.startswith("cereja.commands.") for command in COMMANDS))

    def test_root_help_lists_every_registered_command(self):
        result = subprocess.run(
            [sys.executable, "-m", "cereja", "--help"],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Cereja Tools.", result.stdout)
        for command in EXPECTED_COMMANDS:
            self.assertIn(command, result.stdout)

    def test_root_help_does_not_import_command_implementations(self):
        script = r'''
import contextlib
import io
import json
import sys
from cereja.entrypoint import main
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
blocked = [
    name for name in sys.modules
    if name.startswith((
        "cereja.http",
        "cereja.security._analysis",
        "cereja.system.hardware",
        "cereja.hashtools._compress",
        "cereja.system._context.cache_db",
    ))
]
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

    def test_selected_command_is_imported_and_receives_remaining_arguments(self):
        from cereja.entrypoint import main

        command_module = Mock()
        command_module.main.return_value = 7
        with patch("cereja.entrypoint.importlib.import_module", return_value=command_module) as importer:
            result = main(["tree", ".", "--depth", "2"])

        self.assertEqual(result, 7)
        importer.assert_called_once_with("cereja.commands.tree")
        command_module.main.assert_called_once_with([".", "--depth", "2"])

    def test_legacy_startmodule_routes_to_module_create(self):
        from cereja.entrypoint import main

        command_module = Mock()
        command_module.main.return_value = 0
        with patch("cereja.entrypoint.importlib.import_module", return_value=command_module) as importer:
            result = main(["--startmodule", "demo/tools.py"])

        self.assertEqual(result, 0)
        importer.assert_called_once_with("cereja.commands.module")
        command_module.main.assert_called_once_with(["create", "demo/tools.py"])

    def test_unknown_command_is_a_standard_usage_error(self):
        from cereja.entrypoint import main

        stderr = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as raised:
                main(["does-not-exist"])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("invalid choice", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
