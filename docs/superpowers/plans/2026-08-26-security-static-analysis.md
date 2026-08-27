# Static Security Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a zero-dependency defensive static file analyzer exposed through `cereja.security` and `cereja security analyze`.

**Architecture:** Focused security modules provide immutable report models, bounded byte/file inspection, IOC and heuristic detection, safe recursive archive traversal, and orchestration. The existing CLI delegates to the public security API and serializes reports without executing inspected content.

**Tech Stack:** Python standard library, unittest, existing Cereja compression APIs and CLI.

**Spec:** `docs/superpowers/specs/2026-08-26-security-static-analysis-design.md`

## Global Constraints

- Standard library only; no mandatory third-party dependency.
- Never execute, import, eval, or shell out to analyzed content.
- Real suspicious samples must not be committed.
- Archive processing must enforce traversal and expansion limits.
- Public API reports risk/evidence and never exposes `is_malware`.

---

### Task 1: Core report models and primitive inspection

**Files:**
- Create: `cereja/security/__init__.py`
- Create: `cereja/security/_models.py`
- Create: `cereja/security/_inspect.py`
- Create: `tests/testssecurity.py`

**Interfaces:**
- Produces: `FileHashes`, `Finding`, `SecurityReport`, `hash_bytes(data)`, `detect_file_type(data, name)`, `shannon_entropy(data)`, `extract_strings(data)`.

- [ ] Write tests asserting known hashes including Git blob SHA-1, PE/ZIP/text signature detection, bounded printable-string extraction, entropy bounds, and report serialization.
- [ ] Run `python -m unittest tests.testssecurity -v` and verify failure because `cereja.security` does not exist.
- [ ] Implement the minimal models and primitive inspectors.
- [ ] Re-run the focused tests and verify pass.
- [ ] Commit the task.

### Task 2: IOC and explainable heuristic findings

**Files:**
- Create: `cereja/security/_indicators.py`
- Modify: `cereja/security/_models.py`
- Modify: `tests/testssecurity.py`

**Interfaces:**
- Consumes: extracted strings and `Finding`.
- Produces: `extract_iocs(strings)` and `inspect_indicators(name, data, strings)`.

- [ ] Add failing synthetic tests for URLs/domains/IPs and for command execution, persistence, credential-access, PowerShell, and high-obfuscation indicators.
- [ ] Run focused tests and verify expected failures.
- [ ] Implement bounded regex IOC extraction and stable heuristic finding IDs.
- [ ] Re-run focused tests and verify pass.
- [ ] Commit the task.

### Task 3: Safe recursive archive analysis and public API

**Files:**
- Create: `cereja/security/_archives.py`
- Create: `cereja/security/_analysis.py`
- Modify: `cereja/security/__init__.py`
- Modify: `tests/testssecurity.py`

**Interfaces:**
- Consumes: primitive inspectors, indicators, report models, existing Cereja decompression API.
- Produces: `analyze_file(path, max_depth=2) -> SecurityReport` and recursive ZIP/CJZ child reports.

- [ ] Add failing tests creating harmless ZIPs in memory, nested archives, traversal members, oversized-member metadata, executable-in-archive findings, and a synthetic `.cjz` generated with Cereja compression.
- [ ] Run focused tests and verify expected failures.
- [ ] Implement safe ZIP traversal with member/depth/expanded-size limits and `.cjz` temporary decompression using Cereja APIs.
- [ ] Re-run focused tests and verify pass.
- [ ] Commit the task.

### Task 4: CLI and reports

**Files:**
- Modify: `cereja/cli.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/testssecurity.py`

**Interfaces:**
- Consumes: `analyze_file()` and `SecurityReport.to_dict()`.
- Produces: `cereja security analyze PATH [--format text|json] [--output PATH] [--max-depth N]`.

- [ ] Add failing CLI tests for help, JSON output, text output, report file output, and invalid paths.
- [ ] Run focused CLI/security tests and verify expected failures.
- [ ] Add the `security` parser/handler and deterministic text/JSON rendering.
- [ ] Re-run focused tests and verify pass.
- [ ] Commit the task.

### Task 5: Acceptance validation and documentation

**Files:**
- Create: `docs/guides/security-static-analysis.md`
- Modify: `README.md` only if the existing README has an appropriate CLI/features section.

**Interfaces:**
- Consumes: completed public API and CLI.

- [ ] Run the complete project test suite available in the isolated environment.
- [ ] Run the analyzer against the external LTX2 `.cjz` sample without executing its contents and record only non-sensitive aggregate results locally.
- [ ] Verify the recovered ZIP Git blob SHA-1 equals `8739a37869cdf11a5edcc166028dd66968777e85` and that child inventory includes `1Launcher.cmd`, `protocol.txt`, and `vendor.exe`.
- [ ] Document API, CLI, safety model, limitations, and interpretation of risk scores.
- [ ] Re-run focused tests after documentation changes.
- [ ] Commit the task.