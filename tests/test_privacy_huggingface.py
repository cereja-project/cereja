import io
import json
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from cereja.privacy import huggingface


class HuggingFacePrivacyTest(unittest.TestCase):
    def test_offline_environment_disables_network_clients_and_removes_tokens(self):
        env = huggingface.offline_environment({
            "PATH": "demo",
            "HF_TOKEN": "secret",
            "HUGGING_FACE_HUB_TOKEN": "legacy-secret",
        })
        self.assertEqual(env["PATH"], "demo")
        self.assertEqual(env["HF_HUB_OFFLINE"], "1")
        self.assertEqual(env["HF_DATASETS_OFFLINE"], "1")
        self.assertEqual(env["TRANSFORMERS_OFFLINE"], "1")
        self.assertEqual(env["HF_HUB_DISABLE_TELEMETRY"], "1")
        self.assertEqual(env["DO_NOT_TRACK"], "1")
        self.assertEqual(env["HF_HUB_DISABLE_IMPLICIT_TOKEN"], "1")
        self.assertNotIn("HF_TOKEN", env)
        self.assertNotIn("HUGGING_FACE_HUB_TOKEN", env)

    def test_download_environment_keeps_telemetry_off_and_only_uses_explicit_token(self):
        env = huggingface.download_environment(
            token="temporary-secret",
            base_env={"HUGGING_FACE_HUB_TOKEN": "inherited-secret"},
        )
        self.assertEqual(env["HF_HUB_OFFLINE"], "0")
        self.assertEqual(env["HF_DATASETS_OFFLINE"], "0")
        self.assertEqual(env["TRANSFORMERS_OFFLINE"], "0")
        self.assertEqual(env["HF_HUB_DISABLE_TELEMETRY"], "1")
        self.assertEqual(env["DO_NOT_TRACK"], "1")
        self.assertEqual(env["HF_HUB_DISABLE_IMPLICIT_TOKEN"], "0")
        self.assertEqual(env["HF_TOKEN"], "temporary-secret")
        self.assertNotIn("HUGGING_FACE_HUB_TOKEN", env)

    def test_public_download_does_not_inherit_parent_token(self):
        env = huggingface.download_environment(
            base_env={"HF_TOKEN": "do-not-forward"},
        )
        self.assertNotIn("HF_TOKEN", env)
        self.assertEqual(env["HF_HUB_DISABLE_IMPLICIT_TOKEN"], "1")

    def test_status_never_returns_secret_value(self):
        result = huggingface.status({
            "HF_TOKEN": "top-secret",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "DO_NOT_TRACK": "1",
            "HF_HUB_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
        })
        self.assertTrue(result["token_present"])
        self.assertNotIn("top-secret", json.dumps(result))
        self.assertTrue(result["offline"])
        self.assertEqual(result["network_isolation"], "not_enforced")

    @patch("cereja.privacy.huggingface.subprocess.run")
    def test_run_passes_policy_only_to_child(self, run):
        run.return_value = SimpleNamespace(returncode=0)
        base = {"HF_TOKEN": "parent-token", "PATH": "demo"}
        huggingface.run(["python", "app.py"], offline=True, base_env=base)
        child_env = run.call_args.kwargs["env"]
        self.assertEqual(child_env["HF_HUB_OFFLINE"], "1")
        self.assertNotIn("HF_TOKEN", child_env)
        self.assertEqual(base["HF_TOKEN"], "parent-token")
        self.assertFalse(run.call_args.kwargs["check"])


class HuggingFacePrivacyCliTest(unittest.TestCase):
    def test_status_json_is_machine_readable(self):
        from cereja.commands import privacy

        stdout = io.StringIO()
        with patch("cereja.commands.privacy.huggingface.status", return_value={
            "provider": "huggingface",
            "mode": "offline",
            "offline": True,
            "telemetry_disabled": True,
            "implicit_token_disabled": True,
            "token_present": False,
            "network_isolation": "not_enforced",
            "environment": {},
        }), redirect_stdout(stdout):
            result = privacy.main(["huggingface", "status", "--json"])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(stdout.getvalue())["mode"], "offline")

    def test_offline_run_strips_separator_and_returns_child_code(self):
        from cereja.commands import privacy

        with patch("cereja.commands.privacy.huggingface.run", return_value=SimpleNamespace(returncode=7)) as run:
            result = privacy.main(["huggingface", "run", "--", "python", "app.py"])
        self.assertEqual(result, 7)
        run.assert_called_once_with(["python", "app.py"], offline=True, cwd=None)

    def test_download_prompts_for_token_without_persisting_it(self):
        from cereja.commands import privacy

        with patch("cereja.commands.privacy.getpass.getpass", return_value="temporary-token"), patch(
            "cereja.commands.privacy.huggingface.run", return_value=SimpleNamespace(returncode=0)
        ) as run:
            result = privacy.main(["huggingface", "download", "--", "hf", "download", "org/model"])
        self.assertEqual(result, 0)
        run.assert_called_once_with(
            ["hf", "download", "org/model"],
            offline=False,
            token="temporary-token",
            cwd=None,
        )

    def test_public_download_requires_explicit_no_token(self):
        from cereja.commands import privacy

        with patch("cereja.commands.privacy.huggingface.run", return_value=SimpleNamespace(returncode=0)) as run:
            result = privacy.main([
                "huggingface", "download", "--no-token", "--", "hf", "download", "org/public-model"
            ])
        self.assertEqual(result, 0)
        self.assertIsNone(run.call_args.kwargs["token"])


if __name__ == "__main__":
    unittest.main()
