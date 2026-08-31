"""Report renderers for defensive static security analysis."""
import json


def report_to_json(report, indent: int = 2) -> str:
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=indent)


def _walk_reports(report):
    yield report
    for child in report.children:
        yield from _walk_reports(child)


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
    ]

    metadata_reports = [item for item in _walk_reports(report) if item.metadata]
    if metadata_reports:
        lines.extend(["## Metadata", ""])
        for item in metadata_reports:
            lines.append(f"### `{item.path}`")
            for namespace, values in item.metadata.items():
                if isinstance(values, dict):
                    for key, value in values.items():
                        lines.append(f"- {namespace}.{key}: `{value}`")
                else:
                    lines.append(f"- {namespace}: `{values}`")
            lines.append("")

    lines.extend(["## Findings", ""])
    findings = report.all_findings()
    if not findings:
        lines.append("No static findings.")
    for finding in findings:
        lines.extend([
            f"### [{finding.severity.upper()}] {finding.id}",
            f"- Source: `{finding.source.replace('`', '\\`')}`",
            f"- Confidence: {finding.confidence:.2f}",
            f"- Evidence: `{finding.evidence.replace('`', '\\`')}`",
            "",
            finding.description,
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"
