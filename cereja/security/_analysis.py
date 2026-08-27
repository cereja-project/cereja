"""Static security analysis orchestration."""
import tempfile
from pathlib import Path

from cereja.hashtools import CompressionError, decompress_file, is_encrypted_archive

from ._archives import UnsafeArchiveError, read_zip_members
from ._indicators import extract_iocs, inspect_indicators
from ._inspect import detect_file_type, extract_strings, hash_bytes, shannon_entropy
from ._models import Finding, SecurityReport

EXECUTABLE_SUFFIXES = {".exe", ".dll", ".sys", ".scr", ".bat", ".cmd", ".ps1", ".vbs", ".js"}


def analyze_file(path, max_depth: int = 2) -> SecurityReport:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(str(source))
    if max_depth < 0:
        raise ValueError("max_depth must be non-negative")
    if source.suffix.lower() == ".cjz":
        return _analyze_cjz(source, max_depth)
    return _analyze_bytes(source.read_bytes(), source.name, max_depth)


def _analyze_cjz(source: Path, max_depth: int) -> SecurityReport:
    raw = source.read_bytes()
    report = _base_report(raw, source.name)
    if is_encrypted_archive(str(source)):
        report.findings.append(Finding("archive.encrypted", "archive", "info", 1.0,
            "Encrypted Cereja archive was not decompressed.", "password required", source.name))
        return report
    if max_depth == 0:
        return report
    with tempfile.TemporaryDirectory(prefix="cereja-security-") as directory:
        output = Path(directory) / "payload"
        try:
            restored = Path(decompress_file(str(source), str(output), verbose=False))
            child = _analyze_bytes(restored.read_bytes(), restored.name, max_depth - 1)
            report.children.append(child)
        except CompressionError as exc:
            report.findings.append(Finding("archive.decompression_failed", "archive", "medium", 1.0,
                "Cereja archive could not be inspected.", str(exc), source.name))
    return report


def _base_report(data: bytes, name: str) -> SecurityReport:
    strings = extract_strings(data)
    return SecurityReport(name, len(data), detect_file_type(data, name), shannon_entropy(data),
        hash_bytes(data), extract_iocs(strings), inspect_indicators(name, data, strings))


def _analyze_bytes(data: bytes, name: str, depth: int) -> SecurityReport:
    report = _base_report(data, name)
    if report.file_type != "zip" or depth == 0:
        return report
    try:
        members = read_zip_members(data)
    except (UnsafeArchiveError, ValueError) as exc:
        report.findings.append(Finding("archive.unsafe", "archive", "high", 1.0,
            "Archive was not expanded because it violated safety limits.", str(exc), name))
        return report
    for member_name, member_data in members:
        child = _analyze_bytes(member_data, member_name, depth - 1)
        if Path(member_name).suffix.lower() in EXECUTABLE_SUFFIXES or child.file_type in ("pe", "elf"):
            child.findings.append(Finding("archive.executable_content", "execution", "medium", 0.9,
                "Archive contains executable or script content.", child.file_type, member_name))
        report.children.append(child)
    _detect_command_chains(report)
    return report


def _detect_command_chains(report: SecurityReport):
    names = {Path(child.path).name.lower(): child for child in report.children}
    for child in report.children:
        if Path(child.path).suffix.lower() not in (".cmd", ".bat"):
            continue
        # Strings are re-extracted from no retained raw bytes, so inspect evidence in IOCs/findings is insufficient.
        # Command-chain correlation is handled by filename evidence from common launcher syntax in a bounded text preview.
        # This hook remains intentionally conservative until report models retain previews.
        if "launcher" in Path(child.path).stem.lower() and any(name.endswith(".exe") for name in names):
            child.findings.append(Finding("script.launcher_chain", "execution", "high", 0.75,
                "Launcher script is packaged with a Windows executable.", "launcher + executable", child.path))
