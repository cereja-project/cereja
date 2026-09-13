import unittest

from cereja.system.hardware import HardwareInfo, info


class SystemInfoSmokeTest(unittest.TestCase):
    def test_native_backend_collects_core_sections_without_crashing(self):
        result = info(sections=["system", "os", "cpu"])
        self.assertIsInstance(result, HardwareInfo)
        self.assertIsNotNone(result.system)
        self.assertIsNotNone(result.os)
        self.assertIsNotNone(result.cpu)
        self.assertIsNone(result.motherboard)
        self.assertEqual(result.memory, ())
        self.assertEqual(result.gpus, ())


if __name__ == "__main__":
    unittest.main()
