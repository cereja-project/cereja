"""Human-readable rendering for system inventory."""

from __future__ import annotations

from .models import HardwareInfo


def format_bytes(value: int | None) -> str | None:
    if value is None:
        return None
    size = float(value)
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    unit = units[0]
    for unit in units:
        if abs(size) < 1024.0 or unit == units[-1]:
            break
        size /= 1024.0
    return f"{size:.1f} {unit}"


def _rows(title, pairs):
    values = [(label, value) for label, value in pairs if value not in (None, "")]
    if not values:
        return []
    width = max(len(label) for label, _ in values)
    lines = [title]
    lines.extend(f"  {label:<{width}}  {value}" for label, value in values)
    return lines


def render(info: HardwareInfo) -> str:
    sections = []

    if info.system is not None:
        value = info.system
        sections.append(_rows("System", (
            ("Manufacturer", value.manufacturer),
            ("Model", value.model),
            ("Architecture", value.architecture),
            ("Total Memory", format_bytes(value.total_memory_bytes)),
            ("Machine", value.machine),
            ("Virtualization", value.virtualization),
            ("Serial Number", value.serial_number),
            ("Hardware UUID", value.hardware_uuid),
        )))

    if info.os is not None:
        value = info.os
        sections.append(_rows("Operating System", (
            ("Name", value.name),
            ("Edition", value.edition),
            ("Version", value.version),
            ("Build", value.build),
            ("Architecture", value.architecture),
            ("Kernel", value.kernel),
            ("Kernel Version", value.kernel_version),
            ("Install Date", value.install_date),
            ("Boot Time", value.boot_time),
            ("Timezone", value.timezone),
            ("Locale", value.locale),
            ("Platform", value.platform),
            ("Python Arch", value.python_architecture),
            ("Hostname", value.hostname),
        )))

    if info.cpu is not None:
        value = info.cpu
        sections.append(_rows("CPU", (
            ("Name", value.name),
            ("Manufacturer", value.manufacturer),
            ("Cores", value.cores),
            ("Logical Processors", value.logical_processors),
            ("Max Clock", f"{value.max_clock_mhz} MHz" if value.max_clock_mhz else None),
            ("Architecture", value.architecture),
            ("Identifier", value.identifier),
        )))

    if info.memory:
        pairs = []
        for index, value in enumerate(info.memory, 1):
            prefix = f"Module {index}"
            pairs.extend((
                (prefix, format_bytes(value.capacity_bytes)),
                ("  Manufacturer", value.manufacturer),
                ("  Speed", f"{value.speed_mts} MT/s" if value.speed_mts else None),
                ("  Configured Speed", f"{value.configured_speed_mts} MT/s" if value.configured_speed_mts else None),
                ("  Part Number", value.part_number),
                ("  Bank", value.bank_label),
                ("  Locator", value.device_locator),
                ("  Form Factor", value.form_factor),
                ("  Memory Type", value.memory_type),
                ("  Serial Number", value.serial_number),
            ))
        sections.append(_rows("Memory", pairs))

    if info.gpus:
        pairs = []
        for index, value in enumerate(info.gpus, 1):
            pairs.extend((
                (f"GPU {index}", value.name),
                ("  Manufacturer", value.manufacturer),
                ("  Adapter Memory", format_bytes(value.adapter_memory_bytes)),
                ("  Driver", value.driver_version),
                ("  Processor", value.processor),
            ))
        sections.append(_rows("GPU", pairs))

    if info.motherboard is not None:
        value = info.motherboard
        sections.append(_rows("Motherboard", (
            ("Manufacturer", value.manufacturer),
            ("Product", value.product),
            ("Version", value.version),
            ("Serial Number", value.serial_number),
        )))

    if info.bios is not None:
        value = info.bios
        sections.append(_rows("BIOS / Firmware", (
            ("Manufacturer", value.manufacturer),
            ("Version", value.version),
            ("Release Date", value.release_date),
            ("Serial Number", value.serial_number),
        )))

    rendered = [section for section in sections if section]
    lines = ["Cereja System Info", "─" * 48]
    for section in rendered:
        lines.append("")
        lines.extend(section)
    return "\n".join(lines) + "\n"
