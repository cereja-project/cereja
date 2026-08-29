"""Minimal, dependency-free PE metadata inspection for static analysis."""
import hashlib
import struct
from datetime import datetime, timezone


class PEFormatError(ValueError):
    """Raised when bytes do not contain a supported Portable Executable."""


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _u64(data: bytes, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def inspect_pe(data: bytes) -> dict:
    """Return bounded PE metadata without loading or executing the image."""
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise PEFormatError("not a PE file")
    pe_offset = _u32(data, 0x3C)
    if pe_offset + 24 > len(data) or data[pe_offset:pe_offset + 4] != b"PE\0\0":
        raise PEFormatError("invalid PE signature")

    coff = pe_offset + 4
    machine = _u16(data, coff)
    section_count = _u16(data, coff + 2)
    timestamp = _u32(data, coff + 4)
    optional_size = _u16(data, coff + 16)
    optional = coff + 20
    if optional + optional_size > len(data):
        raise PEFormatError("truncated optional header")

    magic = _u16(data, optional)
    if magic == 0x20B:
        pe_type = "pe32+"
        entry_point = _u32(data, optional + 16)
        image_base = _u64(data, optional + 24)
        subsystem = _u16(data, optional + 68)
        directory_offset = optional + 112
        thunk_width = 8
    elif magic == 0x10B:
        pe_type = "pe32"
        entry_point = _u32(data, optional + 16)
        image_base = _u32(data, optional + 28)
        subsystem = _u16(data, optional + 68)
        directory_offset = optional + 96
        thunk_width = 4
    else:
        raise PEFormatError("unsupported optional header")

    if optional_size < (directory_offset - optional) + 4:
        raise PEFormatError("optional header too small for data directories")
    directory_count = _u32(data, directory_offset - 4)
    directory_limit = min(directory_count, 16)
    if directory_offset + directory_limit * 8 > optional + optional_size:
        raise PEFormatError("truncated data directory table")
    directories = [
        (_u32(data, directory_offset + index * 8), _u32(data, directory_offset + index * 8 + 4))
        for index in range(directory_limit)
    ]

    section_table = optional + optional_size
    sections = []
    for index in range(section_count):
        offset = section_table + index * 40
        if offset + 40 > len(data):
            raise PEFormatError("truncated section table")
        virtual_size = _u32(data, offset + 8)
        virtual_address = _u32(data, offset + 12)
        raw_size = _u32(data, offset + 16)
        raw_pointer = _u32(data, offset + 20)
        sections.append((virtual_address, max(virtual_size, raw_size), raw_pointer))

    def rva_to_offset(rva: int):
        for virtual_address, span, raw_pointer in sections:
            if virtual_address <= rva < virtual_address + span:
                offset = raw_pointer + (rva - virtual_address)
                return offset if 0 <= offset < len(data) else None
        if rva < section_table:
            return rva
        return None

    imports = []
    if len(directories) > 1:
        import_rva, import_size = directories[1]
        descriptor = rva_to_offset(import_rva) if import_rva else None
        if descriptor is not None:
            descriptor_limit = min(len(data), descriptor + max(import_size, 20))
            for _ in range(4096):
                if descriptor + 20 > len(data):
                    break
                original_thunk = _u32(data, descriptor)
                name_rva = _u32(data, descriptor + 12)
                first_thunk = _u32(data, descriptor + 16)
                if original_thunk == name_rva == first_thunk == 0:
                    break
                name_offset = rva_to_offset(name_rva)
                if name_offset is None:
                    break
                name_end = data.find(b"\0", name_offset, min(len(data), name_offset + 512))
                if name_end == -1:
                    name_end = min(len(data), name_offset + 512)
                dll = data[name_offset:name_end].decode("ascii", "replace")

                thunk_offset = rva_to_offset(original_thunk or first_thunk)
                if thunk_offset is None:
                    break
                ordinal_flag = 1 << (thunk_width * 8 - 1)
                for index in range(65536):
                    offset = thunk_offset + index * thunk_width
                    if offset + thunk_width > len(data):
                        break
                    value = _u64(data, offset) if thunk_width == 8 else _u32(data, offset)
                    if value == 0:
                        break
                    if value & ordinal_flag:
                        symbol = f"ord{value & 0xFFFF}"
                    else:
                        hint_name = rva_to_offset(value)
                        if hint_name is None or hint_name + 2 >= len(data):
                            break
                        symbol_offset = hint_name + 2
                        symbol_end = data.find(b"\0", symbol_offset, min(len(data), symbol_offset + 1024))
                        if symbol_end == -1:
                            symbol_end = min(len(data), symbol_offset + 1024)
                        symbol = data[symbol_offset:symbol_end].decode("ascii", "replace")
                    imports.append((dll, symbol))
                descriptor += 20
                if import_size and descriptor > descriptor_limit:
                    break

    imphash_parts = []
    for dll, symbol in imports:
        normalized = dll.lower()
        for extension in (".dll", ".ocx", ".sys"):
            if normalized.endswith(extension):
                normalized = normalized[:-len(extension)]
                break
        imphash_parts.append(f"{normalized}.{symbol.lower()}")
    imphash = hashlib.md5(",".join(imphash_parts).encode()).hexdigest() if imphash_parts else None

    security_rva, security_size = directories[4] if len(directories) > 4 else (0, 0)
    return {
        "pe_type": pe_type,
        "machine": f"0x{machine:04x}",
        "sections": section_count,
        "entry_point_rva": f"0x{entry_point:x}",
        "image_base": f"0x{image_base:x}",
        "subsystem": subsystem,
        "compile_timestamp": datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z"),
        "signed": bool(security_rva and security_size),
        "import_count": len(imports),
        "import_dlls": sorted({dll for dll, _ in imports}, key=str.lower),
        "imphash": imphash,
    }
