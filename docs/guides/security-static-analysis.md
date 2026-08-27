# Static Security Analysis

`cereja.security` provides defensive static inspection of untrusted files. It collects evidence and assigns an explainable risk score; it does not execute inspected content and does not claim that a file is malware.

## CLI

```bash
cereja security analyze sample.zip
cereja security analyze sample.zip --format json
cereja security analyze sample.zip --format markdown -o report.md
cereja security analyze sample.zip --max-depth 3
```

The default output format is Markdown. JSON is intended for automation and downstream tooling.

## Python API

```python
from cereja.security import analyze_file, report_to_json, report_to_markdown

report = analyze_file("sample.zip", max_depth=2)
print(report.risk_level, report.risk_score)
print(report.to_dict())
print(report_to_markdown(report))
```

The report includes MD5, SHA-1, SHA-256, Git blob SHA-1, detected file type, Shannon entropy, IOCs, findings, and recursively analyzed children.

## Supported MVP inputs

Regular files and ZIP archives are inspected directly. Cereja `.cjz` file archives are decompressed through the existing Cereja compression API into a temporary directory and inspected recursively. Encrypted `.cjz` archives remain opaque; the security analyzer never prompts for a password.

ZIP processing rejects traversal paths and enforces limits on member count, individual expanded member size, total expanded size, and recursion depth.

The generic `cereja decompress` command is not extended to ZIP in this MVP. ZIP support belongs to the security analyzer because it needs bounded in-memory inspection rather than general-purpose extraction.

## Findings

Findings contain a stable ID, category, severity, confidence, description, evidence, and source. Current heuristics cover:

- executable or script content in archives;
- explicit launcher chains where a packaged `.cmd` or `.bat` references a packaged executable;
- extension/signature mismatches;
- command execution strings;
- Windows persistence strings;
- credential-related strings;
- network download strings;
- numeric-escape and flattened-script obfuscation;
- LuaJIT runtime identification in Windows PE content.

Risk levels are `info`, `low`, `medium`, `high`, and `critical`. Treat the score as triage information, not an antivirus verdict. Structural findings are deliberately weighted below direct credential/persistence indicators to reduce false positives.

## Safety model

The analyzer does not execute files, import inspected Python modules, evaluate scripts, or invoke inspected commands through a shell. The implementation has no mandatory third-party dependency.

Real malicious or suspicious samples should not be committed to the Cereja repository. Use synthetic fixtures for automated tests and keep acceptance samples external.
