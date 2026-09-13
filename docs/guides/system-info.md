# System information

Cereja can inspect basic operating-system and hardware information without third-party runtime dependencies.
The Python API and CLI share the same typed inventory model, and collection is performed only when requested.

## Command line

Run the default safe-to-share summary with:

```bash
cereja system info
```

The default output is grouped for humans and includes the operating system, machine, CPU, memory, GPU,
motherboard, and firmware information that the current platform can expose. Unique hardware identifiers are
not included by default.

Request additional technical fields with:

```bash
cereja system info --full
```

Allow serial numbers, hardware UUIDs, and other unique identifiers explicitly with:

```bash
cereja system info --sensitive
cereja system info --full --sensitive
```

Sensitive output is intended for local diagnostics. Review it before attaching it to public issues or logs.

For scripts and automation, emit deterministic JSON:

```bash
cereja system info --json
cereja system info --full --json
```

Limit collection to one or more sections with repeatable `--section` flags:

```bash
cereja system info --section os
cereja system info --section cpu --section gpu --json
```

Supported sections are `system`, `os`, `cpu`, `memory`, `gpu`, `motherboard`, and `bios`.

## Python API

```python
from cereja.system import hardware

inventory = hardware.info()
print(inventory.cpu.name if inventory.cpu else None)
print(inventory.to_json(indent=2))
```

Use `detail="full"` for additional technical fields and `include_sensitive=True` only when unique identifiers
are intentionally required:

```python
inventory = hardware.info(
    detail="full",
    include_sensitive=True,
    sections=["system", "os", "cpu"],
)
```

`HardwareInfo` is composed of immutable typed models for system, operating system, CPU, memory, GPU,
motherboard, and BIOS/firmware data. `to_dict()` and `to_json()` serialize that same model; the CLI does not
maintain a separate JSON schema.

## Platform behavior

Inventory availability depends on the operating system, firmware, permissions, drivers, and utilities installed
on the host. Missing information is normal and is represented by `None` or an empty collection rather than an
invented value.

- **Windows:** Cereja queries CIM through a fixed PowerShell command and parses JSON output. Sensitive CIM
  fields are requested only when sensitive collection is enabled.
- **Linux:** Cereja reads standard `/proc`, `/sys`, DMI, and OS-release interfaces. GPU names are collected
  best-effort through `lspci` when that standard system utility is available.
- **macOS:** Cereja uses `platform` plus structured `system_profiler` output. Traditional PC motherboard/BIOS
  fields may not have direct macOS equivalents.

No network request or telemetry is performed. Importing `cereja` or `cereja.system` does not probe the machine;
collection starts only when `hardware.info()` or `cereja system info` is invoked.
