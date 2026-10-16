"""Bounded CJZ operations with exclusive publication and owned staging.

Legacy APIs remain unchanged. Safe directory format CJZD/3 adds directory
records; this reader also accepts the file-only CJZD/2 stream. No encryption,
links, special files, merging or overwrite is supported by this bounded API.
"""
from dataclasses import dataclass
from contextlib import contextmanager
import os
from pathlib import Path
import stat
import struct
import tempfile
import unicodedata
import zlib

from ._compress import compress, _DIR_ARCHIVE_MAGIC, _read_exact
from ._crypto import _publish
from cereja.system._safe_paths import ordinary_path as _ordinary, new_destination as _destination

MAGIC = b'CJZD\x03'
CHUNK = 65536


@dataclass(frozen=True, slots=True)
class ArchiveLimits:
    max_input_bytes: int = 16 * 1024 * 1024
    max_member_bytes: int = 16 * 1024 * 1024
    max_output_bytes: int = 64 * 1024 * 1024
    max_members: int = 1024
    max_depth: int = 16
    max_path_bytes: int = 1024

    def __post_init__(self):
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= 1024 * 1024 * 1024:
                raise ValueError('Invalid archive limit: ' + name)


@dataclass(frozen=True, slots=True)
class ArchiveResult:
    destination: str
    members: int
    expanded_bytes: int


def _name(name, limits):
    if not name or len(name.encode('utf-8')) > limits.max_path_bytes:
        raise ValueError('Archive member path exceeds bounds')
    parts = name.split('/')
    if len(parts) > limits.max_depth:
        raise ValueError('Archive depth limit')
    for part in parts:
        stem = part.split('.')[0].upper()
        if (not part or part in ('.', '..') or part[-1] in '. '
                or any(ord(c) < 32 or ord(c) == 127 or c in '\\:<>"|?*' for c in part)
                or stem in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(10)), *(f'LPT{i}' for i in range(10))}):
            raise ValueError('Unsupported archive member path')
    return tuple(parts)


def _key(name):
    return unicodedata.normalize('NFC', name).casefold()


@contextmanager
def _stage(destination):
    # Sibling-owned root provides a cleanup boundary and same-filesystem publish.
    with tempfile.TemporaryDirectory(prefix='.cereja-archive-', dir=destination.parent) as directory:
        yield Path(directory)


class _BudgetReader:
    def __init__(self, stream, maximum):
        self.stream = stream
        self.maximum = maximum
        self.used = 0

    def read(self, size):
        data = self.stream.read(min(size, self.maximum - self.used + 1))
        self.used += len(data)
        if self.used > self.maximum:
            raise ValueError('Archive input byte limit')
        return data

    def tell(self):
        return self.used


def _inflate(data, output_limit):
    decoder = zlib.decompressobj()
    result = decoder.decompress(data, output_limit + 1)
    if len(result) > output_limit or decoder.unconsumed_tail:
        raise ValueError('Expanded byte limit')
    if not decoder.eof or decoder.unused_data:
        raise ValueError('Truncated stream or trailing compressed data')
    return result


def file_archive(source, destination, *, extract=False, limits=ArchiveLimits(), committing=None):
    source = _ordinary(source)
    target = _destination(destination)
    with source.open('rb') as stream:
        data = stream.read(limits.max_input_bytes + 1)
    if len(data) > limits.max_input_bytes:
        raise ValueError('Archive input byte limit')
    expanded_bytes = len(data)
    if extract:
        if data[:1] != b'\x10':
            raise ValueError('Bounded file extraction supports unencrypted zlib CJZ only')
        data = _inflate(data[1:], min(limits.max_member_bytes, limits.max_output_bytes))
        expanded_bytes = len(data)
    else:
        if len(data) > min(limits.max_member_bytes, limits.max_output_bytes):
            raise ValueError('Source byte limit')
        data, _ = compress(data, strategy='zlib')
        if len(data) > limits.max_input_bytes:
            raise ValueError('Compressed output byte limit')
    _destination(target)
    if committing:
        committing()
    # Existing exclusive hard-link publication; unsupported filesystems fail closed.
    _publish(str(target), data, False)
    return ArchiveResult(str(target), 1, expanded_bytes)


def _manifest(source, limits):
    records = []
    total = 0
    keys = set()
    spellings = {}
    stack = [(source, '')]
    while stack:
        directory, prefix = stack.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                if len(records) >= limits.max_members:
                    raise ValueError('Archive member-count limit')
                name = prefix + entry.name
                parts = _name(name, limits)
                key = _key(name)
                for index in range(1, len(parts) + 1):
                    spelling = '/'.join(parts[:index])
                    normalized = _key(spelling)
                    if normalized in spellings and spellings[normalized] != spelling:
                        raise ValueError('Normalized parent/member collision')
                    spellings[normalized] = spelling
                if key in keys:
                    raise ValueError('Normalized archive collision')
                keys.add(key)
                info = entry.stat(follow_symlinks=False)
                if (stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400
                        or info.st_nlink > 1 and stat.S_ISREG(info.st_mode)):
                    raise ValueError('Links are unsupported')
                if stat.S_ISDIR(info.st_mode):
                    records.append((name, True, 0))
                    stack.append((Path(entry.path), name + '/'))
                elif stat.S_ISREG(info.st_mode):
                    if info.st_size > limits.max_member_bytes:
                        raise ValueError('Member byte limit')
                    total += info.st_size
                    if total > limits.max_output_bytes:
                        raise ValueError('Aggregate expanded byte limit')
                    records.append((name, False, info.st_size))
                else:
                    raise ValueError('Special archive members are unsupported')
    return sorted(records), total


