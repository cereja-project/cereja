"""Lazy APP-02 adapter: typed domain input, bounded safe string output only."""
import time
import re
from datetime import datetime, timezone

from .model import bounded_text

SECTIONS = ('system', 'os', 'cpu', 'memory', 'gpu', 'motherboard', 'bios')
DEFAULT_SECTIONS = ','.join(SECTIONS)
PROJECTION_BYTES = 12288
VALUE_BYTES = 512
MAX_ITEMS = 32


def parse_sections(value):
    if type(value) is not str or len(value) > 128:
        raise ValueError('Use comma-separated section names (128 characters maximum)')
    names = tuple(name.strip() for name in value.split(','))
    if not names or any(name not in SECTIONS for name in names) or len(set(names)) != len(names):
        raise ValueError('Use unique sections: ' + DEFAULT_SECTIONS)
    return tuple(name for name in SECTIONS if name in names)


def validate_sections(value):
    try:
        parse_sections(value)
    except ValueError as error:
        return str(error)
    return None


def project(inventory, sections):
    """Worker-owned inventory is never published or retained by the UI.

    Explicit model/field allowlist omits identity fields even on malformed safe
    defaults. Exact scalars only; at most 32 array entries, 512 bytes per value,
    12 KiB total. Truncation is visible. No to_dict graph or CLI text parsing.
    """
    from cereja.system.hardware.models import (
        HardwareInfo, SystemInfo, OperatingSystemInfo, CPUInfo, MemoryInfo,
        GPUInfo, MotherboardInfo, BIOSInfo)
    if type(inventory) is not HardwareInfo:
        raise TypeError('System collector must return HardwareInfo')
    # Validation applies equally to embedding callers and form submission.
    sections = parse_sections(','.join(sections))
    specs = (
        ('system', 'system', SystemInfo, ('manufacturer', 'model', 'architecture', 'total_memory_bytes')),
        ('os', 'os', OperatingSystemInfo, ('name', 'edition', 'version', 'build', 'architecture', 'kernel')),
        ('cpu', 'cpu', CPUInfo, ('name', 'manufacturer', 'cores', 'logical_processors', 'max_clock_mhz', 'architecture')),
        ('memory', 'memory', MemoryInfo, ('capacity_bytes', 'manufacturer', 'speed_mts', 'configured_speed_mts')),
        ('gpu', 'gpus', GPUInfo, ('name', 'manufacturer', 'adapter_memory_bytes', 'driver_version')),
        ('motherboard', 'motherboard', MotherboardInfo, ('manufacturer', 'product', 'version')),
        ('bios', 'bios', BIOSInfo, ('manufacturer', 'version', 'release_date')),
    )
    lines = ['System information | basic | identifiers excluded',
             'Unavailable means not reported. The facade supplies no per-field reasons or warnings.']
    budget = sum(len(line.encode('utf-8')) + 1 for line in lines)
    truncated = False
    def add(line):
        nonlocal budget, truncated
        size = len(line.encode('utf-8')) + 1
        if budget + size > PROJECTION_BYTES - 64:
            truncated = True
            return False
        lines.append(line)
        budget += size
        return True
    for section, attribute, model, fields in specs:
        if section not in sections:
            continue
        if not add('\n[' + section + ']'):
            break
        value = getattr(inventory, attribute)
        multiple = section in ('memory', 'gpu')
        if multiple and type(value) is not tuple:
            raise TypeError('System collection must use immutable typed section tuples')
        items = value[:MAX_ITEMS] if multiple else (value,)
        if multiple and len(value) > MAX_ITEMS:
            truncated = True
        if not items or value is None:
            add('Unavailable')
            continue
        for index, item in enumerate(items):
            if type(item) is not model:
                raise TypeError('System section has an unexpected model')
            if multiple and not add('Item ' + str(index + 1)):
                break
            for field in fields:
                raw = getattr(item, field)
                if raw is None or (type(raw) is str and raw == ''):
                    text = 'Unavailable'
                elif type(raw) is str:
                    text, cut = bounded_text(raw, VALUE_BYTES)
                    truncated = truncated or cut
                    text = text.replace('\n', ' ').replace('\t', ' ')
                elif type(raw) is int and -(1 << 63) <= raw <= (1 << 63) - 1:
                    text = str(raw)
                else:
                    raise TypeError('System field must be a bounded exact scalar')
                if not add('  ' + field + ': ' + text):
                    break
            if budget > PROJECTION_BYTES - 600:
                truncated = True
                break
        if budget > PROJECTION_BYTES - 600:
            break
    if truncated:
        lines.append('[Content truncated: projection limits]')
    return '\n'.join(lines)


def collect(context, sections):
    """No progress/cancel/commit claims; failures publish only a fixed class label."""
    from cereja.system import hardware
    context.running()
    started = time.monotonic()
    try:
        inventory = hardware.info(detail='basic', include_sensitive=False, sections=sections)
        duration = time.monotonic() - started
        text = project(inventory, sections)
    except Exception as error:
        # Never publish collector exception arguments (paths, commands or IDs).
        name = type(error).__name__
        if name not in ('RuntimeError', 'OSError', 'ValueError', 'TypeError', 'TimeoutError', 'PermissionError'):
            name = 'CollectorError'
        raise RuntimeError(f'System collection unavailable ({name}); elapsed {time.monotonic() - started:.3f}s') from None
    return f'Observed at: {datetime.now(timezone.utc).isoformat(timespec="seconds")}\nCollection duration: {duration:.3f}s (monotonic)\n' + text


def failure_text(message):
    # Bridge diagnostics may describe start/cleanup/publication failures. Display
    # only the adapter's fixed grammar, never arbitrary exception arguments.
    if re.fullmatch(r'RuntimeError: System collection unavailable \((RuntimeError|OSError|ValueError|TypeError|TimeoutError|PermissionError|CollectorError)\); elapsed [0-9]+\.[0-9]{3}s', message):
        return message.removeprefix('RuntimeError: ')
    return 'System collection failed. Diagnostic details omitted; prior snapshots remain selectable.'
