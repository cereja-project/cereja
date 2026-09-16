"""Windows system inventory via PowerShell CIM."""

from __future__ import annotations

from collections import Counter
import csv
import io
import platform

from ._common import clean, run_json, run_text, selected, to_int
from .collector import SECTIONS
from .models import (
    BIOSInfo,
    CPUInfo,
    GPUInfo,
    HardwareInfo,
    MemoryInfo,
    MotherboardInfo,
    OperatingSystemInfo,
    SystemInfo,
)


def _script(include_sensitive):
    if include_sensitive:
        memory_fields = (
            "Capacity,Manufacturer,Speed,ConfiguredClockSpeed,PartNumber,"
            "BankLabel,DeviceLocator,FormFactor,SMBIOSMemoryType,SerialNumber"
        )
        board_fields = "Manufacturer,Product,Version,SerialNumber"
        bios_fields = "Manufacturer,SMBIOSBIOSVersion,ReleaseDate,SerialNumber"
        product_line = (
            "  product = Get-CimInstance Win32_ComputerSystemProduct | "
            "Select-Object IdentifyingNumber,UUID\n"
        )
    else:
        memory_fields = (
            "Capacity,Manufacturer,Speed,ConfiguredClockSpeed,PartNumber,"
            "BankLabel,DeviceLocator,FormFactor,SMBIOSMemoryType"
        )
        board_fields = "Manufacturer,Product,Version"
        bios_fields = "Manufacturer,SMBIOSBIOSVersion,ReleaseDate"
        product_line = ""

    return (
        "$ErrorActionPreference = 'SilentlyContinue'\n"
        "$result = [ordered]@{\n"
        "  computer = Get-CimInstance Win32_ComputerSystem | "
        "Select-Object Manufacturer,Model,SystemType,TotalPhysicalMemory\n"
        f"{product_line}"
        "  os = Get-CimInstance Win32_OperatingSystem | "
        "Select-Object Caption,Version,BuildNumber,OSArchitecture,"
        "InstallDate,LastBootUpTime,LocalDateTime,CSName\n"
        "  cpu = Get-CimInstance Win32_Processor | Select-Object -First 1 "
        "Name,Manufacturer,NumberOfCores,NumberOfLogicalProcessors,"
        "MaxClockSpeed,Architecture,ProcessorId\n"
        "  memory = @(Get-CimInstance Win32_PhysicalMemory | "
        f"Select-Object {memory_fields})\n"
        "  gpu = @(Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterCompatibility,"
        "DriverVersion,VideoProcessor)\n"
        "  board = Get-CimInstance Win32_BaseBoard | "
        f"Select-Object {board_fields}\n"
        "  bios = Get-CimInstance Win32_BIOS | "
        f"Select-Object {bios_fields}\n"
        "}\n"
        "$result | ConvertTo-Json -Depth 5 -Compress\n"
    )


def collect(*, detail="basic", include_sensitive=False, sections=SECTIONS, _runner=run_json):
    payload = _runner(
        [
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            _script(include_sensitive),
        ],
        timeout=10.0,
    )
    if not isinstance(payload, dict):
        payload = {}
    gpu_memory = {}
    if detail == "full" and selected(sections, "gpu"):
        gpu_memory = _nvidia_memory(_items(payload.get("gpu")))
    return _from_cim(
        payload,
        detail=detail,
        include_sensitive=include_sensitive,
        sections=sections,
        gpu_memory=gpu_memory,
    )


