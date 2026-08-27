# Cereja Static Security Analysis Design

## Goal

Add a defensive, zero-dependency static-analysis toolkit under `cereja.security` for inspecting untrusted files without executing them. The toolkit reports evidence and risk indicators; it does not make a deterministic malware verdict.

## Scope

The MVP analyzes regular files, Cereja `.cjz` compressed files, and ZIP archives recursively. It calculates MD5, SHA-1, SHA-256 and Git blob SHA-1; identifies common file types by signatures; calculates Shannon entropy; extracts printable strings and basic IOCs; identifies suspicious script/command indicators; safely inventories archive members; and produces structured findings with risk score/level.

The CLI entry point is `cereja security analyze <path>`, with `--format json|text`, `--max-depth`, and optional report output. Analysis is read-only except for bounded temporary extraction managed internally. No analyzed content is executed, imported, loaded as a library, or invoked through a shell.

## Architecture

`cereja.security` exposes `analyze_file(path, max_depth=2) -> SecurityReport`. Focused internal modules own models, low-level inspection, IOC extraction, archive handling, and orchestration. Archive traversal operates on bytes where practical and enforces depth, member-count, member-size, total-expanded-size, and path-safety limits.

`.cjz` support reuses Cereja compression semantics rather than duplicating a second archive format implementation. The analyzer decompresses into an isolated temporary path and recursively analyzes the restored bytes/file; encrypted archives are reported as opaque rather than prompting for credentials.

## Findings and risk

A `Finding` has a stable ID, category, severity, confidence, description, evidence, and source path. Findings describe observations such as executable content in an archive, command-launch chains, high script obfuscation indicators, suspicious network/credential/persistence strings, or extension/signature mismatch.

`SecurityReport` contains identity, hashes, file type, entropy, IOCs, findings, child reports, risk score, and risk level. Scores are bounded to 0-100 and derived from findings. Risk levels are `info`, `low`, `medium`, `high`, and `critical`. The API intentionally has no `is_malware` field.

## Safety constraints

- Never execute, import, dynamically evaluate, or shell out to analyzed content.
- Standard library only for the MVP.
- Prevent ZIP path traversal and reject/bound decompression bombs.
- Recursive analysis defaults to depth 2 and is configurable.
- Binary/string inspection is bounded to avoid unbounded memory use.
- The real suspicious LTX2 sample remains external to the repository and is used only as an acceptance sample.
- Unit tests use synthetic, non-malicious fixtures.

## Acceptance criteria

For the external `LT_Easy_LD_Prompt_Cronartium.zip.cjz` sample, the MVP should recover or inspect the nested archive, reproduce its cryptographic hashes, inventory `1Launcher.cmd`, `protocol.txt`, and `vendor.exe`, identify the CMD execution relationship, identify `vendor.exe` as Windows PE content, flag the heavily obfuscated script as suspicious, and produce explainable findings without running any sample content.

The implementation must not introduce mandatory third-party dependencies.