import io
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from cereja.commands import protect
from cereja.protect import DEFAULT_KEY_ENV


class ProtectCliTest(unittest.TestCase):
    def test_environment_key_avoids_interactive_prompt(self):
        with patch.dict(
            protect.os.environ,
            {DEFAULT_KEY_ENV: "secret"},
            clear=True,
        ), patch.object(
            protect.getpass,
            "getpass",
        ) as getpass_mock, patch.object(
            protect,
            "protect_path",
            return_value=Path("out/samplepkg"),
        ) as operation, patch(
            "builtins.print",
        ):
            result = protect.main([
                "samplepkg",
                "-o",
                "out",
                "--include-extension",
                ".yaml",
                "--force",
            ])

        self.assertEqual(result, 0)
        getpass_mock.assert_not_called()
        operation.assert_called_once_with(
            "samplepkg",
            "out",
            "secret",
            key_env=DEFAULT_KEY_ENV,
            static_extensions=[".yaml"],
            force=True,
        )

    def test_interactive_password_is_confirmed(self):
        with patch.dict(
            protect.os.environ,
            {},
            clear=True,
        ), patch.object(
            protect.getpass,
            "getpass",
            side_effect=["secret", "secret"],
        ), patch.object(
            protect,
            "protect_path",
            return_value=Path(
                "cereja-protected/samplepkg"
            ),
        ) as operation, patch(
            "builtins.print",
        ):
            result = protect.main([
                "samplepkg",
            ])

        self.assertEqual(result, 0)
        operation.assert_called_once_with(
            "samplepkg",
            "cereja-protected",
            "secret",
            key_env=DEFAULT_KEY_ENV,
            static_extensions=[],
            force=False,
        )

    def test_password_mismatch_returns_cli_error(self):
        stderr = io.StringIO()
        with patch.dict(
            protect.os.environ,
            {},
            clear=True,
        ), patch.object(
            protect.getpass,
            "getpass",
            side_effect=["one", "two"],
        ), redirect_stderr(stderr):
            result = protect.main([
                "samplepkg",
            ])

        self.assertEqual(result, 1)
        self.assertIn(
            "Password confirmation does not match",
            stderr.getvalue(),
        )

    def test_root_registry_exposes_protect_command(self):
        from cereja.commands.registry import get_command

        command = get_command("protect")
        self.assertEqual(
            command.module,
            "cereja.commands.protect",
        )


if __name__ == "__main__":
    unittest.main()
