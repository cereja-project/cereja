"""Safe archive helpers for static analysis."""
import io
import zipfile
from pathlib import PurePosixPath

MAX_MEMBERS = 1000
MAX_MEMBER_SIZE = 32 * 1024 * 1024
MAX_EXPANDED_SIZE = 128 * 1024 * 1024


class UnsafeArchiveError(ValueError):
    pass


def read_zip_members(data: bytes):
    result = []
    total = 0
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise UnsafeArchiveError("archive member limit exceeded")
        for info in infos:
            if info.is_dir():
                continue
            path = PurePosixPath(info.filename.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts:
                raise UnsafeArchiveError("unsafe archive member path")
            if info.file_size > MAX_MEMBER_SIZE:
                raise UnsafeArchiveError("archive member size limit exceeded")
            total += info.file_size
            if total > MAX_EXPANDED_SIZE:
                raise UnsafeArchiveError("archive expanded-size limit exceeded")
            result.append((str(path), archive.read(info)))
    return result
