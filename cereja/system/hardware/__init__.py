"""Cross-platform system and hardware inventory."""

from .collector import DETAILS, SECTIONS, info
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

__all__ = (
    "BIOSInfo",
    "CPUInfo",
    "DETAILS",
    "GPUInfo",
    "HardwareInfo",
    "MemoryInfo",
    "MotherboardInfo",
    "OperatingSystemInfo",
    "SECTIONS",
    "SystemInfo",
    "info",
)
