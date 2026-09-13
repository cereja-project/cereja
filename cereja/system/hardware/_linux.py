"""Linux system inventory using /proc, /sys and stdlib."""

from __future__ import annotations

import os
import platform
import re

from ._common import clean, read_text, run_text, selected, to_int
from .collector import SECTIONS
from .models import (
    BIOSInfo,
    CPUInfo,
    GPUInfo,
    HardwareInfo,
    MotherboardInfo,
    OperatingSystemInfo,
    SystemInfo,
)


def _parse_os_release(text):
    result = {}
    for line in (text or "").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _cpu(text):
    fields = {}
    logical = 0
    for line in (text or "").splitlines():
        if line.startswith("processor"):
            logical += 1
        if ":" in line:
            key, value = line.split(":", 1)
            fields.setdefault(key.strip(), value.strip())
    return CPUInfo(
        name=clean(fields.get("model name") or fields.get("Hardware") or platform.processor()),
        manufacturer=clean(fields.get("vendor_id")),
        cores=to_int(fields.get("cpu cores")),
        logical_processors=logical or os.cpu_count(),
        architecture=platform.machine(),
    )


def _mem_total(text):
    match = re.search(r"^MemTotal:\s+(\d+)\s+kB", text or "", re.MULTILINE)
    return int(match.group(1)) * 1024 if match else None


def _gpu_manufacturer(description):
    known = (
        "NVIDIA Corporation",
        "Intel Corporation",
        "Advanced Micro Devices, Inc.",
        "AMD",
    )
    for vendor in known:
        if description.startswith(vendor):
            return vendor
    return None


def _gpus(runner, *, full=False):
    output = runner(["lspci", "-D"], timeout=5.0)
    if not output:
        return ()
    values = []
    markers = ("VGA compatible controller: ", "3D controller: ", "Display controller: ")
    for line in output.splitlines():
        description = None
        for marker in markers:
            if marker in line:
                description = line.split(marker, 1)[1].strip()
                break
        if not description:
            continue
        values.append(GPUInfo(
            name=description,
            manufacturer=_gpu_manufacturer(description),
            processor=description if full else None,
        ))
    return tuple(values)


def collect(
    *, detail="basic", include_sensitive=False, sections=SECTIONS,
    _read=read_text, _runner=run_text,
):
    full = detail == "full"
    os_release = _parse_os_release(_read("/etc/os-release"))
    cpu_text = _read("/proc/cpuinfo")
    mem_text = _read("/proc/meminfo")

    system = None
    if selected(sections, "system"):
        system = SystemInfo(
            manufacturer=clean(_read("/sys/class/dmi/id/sys_vendor")),
            model=clean(_read("/sys/class/dmi/id/product_name")),
            architecture=platform.machine(),
            total_memory_bytes=_mem_total(mem_text),
            machine=platform.machine() if full else None,
            serial_number=(
                clean(_read("/sys/class/dmi/id/product_serial"))
                if include_sensitive else None
            ),
            hardware_uuid=(
                clean(_read("/sys/class/dmi/id/product_uuid"))
                if include_sensitive else None
            ),
        )

    os_info = None
    if selected(sections, "os"):
        os_info = OperatingSystemInfo(
            name=clean(os_release.get("NAME")) or "Linux",
            edition=None,
            version=clean(os_release.get("VERSION_ID") or os_release.get("VERSION")),
            build=None,
            architecture=platform.machine(),
            kernel=platform.system(),
            kernel_version=platform.release() if full else None,
            timezone=None,
            locale=None,
            platform=platform.platform() if full else None,
            python_architecture=platform.architecture()[0] if full else None,
            hostname=platform.node() if full else None,
        )

    cpu = _cpu(cpu_text) if selected(sections, "cpu") else None
    gpus = _gpus(_runner, full=full) if selected(sections, "gpu") else ()

    motherboard = None
    if selected(sections, "motherboard"):
        motherboard = MotherboardInfo(
            manufacturer=clean(_read("/sys/class/dmi/id/board_vendor")),
            product=clean(_read("/sys/class/dmi/id/board_name")),
            version=clean(_read("/sys/class/dmi/id/board_version")),
            serial_number=(
                clean(_read("/sys/class/dmi/id/board_serial"))
                if include_sensitive else None
            ),
        )

    bios = None
    if selected(sections, "bios"):
        bios = BIOSInfo(
            manufacturer=clean(_read("/sys/class/dmi/id/bios_vendor")),
            version=clean(_read("/sys/class/dmi/id/bios_version")),
            release_date=clean(_read("/sys/class/dmi/id/bios_date")),
            serial_number=None,
        )

    return HardwareInfo(
        system=system,
        os=os_info,
        cpu=cpu,
        memory=(),
        gpus=gpus,
        motherboard=motherboard,
        bios=bios,
    )
