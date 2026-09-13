import json
import unittest

from cereja.system.hardware import (
    BIOSInfo,
    CPUInfo,
    GPUInfo,
    HardwareInfo,
    MemoryInfo,
    MotherboardInfo,
    OperatingSystemInfo,
    SystemInfo,
)


class SystemInfoModelTest(unittest.TestCase):
    def test_hardware_info_serializes_nested_models(self):
        info = HardwareInfo(
            system=SystemInfo(manufacturer="Acer", model="Predator", architecture="x64", total_memory_bytes=32),
            os=OperatingSystemInfo(name="Windows", edition="Pro", version="24H2", build="26100", architecture="x64"),
            cpu=CPUInfo(name="CPU", cores=24, logical_processors=24),
            memory=(MemoryInfo(capacity_bytes=32, manufacturer="Micron", speed_mts=6400),),
            gpus=(GPUInfo(name="RTX", manufacturer="NVIDIA"),),
            motherboard=MotherboardInfo(manufacturer="ARL", product="Macan_ARX", version="V1.26"),
            bios=BIOSInfo(manufacturer="INSYDE", version="V1.26", release_date="2026-02-22"),
        )
        payload = info.to_dict()
        self.assertEqual(payload["system"]["manufacturer"], "Acer")
        self.assertEqual(payload["memory"][0]["speed_mts"], 6400)
        self.assertEqual(json.loads(info.to_json())["gpus"][0]["name"], "RTX")

    def test_models_are_immutable(self):
        info = CPUInfo(name="CPU", cores=8, logical_processors=16)
        with self.assertRaises((AttributeError, TypeError)):
            info.cores = 10

    def test_sensitive_identifiers_are_explicit_fields(self):
        board = MotherboardInfo(manufacturer="Vendor", product="Board", serial_number="secret")
        bios = BIOSInfo(manufacturer="Vendor", version="1", serial_number="bios-secret")
        self.assertEqual(board.serial_number, "secret")
        self.assertEqual(bios.serial_number, "bios-secret")


if __name__ == "__main__":
    unittest.main()
