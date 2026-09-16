import unittest

from cereja.system.hardware import _linux, _macos, _windows


class WindowsBackendTest(unittest.TestCase):
    def test_maps_cim_payload_and_hides_sensitive_values(self):
        payload = {
            "computer": {
                "Manufacturer": "Acer",
                "Model": "Predator",
                "TotalPhysicalMemory": "34359738368",
            },
            "product": {
                "IdentifyingNumber": "SYSTEMSECRET",
                "UUID": "UUIDSECRET",
            },
            "os": {
                "Caption": "Microsoft Windows 11 Pro",
                "Version": "10.0.26100",
                "BuildNumber": "26100",
                "OSArchitecture": "64-bit",
                "CSName": "SECRET-PC",
            },
            "cpu": {
                "Name": "Intel CPU",
                "Manufacturer": "GenuineIntel",
                "NumberOfCores": 24,
                "NumberOfLogicalProcessors": 24,
                "MaxClockSpeed": 5400,
            },
            "memory": [{
                "Capacity": "34359738368",
                "Manufacturer": "Micron",
                "Speed": 6400,
                "ConfiguredClockSpeed": 6400,
                "PartNumber": "PART",
                "SerialNumber": "RAMSECRET",
            }],
            "gpu": [{
                "Name": "RTX 5070",
                "AdapterCompatibility": "NVIDIA",
                "AdapterRAM": "4293918720",
                "DriverVersion": "1.2",
                "VideoProcessor": "RTX",
            }],
            "board": {
                "Manufacturer": "ARL",
                "Product": "Macan_ARX",
                "Version": "V1.26",
                "SerialNumber": "BOARDSECRET",
            },
            "bios": {
                "Manufacturer": "INSYDE",
                "SMBIOSBIOSVersion": "V1.26",
                "ReleaseDate": "20260223000000.000000+000",
                "SerialNumber": "BIOSSECRET",
            },
        }
        basic = _windows._from_cim(
            payload,
            detail="basic",
            include_sensitive=False,
            sections=_windows.SECTIONS,
        )
        self.assertEqual(basic.system.manufacturer, "Acer")
        self.assertEqual(basic.cpu.cores, 24)
        self.assertEqual(basic.memory[0].speed_mts, 6400)
        self.assertIsNone(basic.memory[0].part_number)
        self.assertIsNone(basic.system.serial_number)
        self.assertIsNone(basic.system.hardware_uuid)
        self.assertIsNone(basic.motherboard.serial_number)
        self.assertIsNone(basic.os.hostname)

        full = _windows._from_cim(
            payload,
            detail="full",
            include_sensitive=True,
            sections=_windows.SECTIONS,
        )
        self.assertEqual(full.memory[0].part_number, "PART")
        self.assertEqual(full.system.serial_number, "SYSTEMSECRET")
        self.assertEqual(full.system.hardware_uuid, "UUIDSECRET")
        self.assertEqual(full.motherboard.serial_number, "BOARDSECRET")
        self.assertEqual(full.os.hostname, "SECRET-PC")
        self.assertIsNone(full.gpus[0].adapter_memory_bytes)


class LinuxBackendTest(unittest.TestCase):
    def test_collects_from_proc_sys_and_os_release(self):
        files = {
            "/etc/os-release": (
                'NAME="Ubuntu"\nVERSION_ID="24.04"\n'
                'PRETTY_NAME="Ubuntu 24.04 LTS"\n'
            ),
            "/proc/cpuinfo": (
                "model name\t: Example CPU\n"
                "vendor_id\t: GenuineIntel\n"
                "cpu cores\t: 8\n"
                "processor\t: 0\nprocessor\t: 1\n"
            ),
            "/proc/meminfo": "MemTotal:       32768000 kB\n",
            "/sys/class/dmi/id/sys_vendor": "Acer\n",
            "/sys/class/dmi/id/product_name": "Predator\n",
            "/sys/class/dmi/id/product_serial": "SECRET\n",
            "/sys/class/dmi/id/board_vendor": "ARL\n",
            "/sys/class/dmi/id/board_name": "Macan_ARX\n",
            "/sys/class/dmi/id/board_version": "V1\n",
            "/sys/class/dmi/id/board_serial": "BOARDSECRET\n",
            "/sys/class/dmi/id/bios_vendor": "Vendor\n",
            "/sys/class/dmi/id/bios_version": "1.0\n",
            "/sys/class/dmi/id/bios_date": "01/01/2026\n",
        }

        def read(path):
            return files.get(str(path))

        def run(args, timeout=5.0):
            if args and args[0] == "lspci":
                return (
                    "0000:00:02.0 VGA compatible controller: Intel Corporation Arc Graphics\n"
                    "0000:01:00.0 3D controller: NVIDIA Corporation Device 2f58\n"
                )
            return None

        result = _linux.collect(
            detail="basic",
            include_sensitive=False,
            sections=_linux.SECTIONS,
            _read=read,
            _runner=run,
        )
        self.assertEqual(result.system.manufacturer, "Acer")
        self.assertEqual(result.os.name, "Ubuntu")
        self.assertEqual(result.cpu.name, "Example CPU")
        self.assertEqual(result.system.total_memory_bytes, 32768000 * 1024)
        self.assertEqual(len(result.gpus), 2)
        self.assertEqual(result.gpus[1].manufacturer, "NVIDIA Corporation")
        self.assertIsNone(result.system.serial_number)


class MacOSBackendTest(unittest.TestCase):
    def test_maps_system_profiler_payload(self):
        payload = {
            "SPHardwareDataType": [{
                "machine_model": "MacBookPro",
                "machine_name": "MacBook Pro",
                "chip_type": "Apple M4",
                "number_processors": "10",
                "physical_memory": "32 GB",
                "serial_number": "SECRET",
            }],
            "SPDisplaysDataType": [{
                "sppci_model": "Apple M4",
                "spdisplays_vendor": "Apple",
            }],
            "SPMemoryDataType": [{
                "_items": [{
                    "dimm_size": "16 GB",
                    "dimm_manufacturer": "Example Memory",
                    "dimm_speed": "6400 MT/s",
                    "dimm_part_number": "PART",
                    "dimm_serial_number": "MEMSECRET",
                }]
            }],
        }
        result = _macos._from_profiler(
            payload,
            detail="basic",
            include_sensitive=False,
            sections=_macos.SECTIONS,
        )
        self.assertEqual(result.system.model, "MacBookPro")
        self.assertEqual(result.cpu.name, "Apple M4")
        self.assertEqual(result.gpus[0].manufacturer, "Apple")
        self.assertEqual(result.memory[0].capacity_bytes, 16 * 1024 ** 3)
        self.assertEqual(result.memory[0].manufacturer, "Example Memory")
        self.assertIsNone(result.memory[0].part_number)
        self.assertIsNone(result.memory[0].serial_number)
        self.assertIsNone(result.system.serial_number)

        full = _macos._from_profiler(
            payload,
            detail="full",
            include_sensitive=True,
            sections=_macos.SECTIONS,
        )
        self.assertEqual(full.memory[0].part_number, "PART")
        self.assertEqual(full.memory[0].serial_number, "MEMSECRET")


if __name__ == "__main__":
    unittest.main()
