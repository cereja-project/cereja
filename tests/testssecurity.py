import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from cereja.security import analyze_file
from cereja.security._archives import UnsafeArchiveError, read_zip_members
from cereja.security._indicators import extract_iocs, inspect_indicators
from cereja.security._inspect import detect_file_type, extract_strings, hash_bytes, shannon_entropy


class SecurityInspectionTest(unittest.TestCase):
    def test_hashes_include_git_blob_identity(self):
        data = b"hello"
        hashes = hash_bytes(data)
        expected = hashlib.sha1(b"blob 5\0hello").hexdigest()
        self.assertEqual(hashes.git_blob_sha1, expected)
        self.assertEqual(hashes.sha256, hashlib.sha256(data).hexdigest())

    def test_detects_common_signatures(self):
        self.assertEqual(detect_file_type(b"MZ" + b"\0" * 20, "x.bin"), "pe")
        self.assertEqual(detect_file_type(b"PK\x03\x04" + b"\0" * 20, "x.bin"), "zip")
        self.assertEqual(detect_file_type(b"plain text", "x.bin"), "text")

    def test_entropy_is_bounded(self):
        self.assertEqual(shannon_entropy(b"A" * 100), 0.0)
        self.assertLessEqual(shannon_entropy(bytes(range(256))), 8.0)

    def test_extracts_strings_and_iocs(self):
        strings = extract_strings(b"xx https://example.com/a 192.168.1.2 yy")
        iocs = extract_iocs(strings)
        self.assertIn("https://example.com/a", iocs["urls"])
        self.assertIn("192.168.1.2", iocs["ips"])

    def test_reports_explainable_command_and_credential_indicators(self):
        data = b"powershell -c test Login Data Local State"
        findings = inspect_indicators("sample.txt", data, extract_strings(data))
        ids = {item.id for item in findings}
        self.assertIn("command.execution", ids)
        self.assertIn("credential.access", ids)

    def test_rejects_zip_traversal(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("../escape.txt", "safe fixture")
        with self.assertRaises(UnsafeArchiveError):
            read_zip_members(buffer.getvalue())

    def test_analyzes_zip_recursively_without_execution(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("1Launcher.cmd", "start vendor.exe protocol.txt")
            archive.writestr("vendor.exe", b"MZ" + b"\0" * 100)
            archive.writestr("protocol.txt", "return(function() end)()")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.zip"
            path.write_bytes(buffer.getvalue())
            report = analyze_file(path)
        self.assertEqual(report.file_type, "zip")
        self.assertEqual({child.path for child in report.children}, {"1Launcher.cmd", "vendor.exe", "protocol.txt"})
        vendor = next(child for child in report.children if child.path == "vendor.exe")
        self.assertEqual(vendor.file_type, "pe")
        self.assertIn("archive.executable_content", {item.id for item in vendor.findings})
        self.assertNotIn("is_malware", report.to_dict())


if __name__ == "__main__":
    unittest.main()
