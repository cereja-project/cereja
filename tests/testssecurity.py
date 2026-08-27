import hashlib
import io
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from cereja.security import analyze_file, report_to_json, report_to_markdown
from cereja.security._archives import UnsafeArchiveError, read_zip_members
from cereja.security._indicators import extract_iocs, inspect_indicators
from cereja.security._inspect import detect_file_type, extract_strings, hash_bytes, shannon_entropy
from cereja.security._pe import inspect_pe


def synthetic_pe():
    data = bytearray(0x400)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    coff = 0x84
    struct.pack_into("<HHIIIHH", data, coff, 0x8664, 1, 0, 0, 0, 0xF0, 0x0022)
    optional = coff + 20
    struct.pack_into("<H", data, optional, 0x20B)
    struct.pack_into("<I", data, optional + 16, 0x1000)
    struct.pack_into("<Q", data, optional + 24, 0x140000000)
    struct.pack_into("<H", data, optional + 68, 2)
    struct.pack_into("<I", data, optional + 108, 16)
    struct.pack_into("<II", data, optional + 112 + 8, 0x1000, 40)
    section = optional + 0xF0
    data[section:section + 8] = b".rdata\0\0"
    struct.pack_into("<IIII", data, section + 8, 0x200, 0x1000, 0x200, 0x200)
    struct.pack_into("<IIIII", data, 0x200, 0x1060, 0, 0, 0x1040, 0x1060)
    data[0x240:0x240 + 13] = b"KERNEL32.dll\0"
    struct.pack_into("<QQ", data, 0x260, 0x1080, 0)
    struct.pack_into("<H", data, 0x280, 0)
    data[0x282:0x282 + 15] = b"CreateProcessW\0"
    return bytes(data)


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

    def test_inspects_pe_metadata_and_imphash_without_dependency(self):
        metadata = inspect_pe(synthetic_pe())
        self.assertEqual(metadata["pe_type"], "pe32+")
        self.assertEqual(metadata["machine"], "0x8664")
        self.assertEqual(metadata["import_count"], 1)
        self.assertEqual(metadata["import_dlls"], ["KERNEL32.dll"])
        self.assertEqual(metadata["imphash"], "6a52275a13182d459745b3b784d6ed0c")
        self.assertFalse(metadata["signed"])

    def test_detects_flattened_numeric_escape_obfuscation(self):
        data = b"return(function(...)" + (b"\\123" * 9000)
        findings = inspect_indicators("protocol.txt", data, extract_strings(data))
        ids = {item.id for item in findings}
        self.assertIn("script.obfuscation.numeric_escapes", ids)
        self.assertIn("script.obfuscation.flattened", ids)

    def test_detects_prometheus_vm_structure(self):
        environment = b"getfenv _ENV unpack newproxy setmetatable getmetatable select "
        dispatcher = b"".join(b"if T<123 then " for _ in range(40))
        data = b"return(function(...)" + environment + dispatcher + (b"\\123" * 9000)
        findings = inspect_indicators("protocol.txt", data, extract_strings(data))
        finding = next(item for item in findings if item.id == "obfuscator.prometheus_vm")
        self.assertIn("dispatcher_comparisons=40", finding.evidence)

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

    def test_report_renderers_include_risk_hashes_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.exe"
            path.write_bytes(synthetic_pe())
            report = analyze_file(path)
        json_report = report_to_json(report)
        markdown_report = report_to_markdown(report)
        self.assertIn('"risk_level"', json_report)
        self.assertIn('"imphash"', json_report)
        self.assertIn(report.hashes.sha256, markdown_report)
        self.assertIn("pe.imphash", markdown_report)


if __name__ == "__main__":
    unittest.main()
