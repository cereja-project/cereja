"""Windows system inventory via PowerShell CIM."""

from __future__ import annotations

import platform

from ._common import clean, run_json, selected, to_int
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

_SCRIPT = r'''
$ErrorActionPreference = 'SilentlyContinue'
$result = [ordered]@{
  computer = Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model,SystemType,TotalPhysicalMemory
  os = Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,OSArchitecture,InstallDate,LastBootUpTime,LocalDateTime,CSName
  cpu = Get-CimInstance Win32_Processor | Select-Object -First 1 Name,Manufacturer,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,Architecture,ProcessorId
  memory = @(Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity,Manufacturer,Speed,ConfiguredClockSpeed,PartNumber,BankLabel,DeviceLocator,FormFactor,SMBIOSMemoryType,SerialNumber)
  gpu = @(Get-CimInstance Win32_VideoController | Select-Object Name,AdapterCompatibility,AdapterRAM,DriverVersion,VideoProcessor)
  board = Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer,Product,Version,SerialNumber
  bios = Get-CimInstance Win32_BIOS | Select-Object Manufacturer,SMBIOSBIOSVersion,ReleaseDate,SerialNumber
}
$result | ConvertTo-Json -Depth 5 -Compress
'''


def collect(*, detail="basic", include_sensitive=False, sections=SECTIONS, _runner=run_json):
    payload = _runner(["powershell", "-NoProfile", "-NonInteractive", "-Command", _SCRIPT], timeout=10.0)
    if not isinstance(payload, dict):
        payload = {}
    return _from_cim(payload, detail=detail, include_sensitive=include_sensitive, sections=sections)


def _items(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _date(value):
    text = clean(value)
    if not text:
        return None
    if len(text) >= 8 and text[:8].isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text


def _from_cim(payload, *, detail, include_sensitive, sections):
    computer = payload.get("computer") or {}
    os_data = payload.get("os") or {}
    cpu_data = payload.get("cpu") or {}
    board = payload.get("board") or {}
    bios = payload.get("bios") or {}
    full = detail == "full"

    system = None
    if selected(sections, "system"):
        system = SystemInfo(
            manufacturer=clean(computer.get("Manufacturer")),
            model=clean(computer.get("Model")),
            architecture=clean(computer.get("SystemType")) or platform.machine(),
            total_memory_bytes=to_int(computer.get("TotalPhysicalMemory")),
        )

    os_info = None
    if selected(sections, "os"):
        caption = clean(os_data.get("Caption"))
        edition = None
        if caption and "Windows" in caption:
            edition = caption.split("Windows", 1)[1].strip() or None
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
            timezone=None,
            locale=None,
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
            max_clock_mhz=to_int(cpu_data.get("MaxClockSpeed")) if full else None,
            architecture=str(cpu_data.get("Architecture")) if full and cpu_data.get("Architecture") is not None else None,
            identifier=clean(cpu_data.get("ProcessorId")) if full else None,
        )

    memory = ()
    if selected(sections, "memory"):
        memory = tuple(
            MemoryInfo(
                capacity_bytes=to_int(item.get("Capacity")),
                manufacturer=clean(item.get("Manufacturer")),
                speed_mts=to_int(item.get("Speed")),
                configured_speed_mts=to_int(item.get("ConfiguredClockSpeed")) if full else None,
                part_number=clean(item.get("PartNumber")) if full else None,
                bank_label=clean(item.get("BankLabel")) if full else None,
                device_locator=clean(item.get("DeviceLocator")) if full else None,
                form_factor=item.get("FormFactor") if full else None,
                memory_type=item.get("SMBIOSMemoryType") if full else None,
                serial_number=clean(item.get("SerialNumber")) if include_sensitive else None,
            )
            for item in _items(payload.get("memory")) if isinstance(item, dict)
        )

    gpus = ()
    if selected(sections, "gpu"):
        gpus = tuple(
            GPUInfo(
                name=clean(item.get("Name")),
                manufacturer=clean(item.get("AdapterCompatibility")),
                adapter_memory_bytes=to_int(item.get("AdapterRAM")) if full else None,
                driver_version=clean(item.get("DriverVersion")) if full else None,
                processor=clean(item.get("VideoProcessor")) if full else None,
            )
            for item in _items(payload.get("gpu")) if isinstance(item, dict)
        )

    motherboard = None
    if selected(sections, "motherboard"):
        motherboard = MotherboardInfo(
            manufacturer=clean(board.get("Manufacturer")),
            product=clean(board.get("Product")),
            version=clean(board.get("Version")),
            serial_number=clean(board.get("SerialNumber")) if include_sensitive else None,
        )

    bios_info = None
    if selected(sections, "bios"):
        bios_info = BIOSInfo(
            manufacturer=clean(bios.get("Manufacturer")),
            version=clean(bios.get("SMBIOSBIOSVersion")),
            release_date=_date(bios.get("ReleaseDate")),
            serial_number=clean(bios.get("SerialNumber")) if include_sensitive else None,
        )

    return HardwareInfo(system, os_info, cpu, memory, gpus, motherboard, bios_info)
