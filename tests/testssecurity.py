import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from cereja.security import analyze_file, report_to_json, report_to_markdown
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

    def test_detects_luajit_runtime_identifier_from_pe_bytes(self):
        data = b"MZ" + b"\0" * 64 + b"LuaJIT 2.1.0-beta3\0luajit.exe"
        findings = inspect_indicators("vendor.exe", data, extract_strings(data))
        self.assertIn("runtime.luajit", {item.id for item in findings})

    def test_detects_flattened_numeric_escape_obfuscation(self):
        data = b"return(function(...)" + (b"\\123" * 9000)
        findings = inspect_indicators("protocol.txt", data, extract_strings(data))
        ids = {item.id for item in findings}
        self.assertIn("script.obfuscation.numeric_escapes", ids)
        self.assertIn("script.obfuscation.flattened", ids)

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
            archive.writestr("vendor.exe", b"MZ" + b"\0" * 100 + b"LuaJIT")
            archive.writestr("protocol.txt", "return(function() end)()")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.zip"
            path.write_bytes(buffer.getvalue())
            report = analyze_file(path)
        self.assertEqual(report.file_type, "zip")
        self.assertEqual({child.path for child in report.children}, {"1Launcher.cmd", "vendor.exe", "protocol.txt"})
        vendor = next(child for child in report.children if child.path == "vendor.exe")
        launcher = next(child for child in report.children if child.path == "1Launcher.cmd")
        self.assertEqual(vendor.file_type, "pe")
        self.assertIn("archive.executable_content", {item.id for item in vendor.findings})
        launcher_finding = next(item for item in launcher.findings if item.id == "script.launcher_chain")
        self.assertEqual(launcher_finding.evidence, "start vendor.exe protocol.txt")
        self.assertNotIn("is_malware", report.to_dict())

    def test_launcher_name_alone_does_not_create_chain_finding(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("Launcher.cmd", "echo harmless")
            archive.writestr("tool.exe", b"MZ" + b"\0" * 32)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.zip"
            path.write_bytes(buffer.getvalue())
            report = analyze_file(path)
        launcher = next(child for child in report.children if child.path == "Launcher.cmd")
        self.assertNotIn("script.launcher_chain", {item.id for item in launcher.findings})

    def test_report_renderers_include_risk_and_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.txt"
            path.write_text("powershell -c whoami", encoding="utf-8")
            report = analyze_file(path)
        json_report = report_to_json(report)
        markdown_report = report_to_markdown(report)
        self.assertIn('"risk_level"', json_report)
        self.assertIn(report.hashes.sha256, markdown_report)
        self.assertIn("command.execution", markdown_report)


if __name__ == "__main__":
    unittest.main()