def create_directory_archive(source, destination, *, limits=ArchiveLimits(), committing=None):
    source = _ordinary(source, directory=True)
    target = _destination(destination)
    if target.is_relative_to(source):
        raise ValueError('Destination must be outside source tree')
    records, total = _manifest(source, limits)
    with _stage(target) as stage:
        temporary = stage / 'archive'
        with temporary.open('wb') as output:
            output.write(MAGIC)
            for name, directory, size in records:
                encoded = name.encode('utf-8')
                output.write(b'\x02' if directory else b'\x01')
                output.write(struct.pack('>I', len(encoded)))
                output.write(encoded)
                if directory:
                    continue
                output.write(struct.pack('>Q', size))
                output.write(b'\x10')
                compressor = zlib.compressobj()
                observed = 0
                path = _ordinary(source / name)
                with path.open('rb') as stream:
                    while True:
                        data = stream.read(min(CHUNK, size - observed + 1))
                        if not data:
                            break
                        observed += len(data)
                        if observed > size:
                            raise ValueError('Source changed during archiving')
                        chunk = compressor.compress(data)
                        if chunk:
                            output.write(struct.pack('>I', len(chunk)) + chunk)
                        if output.tell() > limits.max_input_bytes:
                            raise ValueError('Compressed byte limit')
                if observed != size:
                    raise ValueError('Source changed during archiving')
                chunk = compressor.flush()
                output.write(struct.pack('>I', len(chunk)) + chunk + b'\0\0\0\0')
            output.write(b'\0')
            if output.tell() > limits.max_input_bytes:
                raise ValueError('Compressed byte limit')
            output.flush()
            os.fsync(output.fileno())
        _destination(target)
        if committing:
            committing()
        os.link(temporary, target)
    return ArchiveResult(str(target), len(records), total)


def extract_directory_archive(source, destination, *, limits=ArchiveLimits(), committing=None):
    source = _ordinary(source)
    target = _destination(destination)
    # Windows rename refuses an existing target. POSIX rename can replace an
    # empty directory and provides no stdlib no-replace primitive for directories.
    if os.name != 'nt':
        raise ValueError('Exclusive directory publication currently requires Windows')
    if source.stat().st_size > limits.max_input_bytes:
        raise ValueError('Archive input byte limit')
    count = total = 0
    keys = {}
    spellings = {}
    with _stage(target) as stage:
        result = stage / 'result'
        result.mkdir()
        with source.open('rb') as raw_stream:
            stream = _BudgetReader(raw_stream, limits.max_input_bytes)
            magic = _read_exact(stream, len(MAGIC))
            if magic not in (MAGIC, _DIR_ARCHIVE_MAGIC):
                raise ValueError('Unsupported directory archive format')
            while True:
                tag = _read_exact(stream, 1)
                if tag == b'\0':
                    if stream.read(1):
                        raise ValueError('Trailing archive bytes')
                    break
                if tag not in (b'\x01', b'\x02') or tag == b'\x02' and magic != MAGIC:
                    raise ValueError('Unsupported archive member type')
                count += 1
                if count > limits.max_members:
                    raise ValueError('Member-count limit')
                length = struct.unpack('>I', _read_exact(stream, 4))[0]
                if not 0 < length <= limits.max_path_bytes:
                    raise ValueError('Member path byte limit')
                name = _read_exact(stream, length).decode('utf-8')
                parts = _name(name, limits)
                key = _key(name)
                for index in range(1, len(parts) + 1):
                    spelling = '/'.join(parts[:index])
                    normalized = _key(spelling)
                    if normalized in spellings and spellings[normalized] != spelling:
                        raise ValueError('Normalized parent/member collision')
                    spellings[normalized] = spelling
                if key in keys:
                    raise ValueError('Duplicate or normalized member collision')
                for index in range(1, len(parts)):
                    if keys.get(_key('/'.join(parts[:index]))) == 'file':
                        raise ValueError('File/directory conflict')
                if tag == b'\x01' and any(k.startswith(key + '/') for k in keys):
                    raise ValueError('File/directory conflict')
                keys[key] = 'directory' if tag == b'\x02' else 'file'
                output_path = result.joinpath(*parts)
                if tag == b'\x02':
                    output_path.mkdir(parents=True, exist_ok=True)
                    continue
                expected = struct.unpack('>Q', _read_exact(stream, 8))[0]
                if expected > limits.max_member_bytes or total + expected > limits.max_output_bytes:
                    raise ValueError('Expanded byte limit')
                if _read_exact(stream, 1) != b'\x10':
                    raise ValueError('Bounded directory extraction supports zlib only')
                output_path.parent.mkdir(parents=True, exist_ok=True)
                decoder = zlib.decompressobj()
                observed = 0
                with output_path.open('xb') as output:
                    while True:
                        size = struct.unpack('>I', _read_exact(stream, 4))[0]
                        if size == 0:
                            break
                        if size > limits.max_input_bytes or stream.tell() + size > limits.max_input_bytes:
                            raise ValueError('Compressed chunk limit')
                        remaining = expected - observed
                        chunk = decoder.decompress(_read_exact(stream, size), remaining + 1)
                        observed += len(chunk)
                        if observed > expected or decoder.unconsumed_tail or decoder.unused_data:
                            raise ValueError('Expanded byte limit or trailing stream')
                        output.write(chunk)
                    if not decoder.eof or observed != expected:
                        raise ValueError('Truncated stream or size mismatch')
                    output.flush()
                    os.fsync(output.fileno())
                total += observed
        _destination(target)
        if committing:
            committing()
        os.rename(result, target)
    return ArchiveResult(str(target), count, total)
