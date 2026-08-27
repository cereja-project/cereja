"""Static security analysis orchestration."""
import re
import tempfile
from pathlib import Path, PurePosixPath

from cereja.hashtools import CompressionError, decompress_file, is_encrypted_archive

from ._archives import UnsafeArchiveError, read_zip_members
from ._indicators import extract_iocs, inspect_indicators
from ._inspect import detect_file_type, extract_strings, hash_bytes, shannon_entropy
from ._models import Finding, SecurityReport
from ._pe import PEFormatError, inspect_pe

EXECUTABLE_SUFFIXES = {".exe", ".dll", ".sys", ".scr", ".bat", ".cmd", ".ps1", ".vbs", ".js"}
LAUNCHABLE_SUFFIXES = {".exe", ".com", ".scr", ".bat", ".cmd", ".ps1"}


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
    report.file_type = "cjz"
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
    file_type = detect_file_type(data, name)
    report = SecurityReport(
        name,
        len(data),
        file_type,
        shannon_entropy(data),
        hash_bytes(data),
        extract_iocs(strings),
        inspect_indicators(name, data, strings),
    )
    if file_type == "pe":
        try:
            report.metadata["pe"] = inspect_pe(data)
        except PEFormatError as exc:
            report.metadata["pe_error"] = str(exc)
    return report


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
    _detect_command_chains(report, members)
    return report


def _detect_command_chains(report: SecurityReport, members):
    children = {PurePosixPath(child.path).name.lower(): child for child in report.children}
    packaged_names = set(children)
    for member_name, data in members:
        source_name = PurePosixPath(member_name).name.lower()
        if Path(member_name).suffix.lower() not in (".cmd", ".bat"):
            continue

        text = data.decode("utf-8", "replace")[:16384]
        lowered = text.lower()
        referenced = [
            name for name in packaged_names
            if name != source_name and re.search(r"(?<![\w.-])" + re.escape(name) + r"(?![\w.-])", lowered)
        ]
        executables = [name for name in referenced if Path(name).suffix.lower() in LAUNCHABLE_SUFFIXES]
        if not executables:
            continue

        evidence_lines = [
            line.strip() for line in text.splitlines()
            if any(executable in line.lower() for executable in executables)
        ]
        evidence = "; ".join(evidence_lines)[:500] or ", ".join(sorted(referenced))
        children[source_name].findings.append(Finding(
            "script.launcher_chain", "execution", "high", 0.95,
            "Launcher script explicitly references packaged executable content.", evidence, member_name))
