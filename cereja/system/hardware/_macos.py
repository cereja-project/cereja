"""macOS system inventory using system_profiler and stdlib."""

from __future__ import annotations

import platform
import re

from ._common import clean, run_json, selected, to_int
from .collector import SECTIONS
from .models import (
    CPUInfo,
    GPUInfo,
    HardwareInfo,
    MemoryInfo,
    OperatingSystemInfo,
    SystemInfo,
)


def _bytes_from_text(value):
    text = clean(value)
    if not text:
        return None
    match = re.match(r"([\d.]+)\s*(KB|MB|GB|TB)", text.upper())
    if not match:
        return None
    factors = {"KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3, "TB": 1024 ** 4}
    return int(float(match.group(1)) * factors[match.group(2)])


def collect(*, detail="basic", include_sensitive=False, sections=SECTIONS, _runner=run_json):
    payload = _runner(
        ["system_profiler", "SPHardwareDataType", "SPDisplaysDataType", "SPMemoryDataType", "-json"],
        timeout=10.0,
    )
    if not isinstance(payload, dict):
        payload = {}
    return _from_profiler(payload, detail=detail, include_sensitive=include_sensitive, sections=sections)


def _from_profiler(payload, *, detail, include_sensitive, sections):
    full = detail == "full"
    hardware_items = payload.get("SPHardwareDataType") or []
    hw = hardware_items[0] if hardware_items and isinstance(hardware_items[0], dict) else {}

    system = None
    if selected(sections, "system"):
        system = SystemInfo(
            manufacturer="Apple",
            model=clean(hw.get("machine_model") or hw.get("machine_name")),
            architecture=platform.machine(),
            total_memory_bytes=_bytes_from_text(hw.get("physical_memory")),
            machine=clean(hw.get("machine_name")) if full else None,
            serial_number=clean(hw.get("serial_number")) if include_sensitive else None,
            hardware_uuid=clean(hw.get("platform_UUID")) if include_sensitive else None,
        )

    os_info = None
    if selected(sections, "os"):
        version = platform.mac_ver()[0]
        os_info = OperatingSystemInfo(
            name="macOS",
            version=version or None,
            architecture=platform.machine(),
            kernel=platform.system(),
            kernel_version=platform.release() if full else None,
            platform=platform.platform() if full else None,
            python_architecture=platform.architecture()[0] if full else None,
            hostname=platform.node() if full else None,
        )

    cpu = None
    if selected(sections, "cpu"):
        cpu = CPUInfo(
            name=clean(hw.get("chip_type") or hw.get("cpu_type")),
            manufacturer="Apple" if hw.get("chip_type") else None,
            cores=to_int(hw.get("number_processors") or hw.get("number_cores")),
            logical_processors=to_int(hw.get("number_processors") or hw.get("number_cores")),
            architecture=platform.machine(),
        )

    gpus = ()
    if selected(sections, "gpu"):
        values = payload.get("SPDisplaysDataType") or []
        gpus = tuple(
            GPUInfo(
                name=clean(item.get("sppci_model") or item.get("_name")),
                manufacturer=clean(item.get("spdisplays_vendor")),
                adapter_memory_bytes=_bytes_from_text(item.get("spdisplays_vram")) if full else None,
                driver_version=clean(item.get("spdisplays_metal")) if full else None,
                processor=clean(item.get("sppci_model")) if full else None,
            )
            for item in values if isinstance(item, dict)
        )

    memory = ()
    if selected(sections, "memory"):
        values = payload.get("SPMemoryDataType") or []
        memory = tuple(
            MemoryInfo(
                capacity_bytes=_bytes_from_text(item.get("dimm_size") or item.get("size")),
                manufacturer=clean(item.get("dimm_manufacturer")),
                speed_mts=to_int(str(item.get("dimm_speed") or "").split()[0]),
                part_number=clean(item.get("dimm_part_number")) if full else None,
                serial_number=clean(item.get("dimm_serial_number")) if include_sensitive else None,
            )
            for item in values if isinstance(item, dict)
        )

    return HardwareInfo(system=system, os=os_info, cpu=cpu, memory=memory, gpus=gpus)
