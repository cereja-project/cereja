# Cross-Platform System Info Design

## Goal
Add a zero-runtime-dependency system inventory API and CLI to Cereja that reports useful hardware and operating-system information on Windows, Linux, and macOS, with explicit detail and sensitivity controls.

## User-facing API
```python
from cereja.system import hardware

info = hardware.info()
info = hardware.info(detail="full")
info = hardware.info(detail="full", include_sensitive=True)
```

`hardware.info()` returns a typed `SystemInfo` aggregate rather than a raw dictionary. The model exposes `to_dict()` and `to_json()` for structured serialization.

Detail levels:
- `basic`: concise, generally safe diagnostic information.
- `full`: more technical fields useful for troubleshooting and reproducibility.

Sensitive information is independent from detail level and is excluded unless `include_sensitive=True`.
Unknown or unavailable fields are represented as `None` rather than guessed or treated as fatal errors.

## CLI
Primary command:
```bash
cereja system info
```

Supported forms:
```bash
cereja system info
cereja system info --full
cereja system info --sensitive
cereja system info --full --sensitive
cereja system info --json
cereja system info --full --json
cereja system info --section os
cereja system info --section cpu
cereja system info --section memory
cereja system info --section gpu
```

Default output is a human-readable terminal layout grouped by section. `--json` emits machine-readable JSON only. `--section` limits collection/output to one section where practical.

## Information model
```text
SystemInfo
├── system
├── os
├── cpu
├── memory[]
├── gpus[]
├── motherboard
└── bios
```

### System
Basic: manufacturer, model, architecture, total_memory_bytes.
Full may include machine/form-factor and virtualization/container hints where reliable.
Sensitive: machine/system serial number, hardware UUID or equivalent unique identifier.

### Operating system
Basic: name, edition, version, build, architecture, kernel.
Full may include kernel_version, install_date, boot_time, timezone, locale, platform identifier, Python architecture, hostname.
Hostname is excluded from basic output because it can identify a person, company, or asset.

### CPU
Basic: name, manufacturer, physical_cores, logical_processors.
Full may include max_clock_mhz, architecture, processor family/identifier when non-sensitive.

### Memory
Basic per module: capacity_bytes, manufacturer, speed_mts.
Full: configured_speed_mts, part_number, bank_label, device_locator, form_factor, memory_type.
Sensitive: module serial number when exposed.

### GPU
Basic: name, vendor/manufacturer.
Full: adapter_memory_bytes, driver_version, processor/device description.
No dependency on vendor SDKs such as NVML.

### Motherboard
Basic: manufacturer, product/model, version.
Sensitive: serial_number.

### BIOS / firmware
Basic: manufacturer, version, release_date.
Sensitive: serial_number where exposed.

## Architecture
```text
cereja/system/hardware/
├── __init__.py
├── models.py
├── collector.py
├── formatting.py
├── _windows.py
├── _linux.py
└── _macos.py
```

- `models.py`: immutable/slotted dataclasses and deterministic serialization.
- `collector.py`: validates detail/section arguments, selects the backend, and assembles the aggregate.
- platform modules: native collection only.
- `formatting.py`: terminal rendering only.

No hardware probing occurs at import time.

## Platform backends
### Windows
Use stdlib plus built-in Windows facilities:
1. `platform`, `os`, `winreg` where reliable.
2. PowerShell `Get-CimInstance` via `subprocess` for richer inventory.
3. `ctypes`/Win32 only where materially useful.

PowerShell commands use fixed templates controlled by Cereja, never interpolated executable source from user input. Prefer one/few subprocesses returning JSON rather than scraping formatted text.

### Linux
Prefer `/proc`, `/sys`, `os.uname()` and `platform`, including `/proc/cpuinfo`, `/proc/meminfo`, `/sys/class/dmi/id/*`, and `/sys/class/drm/*` where useful. Missing permissions/files produce partial results rather than total failure.

### macOS
Use stdlib plus built-in `sysctl` and `system_profiler` through fixed `subprocess` argument lists. Prefer JSON/XML/plist structured output where available.

## Security and privacy
- Sensitive identifiers are opt-in.
- JSON and visual output use identical filtering.
- Do not probe sensitive fields unless requested where practical.
- No network calls, telemetry, third-party runtime dependencies, or `shell=True`.
- Subprocess collectors use fixed executable argument lists and timeouts.

## Error handling
Collection is best-effort by section. Missing optional fields become `None`; missing repeated devices become empty collections. Failure of one section does not discard valid sections. Unsupported platforms fail clearly only when no backend exists.

## Import and compatibility constraints
- Preserve lazy-import behavior.
- `import cereja` and `import cereja.system` must not probe hardware, launch subprocesses, query registries, or start threads.
- Zero third-party runtime dependencies.
- Do not change unrelated public APIs.
- Update static export/stub declarations required by Cereja's lazy API tooling.

## Testing
- Pure model/serialization tests.
- Collector parser tests using fixtures and separated I/O adapters.
- Real backend smoke tests on Windows, Linux, and macOS CI runners with invariant assertions rather than exact vendor values.
- CLI tests for visual basic output, `--full`, `--sensitive`, `--json`, `--section`, and import side-effect isolation.

## Initial scope
Included: system identity, OS, CPU, memory modules where exposed, GPUs, motherboard, BIOS/firmware, visual CLI, JSON CLI, basic/full/sensitive controls.

Deferred: disks/storage, network adapters, batteries, monitors, sensors/temperatures/fans, CUDA runtime/toolkit, installed software, live utilization, continuous monitoring.