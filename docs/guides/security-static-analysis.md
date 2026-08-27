# Static Security Analysis

`cereja.security` provides defensive static inspection of untrusted files. It collects evidence and assigns an explainable risk score; it does not execute inspected content and does not claim that a file is malware.

## Python API

```python
from cereja.security import analyze_file

report = analyze_file("sample.zip", max_depth=2)
print(report.risk_level, report.risk_score)
print(report.to_dict())
```

The report includes MD5, SHA-1, SHA-256, Git blob SHA-1, detected file type, Shannon entropy, IOCs, findings, and recursively analyzed children.

## Supported MVP inputs

Regular files and ZIP archives are inspected directly. Cereja `.cjz` file archives are decompressed through the existing Cereja compression API into a temporary directory and inspected recursively. Encrypted `.cjz` archives remain opaque; the security analyzer never prompts for a password.

ZIP processing rejects traversal paths and enforces limits on member count, individual expanded member size, total expanded size, and recursion depth.

## Findings

Findings contain a stable ID, category, severity, confidence, description, evidence, and source. Current heuristics cover executable content in archives, extension/signature mismatches, command execution strings, Windows persistence strings, credential-related strings, network download strings, and numeric-escape script obfuscation.

Risk levels are `info`, `low`, `medium`, `high`, and `critical`. Treat the score as triage information, not an antivirus verdict. Confirm high-impact findings through independent review or a purpose-built sandbox before making attribution claims.

## Safety model

The analyzer does not execute files, import inspected Python modules, evaluate scripts, or invoke inspected commands through a shell. The implementation has no mandatory third-party dependency.

Real malicious or suspicious samples should not be committed to the Cereja repository. Use synthetic fixtures for automated tests and keep acceptance samples external.