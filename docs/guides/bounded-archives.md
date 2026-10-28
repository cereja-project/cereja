# Bounded archive API

Import opt-in operations from `cereja.hashtools.archive`. They use Python 3.11+
and the standard library. Existing compression APIs and their persisted formats
remain unchanged; this API does not silently impose limits on legacy callers.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from cereja.hashtools.archive import file_archive

with TemporaryDirectory() as directory:
    root = Path(directory).resolve()
    source = root / 'message.txt'
    source.write_text('example', encoding='utf-8')
    file_archive(source, root / 'message.cjz')
    file_archive(root / 'message.cjz', root / 'restored.txt', extract=True)
    assert (root / 'restored.txt').read_text(encoding='utf-8') == 'example'
```

`file_archive(source, destination, extract=False, limits=ArchiveLimits(),
committing=None)` uses the existing zlib CJZ encoder. Bounded extraction accepts
only unencrypted zlib-marked file archives (`0x10`). It rejects unsupported
strategies/encryption explicitly instead of using an unbounded legacy decoder.
Input is limited before compression; output expansion is limited during decoding.
The existing exclusive hard-link publisher stages bytes beside the target, flushes
and fsyncs before publication and refuses existing targets, including races.
Filesystems without the necessary hard-link operation fail closed.

`create_directory_archive(source, destination, limits=..., committing=None)`
scans only the explicit source, bounds entries, paths and source bytes, refuses
links/reparse points, hard-linked source files and special files, and writes a
stream to owned staging. The destination must be outside the source tree.
Source changes detected during reading fail instead of yielding a partial success.
This is not an atomic snapshot of a concurrently modified source.

The bounded writer uses **CJZD version 3**, an opt-in format extending the
version-2 stream with explicit directory records, including empty directories.
Version 3 starts with `CJZD` plus byte `0x03`. Records use byte `0x01` for files,
byte `0x02` for directories and byte `0x00` for end. File records retain the v2
big-endian path length, UTF-8 relative path, declared expanded size, zlib marker
and sized compressed chunks terminated by a zero chunk. Directory records have
only the path length/path. End-of-archive must be EOF. Old readers are not claimed
to accept version 3. The bounded reader accepts v2 zlib streams and v3; legacy,
password-protected and other strategy archives are explicitly unsupported here.
The old APIs remain available for their existing formats and behavior.

`extract_directory_archive(source, destination, limits=..., committing=None)`
validates every record during decoding. It rejects absolute/parent/empty path
segments, Windows drives/UNC/alternate streams, reserved device names, backslashes,
control characters, trailing dots/spaces and names illegal on Windows. NFC/casefold
collisions, duplicates, parent spelling collisions and file/directory conflicts
are refused on every platform. No archive-controlled links or special records are
accepted. Declared lengths never bypass actual expanded-byte accounting.

Default limits: 16 MiB encoded input/output archive, 16 MiB per expanded member,
64 MiB aggregate expanded bytes, 1,024 members, depth 16, 1,024 UTF-8 bytes per
member path. They are conservative candidate bounds, not calibrated optima or RSS
limits. Source and staging paths must have ordinary existing directory ancestors.
Extraction uses a fresh owned sibling staging directory, validates the complete
archive and flushes extracted files before publishing the directory.

Exclusive directory publication currently uses Windows `rename`, which refuses
an existing target. **Directory extraction is unsupported on POSIX** because the
stdlib `rename` primitive can replace an existing empty directory. The API refuses
that operation rather than emulating atomic publication with a visible copy/merge.
File operations and directory compression are available on supported Python hosts;
platform CI and human acceptance are separate evidence. There is no replacement,
backup/rollback or directory-merge policy in this API.

Operations return `ArchiveResult(destination, members, expanded_bytes)` only after
publication and owned staging cleanup. A `committing` callback, when supplied,
runs at the actual publication boundary. It is an observation hook and does not
authorize overwrite or cancellation. Failure during publication/cleanup can leave
an output; inspect the exact destination. Files are fsynced, but parent-directory
crash durability is not claimed. Source/destination ancestors must be trusted and
stable: preflight checks do not eliminate hostile concurrent ancestor replacement.
There is no total CPU, I/O deadline or whole-process-memory guarantee.
