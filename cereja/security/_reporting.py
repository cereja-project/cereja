"""Report renderers for defensive static security analysis."""
import json


def report_to_json(report, indent: int = 2) -> str:
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=indent)


def report_to_markdown(report) -> str:
    lines = [
        f"# Cereja Security Analysis: {report.path}",
        "",
        f"- Risk: **{report.risk_level.upper()}** ({report.risk_score}/100)",
        f"- Type: `{report.file_type}`",
        f"- Size: {report.size} bytes",
        f"- SHA-256: `{report.hashes.sha256}`",
        f"- Git blob SHA-1: `{report.hashes.git_blob_sha1}`",
        "",
        "## Findings",
        "",
    ]
    findings = report.all_findings()
    if not findings:
        lines.append("No static findings.")
    for finding in findings:
        lines.extend([
            f"### [{finding.severity.upper()}] {finding.id}",
            f"- Source: `{finding.source}`",
            f"- Confidence: {finding.confidence:.2f}",
            f"- Evidence: `{finding.evidence}`",
            "",
            finding.description,
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"
