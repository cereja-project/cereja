# System Info Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add zero-dependency cross-platform system inventory through a typed Python API and `cereja system info` CLI with visual, JSON, detail-level, section, and sensitive-data controls.

**Architecture:** Add a focused `cereja.system.hardware` package with immutable data models, a collector facade, per-platform backends, and rendering helpers. The CLI dispatch remains lazy in `cereja.entrypoint`; collectors are best-effort per section and never probe at import time.

**Tech Stack:** Python 3.11+ standard library only; Windows CIM/PowerShell via `subprocess`, Linux `/proc` + `/sys` + standard OS commands, macOS `system_profiler`/`sysctl`; unittest; existing Cereja lazy-export system.

**Spec:** `docs/superpowers/specs/2026-09-13-system-info-design.md`

## Global Constraints
- Zero third-party runtime dependencies.
- No hardware or subprocess probing during import.
- `basic` is safe to share by default; unique identifiers require explicit `include_sensitive=True` / `--sensitive`.
- Missing platform data is represented as `None` or empty collections instead of failing the entire inventory.
- `--json` and Python serialization use the same typed model schema.
- First version sections: system, os, cpu, memory, gpu, motherboard, bios.
- Existing frozen/lazy public API checks must remain green.

---

### Task 1: Public models and collector contract
**Files:** create `tests/system_info/test_models.py`, `cereja/system/hardware/__init__.py`, `models.py`, `collector.py`; modify `cereja/_exports.py`, `cereja/system/__init__.pyi`.
**Produces:** `SystemInfo`, `OperatingSystemInfo`, `CPUInfo`, `MemoryInfo`, `GPUInfo`, `MotherboardInfo`, `BIOSInfo`, `HardwareInfo`; `hardware.info(*, detail="basic", include_sensitive=False, sections=None)`; `HardwareInfo.to_dict()` / `.to_json()`.
- [ ] Write tests first for immutable typed models, sensitive-value behavior, serialization and argument validation.
- [ ] Commit tests and verify CI RED because `cereja.system.hardware` does not exist.
- [ ] Implement models and collector dispatch with no probing at import time.
- [ ] Register intended public exports only.
- [ ] Verify focused tests and import contracts GREEN.

### Task 2: Platform backends
**Files:** create `tests/system_info/test_backends.py`, `_common.py`, `_windows.py`, `_linux.py`, `_macos.py`.
**Produces:** each backend `collect(*, detail, include_sensitive, sections) -> HardwareInfo`.
- [ ] Add backend contract tests using injected command/file readers.
- [ ] Windows: collect ComputerSystem, OperatingSystem, Processor, PhysicalMemory, VideoController, BaseBoard and BIOS through JSON-producing PowerShell/CIM; serials only when sensitive.
- [ ] Linux: use `/etc/os-release`, `platform`, `/proc/cpuinfo`, `/proc/meminfo`, `/sys/class/dmi/id`, `/sys/class/drm` plus best-effort standard commands when useful.
- [ ] macOS: use `platform`, `sysctl`, and `system_profiler` structured output where available.
- [ ] Per-section failures degrade to missing values.
- [ ] Verify Linux/Windows/macOS CI.

### Task 3: CLI and rendering
**Files:** create `tests/test_system_info_cli.py`, `cereja/commands/system.py`, `cereja/system/hardware/formatting.py`; modify `cereja/entrypoint.py`.
**CLI:** `cereja system info`; flags `--full`, `--sensitive`, `--json`, repeatable `--section {system,os,cpu,memory,gpu,motherboard,bios}`.
- [ ] Write CLI tests first for dispatch, visual layout, JSON, sections and flags.
- [ ] Implement lazy `system` dispatch.
- [ ] Render aligned human-readable sections using stdlib only.
- [ ] JSON emits no decoration; visual defaults exclude sensitive identifiers.
- [ ] Verify CLI tests GREEN.

### Task 4: Documentation and final validation
**Files:** create `docs/guides/system-info.md`; modify `docs/index.md`.
- [ ] Document Python API and CLI basic/full/sensitive/json/section usage.
- [ ] Document platform variability, privacy, and best-effort semantics.
- [ ] Run full configured CI/distribution/API tooling.
- [ ] Remove temporary `docs/superpowers/specs/...` and `docs/superpowers/plans/...` from final PR content before merge.
- [ ] Open/update draft PR with exact validation evidence; no release/version bump.