def _items(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _gpu_name(item):
    return (clean(item.get("Name")) or "").casefold()


def _nvidia_memory(gpus, *, _runner=run_text):
    """Return driver-reported bytes only for unambiguous NVIDIA adapters.

    CIM AdapterRAM is uint32 and cannot describe modern VRAM capacities.
    Names must be unique in both inventories; enumeration order is not an ID.
    """
    names = Counter(_gpu_name(item) for item in gpus if isinstance(item, dict))
    candidates = {
        _gpu_name(item)
        for item in gpus
        if isinstance(item, dict) and _gpu_name(item) and (
            "nvidia" in (clean(item.get("AdapterCompatibility")) or "").casefold()
            or _gpu_name(item).startswith("nvidia ")
        )
    }
    if not any(names[name] == 1 for name in candidates):
        return {}
    output = _runner(
        ["nvidia-smi", "--query-gpu=name,memory.total",
         "--format=csv,noheader,nounits"],
        timeout=5.0,
    )
    if not output:
        return {}
    rows = {}
    try:
        for row in csv.reader(io.StringIO(output), skipinitialspace=True, strict=True):
            if not row:
                continue
            if len(row) != 2:
                return {}
            name = row[0].strip().casefold()
            mib = to_int(row[1].strip())
            memory = mib * 1024 ** 2 if mib is not None and mib > 0 else None
            rows.setdefault(name, []).append(memory)
    except csv.Error:
        return {}
    return {
        name: values[0]
        for name, values in rows.items()
        if name in candidates and names[name] == 1
        and len(values) == 1 and values[0] is not None
    }


def _date(value):
    text = clean(value)
    if not text:
        return None
    if len(text) >= 8 and text[:8].isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text


def _from_cim(payload, *, detail, include_sensitive, sections, gpu_memory=None):
    computer = payload.get("computer") or {}
    product = payload.get("product") or {}
    os_data = payload.get("os") or {}
    cpu_data = payload.get("cpu") or {}
    board = payload.get("board") or {}
    bios = payload.get("bios") or {}
    full = detail == "full"
    gpu_memory = gpu_memory or {}

    system = None
    if selected(sections, "system"):
        system = SystemInfo(
            manufacturer=clean(computer.get("Manufacturer")),
            model=clean(computer.get("Model")),
            architecture=clean(computer.get("SystemType")) or platform.machine(),
            total_memory_bytes=to_int(computer.get("TotalPhysicalMemory")),
            machine=clean(computer.get("SystemType")) if full else None,
            serial_number=(
                clean(product.get("IdentifyingNumber"))
                if include_sensitive else None
            ),
            hardware_uuid=(
                clean(product.get("UUID")) if include_sensitive else None
            ),
        )

    os_info = None
    if selected(sections, "os"):
        caption = clean(os_data.get("Caption"))
        edition = None
        if caption and "Windows" in caption:
            remainder = caption.split("Windows", 1)[1].strip()
            parts = remainder.split(" ", 1)
            edition = parts[1] if len(parts) == 2 else remainder or None
        os_info = OperatingSystemInfo(
            name=caption or "Windows",
            edition=edition,
            version=clean(os_data.get("Version")),
            build=clean(os_data.get("BuildNumber")),
            architecture=clean(os_data.get("OSArchitecture")),
            kernel="Windows NT",
            kernel_version=platform.version() if full else None,
            install_date=_date(os_data.get("InstallDate")) if full else None,
            boot_time=_date(os_data.get("LastBootUpTime")) if full else None,
            platform=platform.platform() if full else None,
            python_architecture=platform.architecture()[0] if full else None,
            hostname=clean(os_data.get("CSName")) if full else None,
        )

    cpu = None
    if selected(sections, "cpu"):
        cpu = CPUInfo(
            name=clean(cpu_data.get("Name")),
            manufacturer=clean(cpu_data.get("Manufacturer")),
            cores=to_int(cpu_data.get("NumberOfCores")),
            logical_processors=to_int(cpu_data.get("NumberOfLogicalProcessors")),
            max_clock_mhz=(
                to_int(cpu_data.get("MaxClockSpeed")) if full else None
            ),
            architecture=(
                str(cpu_data.get("Architecture"))
                if full and cpu_data.get("Architecture") is not None else None
            ),
            identifier=clean(cpu_data.get("ProcessorId")) if full else None,
        )

    memory = ()
    if selected(sections, "memory"):
        memory = tuple(
            MemoryInfo(
                capacity_bytes=to_int(item.get("Capacity")),
                manufacturer=clean(item.get("Manufacturer")),
                speed_mts=to_int(item.get("Speed")),
                configured_speed_mts=(
                    to_int(item.get("ConfiguredClockSpeed")) if full else None
                ),
                part_number=clean(item.get("PartNumber")) if full else None,
                bank_label=clean(item.get("BankLabel")) if full else None,
                device_locator=(
                    clean(item.get("DeviceLocator")) if full else None
                ),
                form_factor=item.get("FormFactor") if full else None,
                memory_type=item.get("SMBIOSMemoryType") if full else None,
                serial_number=(
                    clean(item.get("SerialNumber"))
                    if include_sensitive else None
                ),
            )
            for item in _items(payload.get("memory"))
            if isinstance(item, dict)
        )

    gpus = ()
    if selected(sections, "gpu"):
        gpus = tuple(
            GPUInfo(
                name=clean(item.get("Name")),
                manufacturer=clean(item.get("AdapterCompatibility")),
                adapter_memory_bytes=(
                    gpu_memory.get(_gpu_name(item)) if full else None
                ),
                driver_version=(
                    clean(item.get("DriverVersion")) if full else None
                ),
                processor=clean(item.get("VideoProcessor")) if full else None,
            )
            for item in _items(payload.get("gpu"))
            if isinstance(item, dict)
        )

    motherboard = None
    if selected(sections, "motherboard"):
        motherboard = MotherboardInfo(
            manufacturer=clean(board.get("Manufacturer")),
            product=clean(board.get("Product")),
            version=clean(board.get("Version")),
            serial_number=(
                clean(board.get("SerialNumber")) if include_sensitive else None
            ),
        )

    bios_info = None
    if selected(sections, "bios"):
        bios_info = BIOSInfo(
            manufacturer=clean(bios.get("Manufacturer")),
            version=clean(bios.get("SMBIOSBIOSVersion")),
            release_date=_date(bios.get("ReleaseDate")),
            serial_number=(
                clean(bios.get("SerialNumber")) if include_sensitive else None
            ),
        )

    return HardwareInfo(
        system, os_info, cpu, memory, gpus, motherboard, bios_info
    )
