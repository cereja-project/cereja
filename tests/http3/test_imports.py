import subprocess
import sys
import unittest


class HTTPImportTest(unittest.TestCase):
    def test_import_does_not_start_thread_or_event_loop(self):
        code = r'''
import asyncio
import sys
import threading
before = {id(t) for t in threading.enumerate()}
import cereja.http
assert {id(t) for t in threading.enumerate()} == before
try:
    asyncio.get_running_loop()
except RuntimeError:
    pass
else:
    raise AssertionError("import created a running event loop")
assert "cereja.display" not in sys.modules
assert "cereja.file" not in sys.modules
'''
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
