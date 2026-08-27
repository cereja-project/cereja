"""Bounded, side-effect-free file inspection primitives."""
import hashlib
import math
import re
from collections import Counter

from ._models import FileHashes

MAX_STRING_SCAN = 4 * 1024 * 1024


def hash_bytes(data: bytes) -> FileHashes:
    git_header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return FileHashes(
        md5=hashlib.md5(data).hexdigest(),
        sha1=hashlib.sha1(data).hexdigest(),
        sha256=hashlib.sha256(data).hexdigest(),
        git_blob_sha1=hashlib.sha1(git_header + data).hexdigest(),
    )


def detect_file_type(data: bytes, name: str = "") -> str:
    if data.startswith(b"PK\x03\x04"):
        return "zip"
    if data.startswith(b"MZ"):
        return "pe"
    if data.startswith(b"\x7fELF"):
        return "elf"
    if data.startswith(b"%PDF-"):
        return "pdf"
    sample = data[:4096]
    if sample and b"\x00" not in sample:
        try:
            sample.decode("utf-8")
            return "text"
        except UnicodeDecodeError:
            pass
    return "binary"


def shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    size = len(data)
    return -sum((count / size) * math.log2(count / size) for count in Counter(data).values())


def extract_strings(data: bytes, min_length: int = 4, limit: int = 5000):
    sample = data[:MAX_STRING_SCAN]
    pattern = rb"[\x20-\x7e]{%d,}" % min_length
    return [match.group().decode("ascii", "ignore") for match in list(re.finditer(pattern, sample))[:limit]]
