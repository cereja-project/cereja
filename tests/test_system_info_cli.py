import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from cereja.entrypoint import main
from cereja.system.hardware import CPUInfo, HardwareInfo, OperatingSystemInfo, SystemInfo


_SAMPLE = HardwareInfo(
    system=SystemInfo(manufacturer="Acer", model="Predator", architecture="x64", total_memory_bytes=34359738368),
    os=OperatingSystemInfo(name="Windows 11", edition="Pro", version="24H2", build="26100", architecture="x64", kernel="Windows NT"),
    cpu=CPUInfo(name="Intel CPU", manufacturer="Intel", cores=24, logical_processors=24),
)


class SystemInfoCliTest(unittest.TestCase):
    def run_cli(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_visual_output_is_grouped_and_human_readable(self):
        with patch("cereja.system.hardware.info", return_value=_SAMPLE):
            code, stdout, stderr = self.run_cli(["system", "info"])
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Cereja System Info", stdout)
        self.assertIn("System", stdout)
        self.assertIn("Operating System", stdout)
        self.assertIn("CPU", stdout)
        self.assertIn("Predator", stdout)
        self.assertIn("32.0 GiB", stdout)

    def test_json_output_contains_only_json(self):
        with patch("cereja.system.hardware.info", return_value=_SAMPLE):
            code, stdout, stderr = self.run_cli(["system", "info", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertEqual(payload["system"]["manufacturer"], "Acer")
        self.assertNotIn("Cereja System Info", stdout)

    def test_flags_are_forwarded_to_collector(self):
        with patch("cereja.system.hardware.info", return_value=_SAMPLE) as collect:
            code, _, _ = self.run_cli([
                "system", "info", "--full", "--sensitive",
                "--section", "cpu", "--section", "os",
            ])
        self.assertEqual(code, 0)
        collect.assert_called_once_with(
            detail="full", include_sensitive=True, sections=["cpu", "os"]
        )

    def test_system_without_info_is_usage_error(self):
        code, _, stderr = self.run_cli(["system"])
        self.assertEqual(code, 2)
        self.assertIn("usage:", stderr.lower())


if __name__ == "__main__":
    unittest.main()
