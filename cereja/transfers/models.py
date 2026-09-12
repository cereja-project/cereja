from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TransferProgress:
    bytes_transferred: int
    total_bytes: int | None


@dataclass(frozen=True, slots=True)
class DownloadResult:
    path: Path
    bytes_transferred: int
    total_bytes: int | None
    status_code: int
