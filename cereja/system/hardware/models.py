"""Typed system and hardware inventory models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json


@dataclass(frozen=True, slots=True)
class SystemInfo:
    manufacturer: str | None = None
    model: str | None = None
    architecture: str | None = None
    total_memory_bytes: int | None = None
    machine: str | None = None
    virtualization: str | None = None
    serial_number: str | None = None
    hardware_uuid: str | None = None


@dataclass(frozen=True, slots=True)
class OperatingSystemInfo:
    name: str | None = None
    edition: str | None = None
    version: str | None = None
    build: str | None = None
    architecture: str | None = None
    kernel: str | None = None
    kernel_version: str | None = None
    install_date: str | None = None
    boot_time: str | None = None
    timezone: str | None = None
    locale: str | None = None
    platform: str | None = None
    python_architecture: str | None = None
    hostname: str | None = None


@dataclass(frozen=True, slots=True)
class CPUInfo:
    name: str | None = None
    manufacturer: str | None = None
    cores: int | None = None
    logical_processors: int | None = None
    max_clock_mhz: int | None = None
    architecture: str | None = None
    identifier: str | None = None


@dataclass(frozen=True, slots=True)
class MemoryInfo:
    capacity_bytes: int | None = None
    manufacturer: str | None = None
    speed_mts: int | None = None
    configured_speed_mts: int | None = None
    part_number: str | None = None
    bank_label: str | None = None
    device_locator: str | None = None
    form_factor: str | int | None = None
    memory_type: str | int | None = None
    serial_number: str | None = None


@dataclass(frozen=True, slots=True)
class GPUInfo:
    name: str | None = None
    manufacturer: str | None = None
    adapter_memory_bytes: int | None = None
    driver_version: str | None = None
    processor: str | None = None


@dataclass(frozen=True, slots=True)
class MotherboardInfo:
    manufacturer: str | None = None
    product: str | None = None
    version: str | None = None
    serial_number: str | None = None


@dataclass(frozen=True, slots=True)
class BIOSInfo:
    manufacturer: str | None = None
    version: str | None = None
    release_date: str | None = None
    serial_number: str | None = None


@dataclass(frozen=True, slots=True)
class HardwareInfo:
    system: SystemInfo | None = None
    os: OperatingSystemInfo | None = None
    cpu: CPUInfo | None = None
    memory: tuple[MemoryInfo, ...] = ()
    gpus: tuple[GPUInfo, ...] = ()
    motherboard: MotherboardInfo | None = None
    bios: BIOSInfo | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, *, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, sort_keys=True)
