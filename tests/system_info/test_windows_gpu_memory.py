"""Synthetic regressions for Windows GPU memory collection."""

import json
import subprocess
import unittest
from unittest.mock import patch

from cereja.system.hardware import _windows


def gpu(name="NVIDIA Example GPU", manufacturer="NVIDIA", memory=4293918720):
    return {
        "Name": name,
        "AdapterCompatibility": manufacturer,
        "AdapterRAM": memory,
        "DriverVersion": "1.2.3",
        "VideoProcessor": "Example processor",
    }


class WindowsGPUMemoryTest(unittest.TestCase):
    def collect(self, gpus, output="NVIDIA Example GPU, 8192\n", *,
                detail="full", sections=("gpu",), error=None, returncode=0):
        self.commands = []

        def run(args, **kwargs):
            self.commands.append((args, kwargs))
            if args[0] == "powershell":
                return subprocess.CompletedProcess(args, 0, json.dumps({"gpu": gpus}))
            if args[0] == "nvidia-smi":
                if error is not None:
                    raise error
                return subprocess.CompletedProcess(args, returncode, output)
            raise AssertionError(f"Unexpected command: {args[0]}")

        with patch("cereja.system.hardware._common.subprocess.run", side_effect=run):
            return _windows.collect(detail=detail, sections=sections)

    def test_memory_above_uint32_limit_comes_from_driver(self):
        result = self.collect([gpu()])
        self.assertEqual(result.gpus[0].adapter_memory_bytes, 8 * 1024 ** 3)
        self.assertEqual(result.gpus[0].driver_version, "1.2.3")
        self.assertEqual(result.gpus[0].processor, "Example processor")

    def test_hybrid_gpu_order_does_not_assign_discrete_memory_to_integrated_gpu(self):
        result = self.collect([gpu("Integrated Example", "Intel"), gpu()])
        self.assertIsNone(result.gpus[0].adapter_memory_bytes)
        self.assertEqual(result.gpus[1].adapter_memory_bytes, 8 * 1024 ** 3)

    def test_distinct_gpus_match_by_name_not_enumeration_order(self):
        result = self.collect(
            [gpu("NVIDIA Example A"), gpu("NVIDIA Example B")],
            "NVIDIA Example B, 24576\nNVIDIA Example A, 12288\n",
        )
        self.assertEqual([item.adapter_memory_bytes for item in result.gpus],
                         [12 * 1024 ** 3, 24 * 1024 ** 3])

    def test_matches_case_and_surrounding_whitespace(self):
        result = self.collect([gpu(" NVIDIA Example GPU ")],
                              "nvidia example gpu , 8192\r\n")
        self.assertEqual(result.gpus[0].adapter_memory_bytes, 8 * 1024 ** 3)

    def test_parses_quoted_csv_names(self):
        result = self.collect([gpu("NVIDIA Example, GPU")],
                              '"NVIDIA Example, GPU", 16384\n')
        self.assertEqual(result.gpus[0].adapter_memory_bytes, 16 * 1024 ** 3)

    def test_converts_reported_mib_without_rounding_to_marketed_capacity(self):
        result = self.collect([gpu()], "NVIDIA Example GPU, 8100\n")
        self.assertEqual(result.gpus[0].adapter_memory_bytes, 8100 * 1024 ** 2)

    def test_duplicate_cim_names_are_unknown(self):
        result = self.collect([gpu(), gpu()])
        self.assertEqual([item.adapter_memory_bytes for item in result.gpus],
                         [None, None])

    def test_name_collision_with_other_vendor_is_ambiguous(self):
        result = self.collect([gpu("Example GPU"), gpu("Example GPU", "AMD")],
                              "Example GPU, 8192\n")
        self.assertEqual([item.adapter_memory_bytes for item in result.gpus],
                         [None, None])

    def test_duplicate_driver_names_are_unknown_even_with_same_capacity(self):
        for second in ("8192", "16384", "[N/A]"):
            with self.subTest(second=second):
                result = self.collect([gpu()],
                                      f"NVIDIA Example GPU, 8192\nNVIDIA Example GPU, {second}\n")
                self.assertIsNone(result.gpus[0].adapter_memory_bytes)

    def test_unknown_or_invalid_driver_memory_does_not_fall_back_to_cim(self):
        for value in ("[N/A]", "N/A", "", "-1", "0", "nan", "inf", "8192.5", "8192 MiB"):
            with self.subTest(value=value):
                result = self.collect([gpu()], f"NVIDIA Example GPU, {value}\n")
                self.assertIsNone(result.gpus[0].adapter_memory_bytes)

    def test_empty_or_malformed_driver_output_is_unknown(self):
        for output in (None, "", "\n", "error", '"unterminated, 8192\n',
                       "NVIDIA Example GPU, 8192, unexpected\n"):
            with self.subTest(output=output):
                result = self.collect([gpu()], output)
                self.assertIsNone(result.gpus[0].adapter_memory_bytes)

    def test_missing_driver_command_is_unknown(self):
        result = self.collect([gpu()], error=FileNotFoundError())
        self.assertIsNone(result.gpus[0].adapter_memory_bytes)
        self.assertEqual(result.gpus[0].name, "NVIDIA Example GPU")

    def test_driver_timeout_is_unknown(self):
        result = self.collect([gpu()], error=subprocess.TimeoutExpired("nvidia-smi", 5))
        self.assertIsNone(result.gpus[0].adapter_memory_bytes)

    def test_failed_driver_command_does_not_parse_stdout(self):
        result = self.collect([gpu()], returncode=1)
        self.assertIsNone(result.gpus[0].adapter_memory_bytes)

    def test_unmatched_name_is_unknown(self):
        result = self.collect([gpu()], "NVIDIA Other GPU, 16384\n")
        self.assertIsNone(result.gpus[0].adapter_memory_bytes)

    def test_cim_memory_alone_is_never_treated_as_verified_vram(self):
        for value in (2 * 1024 ** 3, 4293918720, 0, None):
            with self.subTest(value=value):
                result = _windows._from_cim(
                    {"gpu": [gpu(memory=value)]}, detail="full",
                    include_sensitive=False, sections=("gpu",),
                )
                self.assertIsNone(result.gpus[0].adapter_memory_bytes)

    def test_non_nvidia_devices_do_not_probe_or_receive_nvidia_memory(self):
        for manufacturer in ("Intel", "AMD"):
            with self.subTest(manufacturer=manufacturer):
                result = self.collect([gpu("Other GPU", manufacturer)])
                self.assertIsNone(result.gpus[0].adapter_memory_bytes)
                self.assertEqual(len(self.commands), 1)

    def test_basic_inventory_does_not_probe_driver_memory(self):
        result = self.collect([gpu()], detail="basic")
        self.assertIsNone(result.gpus[0].adapter_memory_bytes)
        self.assertEqual(len(self.commands), 1)

    def test_unselected_gpu_section_does_not_probe_driver_memory(self):
        result = self.collect([gpu()], sections=("cpu",))
        self.assertEqual(result.gpus, ())
        self.assertEqual(len(self.commands), 1)

    def test_missing_or_invalid_cim_gpu_data_does_not_probe(self):
        for value in (None, [], [None, "invalid"], {}):
            with self.subTest(value=value):
                result = self.collect(value)
                self.assertTrue(all(item.adapter_memory_bytes is None for item in result.gpus))
                self.assertEqual(len(self.commands), 1)

    def test_single_cim_object_is_supported(self):
        result = self.collect(gpu())
        self.assertEqual(result.gpus[0].adapter_memory_bytes, 8 * 1024 ** 3)

    def test_driver_query_is_bounded_and_does_not_request_identifiers(self):
        result = self.collect([gpu()])
        self.assertEqual(result.gpus[0].adapter_memory_bytes, 8 * 1024 ** 3)
        args, kwargs = self.commands[-1]
        self.assertEqual(args, ["nvidia-smi", "--query-gpu=name,memory.total",
                                "--format=csv,noheader,nounits"])
        self.assertGreater(kwargs["timeout"], 0)
        self.assertLessEqual(kwargs["timeout"], 5)
        self.assertFalse(kwargs.get("shell", False))

    def test_json_preserves_numeric_bytes_and_null_unknown_values(self):
        result = self.collect([gpu("Integrated Example", "Intel"), gpu()])
        payload = json.loads(result.to_json())
        self.assertIsNone(payload["gpus"][0]["adapter_memory_bytes"])
        self.assertEqual(payload["gpus"][1]["adapter_memory_bytes"], 8 * 1024 ** 3)


if __name__ == "__main__":
    unittest.main()
