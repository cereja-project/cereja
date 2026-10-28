"""Tests for OpenHands process-scoped privacy profiles and CLI."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cereja.commands import privacy
from cereja.privacy import huggingface, openhands


class OpenHandsPrivacyTest(unittest.TestCase):
    def test_import_has_no_side_effects(self):
        code = (
            "import os, sys\n"
            "env_before = dict(os.environ)\n"
            "import cereja.privacy.openhands as oh\n"
            "import cereja.privacy as p\n"
            "assert dict(os.environ) == env_before\n"
            "assert 'openhands' in p.__all__\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, f"Import had side effects: {result.stderr}")

    def test_environment_does_not_mutate_parent(self):
        base = {"PATH": "demo_path", "CUSTOM_VAR": "custom_val"}
        original_base = dict(base)
        env_snapshot = dict(os.environ)

        child_env = openhands.environment("agent-server", base_env=base)

        self.assertEqual(base, original_base)
        self.assertEqual(dict(os.environ), env_snapshot)
        self.assertEqual(child_env["DO_NOT_TRACK"], "1")
        self.assertEqual(child_env["OH_TELEMETRY_EXPORTER"], "none")

    def test_empty_base_environment_is_respected(self):
        with patch.dict(os.environ, {"OH_TELEMETRY_POSTHOG_API_KEY": "parent_secret"}, clear=False):
            env = openhands.environment("agent-server", base_env={})
            self.assertNotIn("OH_TELEMETRY_POSTHOG_API_KEY", env)
            self.assertEqual(
                env,
                {"DO_NOT_TRACK": "1", "OH_TELEMETRY_EXPORTER": "none"},
            )

    def test_agent_server_overrides_telemetry_opt_in(self):
        base = {
            "DO_NOT_TRACK": "0",
            "OH_TELEMETRY_EXPORTER": "posthog",
            "KEEP_ME": "kept",
        }
        env = openhands.environment("agent-server", base_env=base)
        self.assertEqual(env["DO_NOT_TRACK"], "1")
        self.assertEqual(env["OH_TELEMETRY_EXPORTER"], "none")
        self.assertEqual(env["KEEP_ME"], "kept")

    def test_tracing_is_handled_independently_from_telemetry(self):
        base = {
            "DO_NOT_TRACK": "1",
            "OH_TELEMETRY_POSTHOG_API_KEY": "synth-ph-key",
            "OH_TELEMETRY_POSTHOG_HOST": "https://posthog.example.com",
            "OH_TELEMETRY_HTTP_ENDPOINT": "https://telemetry.example.com",
            "OH_TELEMETRY_HTTP_TOKEN": "synth-http-tok",
            "LMNR_PROJECT_API_KEY": "synth-lmnr-key",
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://localhost:4318/v1/traces",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318",
            "OTEL_ENDPOINT": "http://localhost:4317",
            "OTEL_EXPORTER_OTLP_TRACES_HEADERS": "Authorization=Bearer trace-secret",
            "OTEL_EXPORTER_OTLP_HEADERS": "Authorization=Bearer otel-secret",
            "SOME_OTHER_SETTING": "preserved",
        }
        env = openhands.environment("agent-server", base_env=base)

        for removed_var in openhands.AGENT_SERVER_REMOVED:
            self.assertNotIn(removed_var, env)

        self.assertEqual(env["SOME_OTHER_SETTING"], "preserved")
        self.assertEqual(env["DO_NOT_TRACK"], "1")
        self.assertEqual(env["OH_TELEMETRY_EXPORTER"], "none")

    def test_canvas_build_and_static_profiles_are_distinct(self):
        build_env = openhands.environment("canvas-build", base_env={})
        self.assertEqual(
            build_env,
            {"DO_NOT_TRACK": "1", "VITE_DO_NOT_TRACK": "1"},
        )
        self.assertNotIn("AGENT_CANVAS_DISABLE_TELEMETRY", build_env)

        static_env = openhands.environment("canvas-static", base_env={})
        self.assertEqual(
            static_env,
            {"DO_NOT_TRACK": "1", "AGENT_CANVAS_DISABLE_TELEMETRY": "1"},
        )
        self.assertNotIn("VITE_DO_NOT_TRACK", static_env)

        # Build flag alone does not satisfy runtime status of canvas-static
        st_static = openhands.status(environment=build_env, component="canvas-static")
        self.assertEqual(st_static["flags"]["AGENT_CANVAS_DISABLE_TELEMETRY"], "unset")

    def test_network_configuration_is_preserved(self):
        base = {
            "HTTP_PROXY": "http://proxy.internal:8080",
            "HTTPS_PROXY": "https://proxy.internal:8080",
            "NO_PROXY": "localhost,127.0.0.1",
        }
        env = openhands.environment("agent-server", base_env=base)
        self.assertEqual(env["HTTP_PROXY"], "http://proxy.internal:8080")
        self.assertEqual(env["HTTPS_PROXY"], "https://proxy.internal:8080")
        self.assertEqual(env["NO_PROXY"], "localhost,127.0.0.1")

        # No Hugging Face offline flags are added
        self.assertNotIn("HF_HUB_OFFLINE", env)
        self.assertNotIn("HF_DATASETS_OFFLINE", env)
        self.assertNotIn("TRANSFORMERS_OFFLINE", env)

    def test_security_credentials_are_preserved_but_not_reported(self):
        base = {
            "SESSION_API_KEY": "synth-session-key-xyz-123",
            "OH_SECRET_KEY": "synth-secret-key-abc-456",
            "PATH": "demo_path",
        }
        child_env = openhands.environment("agent-server", base_env=base)
        self.assertEqual(child_env["SESSION_API_KEY"], "synth-session-key-xyz-123")
        self.assertEqual(child_env["OH_SECRET_KEY"], "synth-secret-key-abc-456")

        st = openhands.status(environment=child_env, component="agent-server")
        serialized = json.dumps(st)
        self.assertNotIn("SESSION_API_KEY", serialized)
        self.assertNotIn("OH_SECRET_KEY", serialized)
        self.assertNotIn("synth-session-key-xyz-123", serialized)
        self.assertNotIn("synth-secret-key-abc-456", serialized)

    def test_status_does_not_echo_untrusted_values(self):
        untrusted_env = {
            "DO_NOT_TRACK": "MALFORMED_UNTRUSTED_FLAG_VAL",
            "OH_TELEMETRY_EXPORTER": "MALFORMED_EXPORTER_VAL",
            "OH_TELEMETRY_POSTHOG_API_KEY": "POSTHOG_SECRET_KEY_999",
            "OTEL_EXPORTER_OTLP_HEADERS": "OTEL_HEADER_SECRET_888",
        }
        st = openhands.status(environment=untrusted_env, component="agent-server")
        self.assertEqual(st["flags"]["DO_NOT_TRACK"], "conflicting")
        self.assertEqual(st["flags"]["OH_TELEMETRY_EXPORTER"], "conflicting")
        self.assertEqual(st["removable_variables"]["OH_TELEMETRY_POSTHOG_API_KEY"], "present")
        self.assertEqual(st["removable_variables"]["OTEL_EXPORTER_OTLP_HEADERS"], "present")

        serialized = json.dumps(st)
        self.assertNotIn("MALFORMED_UNTRUSTED_FLAG_VAL", serialized)
        self.assertNotIn("MALFORMED_EXPORTER_VAL", serialized)
        self.assertNotIn("POSTHOG_SECRET_KEY_999", serialized)
        self.assertNotIn("OTEL_HEADER_SECRET_888", serialized)

        rendered = privacy._render_openhands_status(st)
        self.assertNotIn("MALFORMED_UNTRUSTED_FLAG_VAL", rendered)
        self.assertNotIn("MALFORMED_EXPORTER_VAL", rendered)
        self.assertNotIn("POSTHOG_SECRET_KEY_999", rendered)
        self.assertNotIn("OTEL_HEADER_SECRET_888", rendered)

    def test_status_reports_unverified_security_boundaries(self):
        st = openhands.status(environment={}, component="agent-server")
        self.assertEqual(st["provider"], "openhands")
        self.assertEqual(st["component"], "agent-server")
        self.assertEqual(st["coverage_scope"], "child_environment_only")
        self.assertEqual(st["runtime_behavior"], "not_verified")
        self.assertEqual(st["network_isolation"], "not_enforced")
        self.assertEqual(st["outbound_content_filtering"], "not_enforced")
        self.assertEqual(st["model_routing"], "not_checked")
        self.assertEqual(st["critic"], "not_checked")
        self.assertEqual(st["webhooks"], "not_checked")
        self.assertEqual(st["local_content_logging"], "not_checked")

        # Explicitly ensure no false claims of protection
        self.assertNotIn("private", st)
        self.assertNotIn("secure", st)
        self.assertNotIn("no_data_leakage", st)

    @patch("cereja.privacy.openhands.subprocess.run")
    def test_invalid_command_never_spawns(self, mock_run):
        invalid_commands = [
            "python app.py",              # string
            b"python app.py",             # bytes
            [],                           # empty sequence
            ["python", 123],              # non-string item
            [""],                         # empty executable
            ["   "],                      # whitespace executable
        ]
        for cmd in invalid_commands:
            with self.subTest(cmd=cmd):
                with self.assertRaises((TypeError, ValueError)):
                    openhands.run(cmd, component="agent-server")
        mock_run.assert_not_called()

        with self.assertRaises(ValueError):
            openhands.run(["python"], component="invalid-comp")
        with self.assertRaises(TypeError):
            openhands.run(["python"])  # missing component
        mock_run.assert_not_called()

    @patch("cereja.privacy.openhands.subprocess.run")
    def test_run_preserves_argv_cwd_and_return_code(self, mock_run):
        mock_run.return_value = SimpleNamespace(returncode=42)
        base = {"SESSION_API_KEY": "my-sess-key"}

        res = openhands.run(
            ["python", "-m", "agent_server", "--port", "8000"],
            component="agent-server",
            cwd="test_dir",
            base_env=base,
        )

        self.assertEqual(res.returncode, 42)
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        self.assertEqual(args[0], ["python", "-m", "agent_server", "--port", "8000"])
        self.assertEqual(kwargs["cwd"], Path("test_dir"))
        self.assertFalse(kwargs["check"])
        self.assertFalse(kwargs.get("shell", False))
        self.assertEqual(kwargs["env"]["DO_NOT_TRACK"], "1")
        self.assertEqual(kwargs["env"]["OH_TELEMETRY_EXPORTER"], "none")
        self.assertEqual(kwargs["env"]["SESSION_API_KEY"], "my-sess-key")


class OpenHandsPrivacyCliTest(unittest.TestCase):
    def test_cli_launch_errors_are_sanitized(self):
        stderr = io.StringIO()
        with patch(
            "cereja.commands.privacy.openhands.run",
            side_effect=OSError("Synthetic error leaking secret-api-key-99999"),
        ), redirect_stderr(stderr):
            code = privacy.main([
                "openhands", "run", "--component", "agent-server", "--", "python", "app.py"
            ])
        self.assertEqual(code, 1)
        err_output = stderr.getvalue()
        self.assertNotIn("secret-api-key-99999", err_output)
        self.assertIn("Error: failed to launch OpenHands child process", err_output)

        stderr2 = io.StringIO()
        with patch(
            "cereja.commands.privacy.openhands.run",
            side_effect=ValueError("Invalid args with private-token-88888"),
        ), redirect_stderr(stderr2):
            code2 = privacy.main([
                "openhands", "run", "--component", "agent-server", "--", "python", "app.py"
            ])
        self.assertEqual(code2, 1)
        err_output2 = stderr2.getvalue()
        self.assertNotIn("private-token-88888", err_output2)

    def test_cli_json_and_component_validation(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = privacy.main(["openhands", "status", "--component", "agent-server", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(stdout.getvalue())
        self.assertEqual(data["provider"], "openhands")
        self.assertEqual(data["component"], "agent-server")
        self.assertEqual(data["network_isolation"], "not_enforced")

        # Missing --component raises SystemExit with non-zero exit code
        with self.assertRaises(SystemExit) as cm:
            privacy.main(["openhands", "status"])
        self.assertNotEqual(cm.exception.code, 0)

        # Invalid --component raises SystemExit with non-zero exit code
        with self.assertRaises(SystemExit) as cm:
            privacy.main(["openhands", "status", "--component", "unknown-component"])
        self.assertNotEqual(cm.exception.code, 0)

        # Missing command after -- in run
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = privacy.main(["openhands", "run", "--component", "agent-server", "--"])
        self.assertEqual(code, 1)
        self.assertIn("Error: a child command is required after --", stderr.getvalue())

    def test_existing_huggingface_behavior_is_unchanged(self):
        base = {
            "HF_TOKEN": "secret",
            "HUGGING_FACE_HUB_TOKEN": "legacy-secret",
        }
        env = huggingface.offline_environment(base)
        self.assertEqual(env["HF_HUB_OFFLINE"], "1")
        self.assertEqual(env["HF_HUB_DISABLE_TELEMETRY"], "1")
        self.assertNotIn("HF_TOKEN", env)

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = privacy.main(["huggingface", "status", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["provider"], "huggingface")


class OpenHandsPrivacySubprocessSmokeTest(unittest.TestCase):
    def test_subprocess_smoke_verifies_environment_passing(self):
        """Smoke test with real Python child process verifying flag passage."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "output.json"
            base_env = {
                "OH_TELEMETRY_POSTHOG_API_KEY": "synth-posthog-key-12345",
                "SESSION_API_KEY": "synth-sess-key-99999",
                "PATH": os.environ.get("PATH", ""),
                "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            }
            child_code = (
                "import os, json, sys\n"
                "out = {\n"
                "    'dnt': os.environ.get('DO_NOT_TRACK'),\n"
                "    'exporter': os.environ.get('OH_TELEMETRY_EXPORTER'),\n"
                "    'has_posthog': 'OH_TELEMETRY_POSTHOG_API_KEY' in os.environ,\n"
                "    'has_session': 'SESSION_API_KEY' in os.environ,\n"
                "}\n"
                "with open(sys.argv[1], 'w') as f:\n"
                "    json.dump(out, f)\n"
            )
            result = openhands.run(
                [sys.executable, "-c", child_code, str(out_file)],
                component="agent-server",
                base_env=base_env,
            )
            self.assertEqual(result.returncode, 0)
            self.assertTrue(out_file.exists())
            with open(out_file) as f:
                data = json.load(f)
            self.assertEqual(data["dnt"], "1")
            self.assertEqual(data["exporter"], "none")
            self.assertFalse(data["has_posthog"])
            self.assertTrue(data["has_session"])


if __name__ == "__main__":
    unittest.main()
