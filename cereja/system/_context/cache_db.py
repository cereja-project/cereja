"""Private SQLite bootstrap for the bounded text-context cache."""

import os
import re
import shutil
import sqlite3
import stat
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional, Union

from .models import ContextCacheClearReport, ContextCacheInfo


APPLICATION_ID = 0x434A4358  # "CJCX"
SCHEMA_VERSION = 1
DEFAULT_NAMESPACE = "default"
DEFAULT_MAX_BYTES = 256 * 1024 * 1024
BUSY_TIMEOUT_MS = 500
_BATCH_LOOKUP_CHUNK_SIZE = 900

_SQLITE_HEADER = b"SQLite format 3\x00"
_SQLITE_PAGE_SIZE_OFFSET = 16
_SQLITE_WRITE_VERSION_OFFSET = 18
_SQLITE_READ_VERSION_OFFSET = 19
_SQLITE_USER_VERSION_OFFSET = 60
_SQLITE_APPLICATION_ID_OFFSET = 68
_SQLITE_IDENTITY_BYTES = 72
_PreparedPath = tuple[
    bool, tuple[int, int], tuple[int, int], dict[Path, tuple[int, int]]
]

_SCAN_TOKEN_LOCK = threading.Lock()
_LAST_SCAN_STARTED_NS = 0

_SCHEMA_DDL = {
    "metadata": """CREATE TABLE metadata (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""",
    "namespaces": """CREATE TABLE namespaces (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        last_access_ns INTEGER NOT NULL
    )""",
    "roots": """CREATE TABLE roots (
        id INTEGER PRIMARY KEY,
        canonical_path TEXT NOT NULL UNIQUE,
        last_access_ns INTEGER NOT NULL,
        scan_generation INTEGER NOT NULL DEFAULT 0,
        scan_started_ns INTEGER NOT NULL DEFAULT 0,
        scan_nonce TEXT NOT NULL DEFAULT ''
    )""",
    "namespace_roots": """CREATE TABLE namespace_roots (
        namespace_id INTEGER NOT NULL REFERENCES namespaces(id) ON DELETE CASCADE,
        root_id INTEGER NOT NULL REFERENCES roots(id) ON DELETE CASCADE,
        PRIMARY KEY (namespace_id, root_id)
    )""",
    "files": """CREATE TABLE files (
        id INTEGER PRIMARY KEY,
        canonical_path TEXT NOT NULL UNIQUE,
        device INTEGER,
        inode INTEGER,
        size_bytes INTEGER NOT NULL,
        mtime_ns INTEGER NOT NULL,
        ctime_ns INTEGER NOT NULL,
        state TEXT NOT NULL CHECK (
            state IN ('text', 'binary_file', 'invalid_utf8', 'file_too_large')
        ),
        content_sha256 TEXT,
        folded_text TEXT,
        created_ns INTEGER NOT NULL,
        validated_ns INTEGER NOT NULL,
        last_access_ns INTEGER NOT NULL
    )""",
    "root_files": """CREATE TABLE root_files (
        root_id INTEGER NOT NULL REFERENCES roots(id) ON DELETE CASCADE,
        file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
        relative_path TEXT NOT NULL,
        last_seen_scan TEXT NOT NULL,
        PRIMARY KEY (root_id, file_id)
    )""",
}

_LEGACY_SCHEMA_DDL = dict(_SCHEMA_DDL)
_LEGACY_SCHEMA_DDL["roots"] = """CREATE TABLE roots (
        id INTEGER PRIMARY KEY,
        canonical_path TEXT NOT NULL UNIQUE,
        last_access_ns INTEGER NOT NULL,
        scan_generation INTEGER NOT NULL DEFAULT 0
    )"""

_EXPECTED_AUTOINDEXES = {
    ("sqlite_autoindex_metadata_1", "metadata"),
    ("sqlite_autoindex_namespaces_1", "namespaces"),
    ("sqlite_autoindex_roots_1", "roots"),
    ("sqlite_autoindex_namespace_roots_1", "namespace_roots"),
    ("sqlite_autoindex_files_1", "files"),
    ("sqlite_autoindex_root_files_1", "root_files"),
}

_TABLE_NAMES = frozenset(
    {"metadata", "namespaces", "namespace_roots", "roots", "root_files", "files"}
)

_EXPECTED_COLUMNS = {
    "metadata": (("key", "TEXT", 0, 1), ("value", "TEXT", 1, 0)),
    "namespaces": (("id", "INTEGER", 0, 1), ("name", "TEXT", 1, 0),
                   ("last_access_ns", "INTEGER", 1, 0)),
    "roots": (("id", "INTEGER", 0, 1), ("canonical_path", "TEXT", 1, 0),
              ("last_access_ns", "INTEGER", 1, 0),
              ("scan_generation", "INTEGER", 1, 0),
              ("scan_started_ns", "INTEGER", 1, 0),
              ("scan_nonce", "TEXT", 1, 0)),
    "namespace_roots": (("namespace_id", "INTEGER", 1, 1),
                        ("root_id", "INTEGER", 1, 2)),
    "files": (("id", "INTEGER", 0, 1), ("canonical_path", "TEXT", 1, 0),
              ("device", "INTEGER", 0, 0), ("inode", "INTEGER", 0, 0),
              ("size_bytes", "INTEGER", 1, 0), ("mtime_ns", "INTEGER", 1, 0),
              ("ctime_ns", "INTEGER", 1, 0), ("state", "TEXT", 1, 0),
              ("content_sha256", "TEXT", 0, 0), ("folded_text", "TEXT", 0, 0),
              ("created_ns", "INTEGER", 1, 0), ("validated_ns", "INTEGER", 1, 0),
              ("last_access_ns", "INTEGER", 1, 0)),
    "root_files": (("root_id", "INTEGER", 1, 1), ("file_id", "INTEGER", 1, 2),
                   ("relative_path", "TEXT", 1, 0),
                   ("last_seen_scan", "TEXT", 1, 0)),
}

_EXPECTED_FOREIGN_KEYS = {
    "namespace_roots": {
        ("root_id", "roots", "id", "NO ACTION", "CASCADE", "NONE"),
        ("namespace_id", "namespaces", "id", "NO ACTION", "CASCADE", "NONE"),
    },
    "root_files": {
        ("file_id", "files", "id", "NO ACTION", "CASCADE", "NONE"),
        ("root_id", "roots", "id", "NO ACTION", "CASCADE", "NONE"),
    },
}

_EXPECTED_UNIQUE_COLUMNS = {
    "namespaces": {("name",)},
    "roots": {("canonical_path",)},
    "files": {("canonical_path",)},
}

_EXPECTED_COLUMN_DEFAULTS = {
    ("roots", "scan_generation"): "0",
    ("roots", "scan_started_ns"): "0",
    ("roots", "scan_nonce"): "''",
}


class CacheDatabaseError(RuntimeError):
    """Raised when a cache database is not safe or compatible to use."""


class CacheDatabaseUnavailable(CacheDatabaseError):
    """Raised when the cache database cannot be opened."""


class _CachePathLock:
    """Shared/exclusive advisory lock coordinated by every cache opener."""

    def __init__(self, database_path: Path):
        self.path = Path(f"{database_path}.lock")
        self._descriptor: int | None = None
        self._platform_state = None
        self.exclusive = False

    def acquire(
        self,
        exclusive: bool,
        *,
        create: bool = True,
        wait: bool = True,
    ) -> None:
        if self._descriptor is not None:
            raise CacheDatabaseError("context cache lock is already held")
        if ContextCacheDatabase._is_link(self.path):
            raise CacheDatabaseError("context cache lock file is unsafe")
        flags = os.O_RDWR | getattr(os, "O_BINARY", 0)
        if create:
            flags |= os.O_CREAT
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self.path, flags, 0o600)
        try:
            result = os.fstat(descriptor)
            if not stat.S_ISREG(result.st_mode):
                raise CacheDatabaseError(
                    "context cache lock must be a regular file"
                )
            if _uses_posix_permissions() and stat.S_IMODE(result.st_mode) & 0o077:
                raise CacheDatabaseError(
                    "context cache lock permissions are unsafe"
                )
            if (ContextCacheDatabase._is_link(self.path)
                    or ContextCacheDatabase._identity(self.path)
                    != (result.st_dev, result.st_ino)):
                raise CacheDatabaseError("context cache lock identity changed")
            self._platform_state = _acquire_descriptor_lock(
                descriptor, exclusive, wait=wait
            )
        except BaseException:
            os.close(descriptor)
            raise
        self._descriptor = descriptor
        self.exclusive = exclusive

    def change(self, exclusive: bool) -> None:
        if self._descriptor is None:
            raise CacheDatabaseError("context cache lock is not held")
        if self.exclusive == exclusive:
            return
        descriptor = self._descriptor
        _release_descriptor_lock(descriptor, self._platform_state)
        self._platform_state = None
        try:
            self._platform_state = _acquire_descriptor_lock(
                descriptor, exclusive
            )
        except BaseException:
            os.close(descriptor)
            self._descriptor = None
            raise
        self.exclusive = exclusive

    def release(self) -> None:
        if self._descriptor is None:
            return
        descriptor = self._descriptor
        self._descriptor = None
        try:
            _release_descriptor_lock(descriptor, self._platform_state)
        finally:
            self._platform_state = None
            os.close(descriptor)


@dataclass(frozen=True, slots=True)
class ScanToken:
    """Scan identity with a process-monotonic start timestamp."""

    namespace: str
    canonical_root: str
    started_ns: int
    nonce: str


@dataclass(frozen=True, slots=True)
class FileSignature:
    """Filesystem identity fields used to validate a cached file."""

    device: int | None
    inode: int | None
    size_bytes: int
    mtime_ns: int
    ctime_ns: int


@dataclass(frozen=True, slots=True)
class CachedFile:
    """Cached text state and its association-relative path."""

    canonical_path: str
    relative_path: str
    signature: FileSignature
    state: str
    folded_text: str | None
    content_sha256: str | None


@dataclass(frozen=True, slots=True)
class CacheMaintenanceReport:
    """Internal accounting for one quota-maintenance pass."""

    associations_removed: int
    roots_removed: int
    files_removed: int
    before_bytes: int
    after_bytes: int


def default_cache_path() -> Path:
    """Return the platform-specific location for Cereja's context cache."""
    if os.name == "nt":
        return Path(os.environ["LOCALAPPDATA"]) / "Cereja" / "cache" / "context.sqlite3"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "Cereja" / "context.sqlite3"
    cache_home = os.environ.get("XDG_CACHE_HOME")
    if cache_home:
        return Path(cache_home) / "cereja" / "context.sqlite3"
    return Path.home() / ".cache" / "cereja" / "context.sqlite3"


class ContextCacheDatabase:
    """Own the lifecycle and schema identity of one context-cache database.

    POSIX creation uses exclusive/no-follow flags when available and validates
    identity before and after ``sqlite3.connect()``. Windows uses the same
    checks as best-effort protection. Because stdlib SQLite reopens by path,
    neither platform can absolutely exclude a swap-and-restore during that
    interval; post-connect validation precedes configuration and schema work.
    """

    def __init__(self, path: Union[Path, str]):
        self.path = Path(path)
        self._connection: Optional[sqlite3.Connection] = None
        self._cache_lock: _CachePathLock | None = None

    @property
    def connection(self) -> sqlite3.Connection:
        """Return the open SQLite connection."""
        if self._connection is None:
            raise CacheDatabaseError("context cache database is not open")
        return self._connection

    def __enter__(self) -> "ContextCacheDatabase":
        bootstrap: _PreparedPath | None = None
        try:
            self._prepare_directory()
            if not self._database_exists():
                self._reject_orphan_sidecars()
                self._acquire_cache_lock(True)
                prepared = self._prepare_path(create=True)
                if prepared[0]:
                    bootstrap = prepared
                self._open_locked(prepared)
            else:
                prepared = self._prepare_path()
                self._read_main_header_identity(prepared[2])
                self._acquire_existing_cache_lock()
                locked_prepared = self._prepare_path()
                if locked_prepared[1:4] != prepared[1:4]:
                    raise CacheDatabaseError(
                        "context cache storage identity changed"
                    )
                self._open_locked(locked_prepared)
        except CacheDatabaseError:
            self._close_connection()
            if bootstrap is not None:
                self._cleanup_failed_bootstrap(bootstrap)
            self._release_cache_lock()
            raise
        except (OSError, sqlite3.Error) as error:
            self._close_connection()
            if bootstrap is not None:
                self._cleanup_failed_bootstrap(bootstrap)
            self._release_cache_lock()
            raise CacheDatabaseUnavailable(
                "context cache database is unavailable"
            ) from error
        return self

    def _open_locked(
        self,
        prepared: _PreparedPath,
    ) -> None:
        database_is_empty, directory_identity, file_identity, sidecars = prepared
        if database_is_empty:
            self._require_exclusive_lock()
            self._open_prepared(prepared)
            self._cache_lock.change(False)
            return

        schema_version = self._read_header_identity(
            file_identity,
            sidecars,
        )
        if schema_version != SCHEMA_VERSION:
            raise CacheDatabaseUnavailable(
                "context cache database has an unsupported schema version"
            )
        legacy_schema = self._preflight_existing_database(
            prepared,
        )
        if legacy_schema:
            self._require_exclusive_lock()
            locked_prepared = self._prepare_path()
            if locked_prepared[1:4] != prepared[1:4]:
                raise CacheDatabaseError(
                    "context cache storage identity changed"
                )
            schema_version = self._read_header_identity(
                locked_prepared[2],
                locked_prepared[3],
            )
            if schema_version != SCHEMA_VERSION:
                raise CacheDatabaseUnavailable(
                    "context cache database has an unsupported schema version"
                )
            self._preflight_existing_database(locked_prepared)
            prepared = locked_prepared
        self._open_prepared(prepared)
        if self._cache_lock.exclusive:
            self._cache_lock.change(False)

    def _acquire_cache_lock(self, exclusive: bool) -> None:
        lock = _CachePathLock(self.path)
        lock.acquire(exclusive)
        self._cache_lock = lock

    def _acquire_existing_cache_lock(self) -> None:
        """Lock existing storage, preferring exclusive access when available."""
        lock = _CachePathLock(self.path)
        try:
            lock.acquire(True, wait=False)
        except BlockingIOError:
            lock.acquire(False)
        self._cache_lock = lock

    def _cleanup_failed_bootstrap(self, prepared: _PreparedPath) -> None:
        """Remove only storage identities created by this failed bootstrap."""
        if self._cache_lock is None or not self._cache_lock.exclusive:
            return
        _, directory_identity, file_identity, sidecars = prepared
        try:
            if self._identity(self.path.parent) != directory_identity:
                return
            for sidecar, identity in sidecars.items():
                if (sidecar.exists() and not self._is_link(sidecar)
                        and self._identity(sidecar) == identity):
                    sidecar.unlink()
            if (self.path.exists() and not self._is_link(self.path)
                    and self._identity(self.path) == file_identity):
                self.path.unlink()
        except OSError:
            return

    def _require_exclusive_lock(self) -> None:
        if self._cache_lock is None:
            raise CacheDatabaseError("context cache lock is not held")
        self._cache_lock.change(True)

    def _release_cache_lock(self) -> None:
        if self._cache_lock is not None:
            self._cache_lock.release()
            self._cache_lock = None

    def _open_prepared(
        self,
        prepared: _PreparedPath,
    ) -> None:
        database_is_empty, directory_identity, file_identity, sidecars = prepared
        journal_reservation = None
        try:
            if not database_is_empty:
                journal_reservation = self._reserve_rollback_journal()
                self._validate_sidecars()
            self._connection = sqlite3.connect(
                str(self.path), timeout=BUSY_TIMEOUT_MS / 1000
            )
        finally:
            if journal_reservation is not None:
                self._release_rollback_journal_reservation(
                    journal_reservation,
                    directory_identity,
                    file_identity,
                )
        self._validate_identity(directory_identity, file_identity)
        self._configure_connection(database_is_empty)
        self._secure_new_sidecars(sidecars)
        self._verify_or_create_schema()
        self._secure_new_sidecars(sidecars)

    def _reserve_rollback_journal(self) -> tuple[int, tuple[int, int]]:
        journal = Path(f"{self.path}-journal")
        flags = os.O_CREAT | os.O_EXCL | os.O_RDWR
        flags |= getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(journal, flags, 0o400)
        try:
            result = os.fstat(descriptor)
            identity = (result.st_dev, result.st_ino)
            if _uses_posix_permissions() and hasattr(os, "fchmod"):
                os.fchmod(descriptor, 0o400)
        except BaseException:
            os.close(descriptor)
            raise
        return descriptor, identity

    def _release_rollback_journal_reservation(
        self,
        reservation: tuple[int, tuple[int, int]],
        directory_identity: tuple[int, int],
        file_identity: tuple[int, int],
    ) -> None:
        descriptor, identity = reservation
        os.close(descriptor)
        journal = Path(f"{self.path}-journal")
        self._validate_identity(directory_identity, file_identity)
        if (self._is_link(journal) or not journal.is_file()
                or self._identity(journal) != identity
                or journal.stat(follow_symlinks=False).st_size != 0):
            raise CacheDatabaseUnavailable(
                "context cache rollback journal changed during open"
            )
        if _uses_posix_permissions() or os.name == "nt":
            journal.chmod(0o600)
        journal.unlink()

    def _read_header_identity(
        self,
        file_identity: tuple[int, int],
        sidecars: dict[Path, tuple[int, int]],
    ) -> int:
        """Return a recognized schema version without opening SQLite."""
        application_id, schema_version, _ = (
            self._read_main_header_identity(file_identity)
        )
        if sidecars:
            raise CacheDatabaseUnavailable(
                "context cache has existing SQLite sidecars"
            )
        self._validate_header_values(application_id, schema_version)
        return schema_version

    def _read_main_header_identity(
        self,
        file_identity: tuple[int, int],
    ) -> tuple[int, int, int]:
        """Read identity and WAL-mode metadata from the main database header."""
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self.path, flags)
        try:
            result = os.fstat(descriptor)
            if (result.st_dev, result.st_ino) != file_identity:
                raise CacheDatabaseError(
                    "context cache database identity changed"
                )
            header = os.read(descriptor, _SQLITE_IDENTITY_BYTES)
        finally:
            os.close(descriptor)
        self._validate_secure_file(self.path)
        if (len(header) < _SQLITE_IDENTITY_BYTES
                or header[:len(_SQLITE_HEADER)] != _SQLITE_HEADER):
            raise CacheDatabaseUnavailable(
                "context cache database identity is not recognized"
            )
        application_id, schema_version = _database_header_identity(header)
        self._validate_header_values(application_id, schema_version)
        page_size = _database_page_size(header)
        if (header[_SQLITE_WRITE_VERSION_OFFSET] != 2
                or header[_SQLITE_READ_VERSION_OFFSET] != 2):
            raise CacheDatabaseUnavailable(
                "context cache database is not in WAL mode"
            )
        return application_id, schema_version, page_size

    def _preflight_existing_database(
        self,
        prepared: _PreparedPath,
    ) -> bool:
        """Validate an existing cache on a private copy before opening it RW."""
        sources = (self.path,)
        before = {
            source: _stable_file_identity(source)
            for source in sources
        }
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                snapshot_path = Path(temporary_directory) / self.path.name
                shutil.copyfile(self.path, snapshot_path)
                if _uses_posix_permissions():
                    snapshot_path.chmod(0o600)
                self._validate_preflight_sources(
                    prepared,
                    before,
                )

                snapshot = type(self)(snapshot_path)
                uri = f"{snapshot_path.absolute().as_uri()}?mode=ro"
                try:
                    snapshot._connection = sqlite3.connect(
                        uri,
                        uri=True,
                        timeout=BUSY_TIMEOUT_MS / 1000,
                    )
                    snapshot.connection.execute("PRAGMA query_only = ON")
                    snapshot.connection.execute(
                        f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}"
                    )
                    if tuple(snapshot.connection.execute("PRAGMA integrity_check")) != (
                        ("ok",),
                    ):
                        raise CacheDatabaseUnavailable(
                            "recognized context cache database is corrupt"
                        )
                    if tuple(snapshot.connection.execute(
                        "PRAGMA foreign_key_check"
                    )):
                        raise CacheDatabaseUnavailable(
                            "recognized context cache database has invalid references"
                        )
                    legacy_schema = snapshot._validate_existing_schema()
                finally:
                    snapshot._close_connection()
                self._validate_preflight_sources(
                    prepared,
                    before,
                )
        except CacheDatabaseError:
            raise
        except (OSError, sqlite3.Error) as error:
            raise CacheDatabaseUnavailable(
                "context cache database is unavailable"
            ) from error
        return legacy_schema

    def _validate_preflight_sources(
        self,
        prepared: _PreparedPath,
        expected: dict[Path, tuple[int, int, int, int, int]],
    ) -> None:
        _, directory_identity, file_identity, sidecars = prepared
        self._validate_identity(directory_identity, file_identity)
        self._validate_sidecars()
        if sidecars:
            raise CacheDatabaseUnavailable(
                "context cache has existing SQLite sidecars"
            )
        self._reject_existing_rollback_journal()
        if self._existing_sidecars() != sidecars:
            raise CacheDatabaseUnavailable(
                "context cache sidecar set changed while being validated"
            )
        actual = {
            source: _stable_file_identity(source)
            for source in expected
        }
        if actual != expected:
            raise CacheDatabaseUnavailable(
                "context cache changed while being validated"
            )

    @staticmethod
    def _validate_header_values(application_id: int, schema_version: int) -> None:
        if application_id != APPLICATION_ID:
            raise CacheDatabaseUnavailable(
                "context cache database has an unknown application id"
            )
        if schema_version > SCHEMA_VERSION:
            raise CacheDatabaseUnavailable(
                "context cache database has a newer schema version"
            )
        if schema_version != SCHEMA_VERSION:
            raise CacheDatabaseUnavailable(
                "context cache database has an unsupported schema version"
            )

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._close_connection()
        self._release_cache_lock()

    def table_names(self) -> set[str]:
        """Return the set of application tables in the open database."""
        return {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
            if not row[0].startswith("sqlite_")
        }

    @classmethod
    def read_info(cls, path: Union[Path, str]) -> ContextCacheInfo:
        """Read default-namespace statistics through a read-only connection."""
        database = cls(path)
        directory_identity, file_identity, sidecars = (
            database._prepare_read_only_path()
        )
        database._read_main_header_identity(file_identity)
        try:
            database._acquire_existing_cache_lock()
            directory_identity, file_identity, sidecars = (
                database._prepare_read_only_path()
            )
            schema_version = database._read_header_identity(
                file_identity,
                sidecars,
            )
            if schema_version != SCHEMA_VERSION:
                raise CacheDatabaseUnavailable(
                    "context cache database has an unsupported schema version"
                )
            database._preflight_existing_database(
                (False, directory_identity, file_identity, sidecars),
            )
            database_bytes, wal_bytes, shm_bytes = database._storage_sizes()
            return database._read_info_snapshot(
                directory_identity,
                file_identity,
                database_bytes,
                wal_bytes,
                shm_bytes,
            )
        except CacheDatabaseError:
            raise
        except (OSError, sqlite3.Error) as error:
            raise CacheDatabaseUnavailable(
                "context cache database is unavailable"
            ) from error
        finally:
            database._close_connection()
            database._release_cache_lock()

    def _read_info_snapshot(
        self,
        directory_identity: tuple[int, int],
        file_identity: tuple[int, int],
        database_bytes: int,
        wal_bytes: int,
        shm_bytes: int,
    ) -> ContextCacheInfo:
        snapshot_sources = (self.path,)
        before = {
            source: _stable_file_identity(source)
            for source in snapshot_sources
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            snapshot_path = Path(temporary_directory) / self.path.name
            shutil.copyfile(self.path, snapshot_path)
            if _uses_posix_permissions():
                snapshot_path.chmod(0o600)
            self._validate_identity(directory_identity, file_identity)
            self._validate_sidecars()
            if self._existing_sidecars():
                raise CacheDatabaseUnavailable(
                    "context cache has existing SQLite sidecars"
                )
            after = {
                source: _stable_file_identity(source)
                for source in snapshot_sources
            }
            if after != before:
                raise CacheDatabaseUnavailable(
                    "context cache changed while reading metadata"
                )
            snapshot = type(self)(snapshot_path)
            uri = f"{snapshot_path.absolute().as_uri()}?mode=ro"
            try:
                snapshot._connection = sqlite3.connect(
                    uri, uri=True, timeout=BUSY_TIMEOUT_MS / 1000
                )
                snapshot.connection.execute("PRAGMA query_only = ON")
                info = snapshot._query_info(
                    database_bytes, wal_bytes, shm_bytes
                )
            finally:
                snapshot._close_connection()
            self._validate_sidecars()
            if self._existing_sidecars():
                raise CacheDatabaseUnavailable(
                    "context cache has existing SQLite sidecars"
                )
        return ContextCacheInfo(
            path=self.path.absolute().as_posix(),
            schema_version=info.schema_version,
            namespace=info.namespace,
            database_bytes=database_bytes,
            wal_bytes=wal_bytes,
            shm_bytes=shm_bytes,
            roots=info.roots,
            files=info.files,
            text_files=info.text_files,
            skipped_files=info.skipped_files,
            last_access_ns=info.last_access_ns,
        )

    def _prepare_read_only_path(
        self,
    ) -> tuple[
        tuple[int, int], tuple[int, int], dict[Path, tuple[int, int]]
    ]:
        if self._is_link(self.path):
            raise CacheDatabaseError(
                "context cache database must not be a symlink"
            )
        try:
            mode = self.path.lstat().st_mode
        except FileNotFoundError as error:
            raise CacheDatabaseUnavailable(
                "context cache database is unavailable"
            ) from error
        if not stat.S_ISREG(mode):
            raise CacheDatabaseError(
                "context cache database must be a regular file"
            )
        directory = self.path.parent
        if self._is_link(directory) or not directory.is_dir():
            raise CacheDatabaseError("context cache directory is unsafe")
        directory_identity = self._identity(directory)
        file_identity = self._identity(self.path)
        self._validate_secure_file(self.path)
        self._validate_sidecars()
        self._reject_existing_rollback_journal()
        return directory_identity, file_identity, self._existing_sidecars()

    def _query_info(
        self,
        database_bytes: int,
        wal_bytes: int,
        shm_bytes: int,
    ) -> ContextCacheInfo:
        application_id = self.connection.execute(
            "PRAGMA application_id"
        ).fetchone()[0]
        schema_version = self.connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]
        if application_id != APPLICATION_ID:
            raise CacheDatabaseUnavailable(
                "context cache database has an unknown application id"
            )
        if schema_version != SCHEMA_VERSION:
            raise CacheDatabaseUnavailable(
                "context cache database has an unsupported schema version"
            )
        if self.table_names() != _TABLE_NAMES:
            raise CacheDatabaseError(
                "context cache database schema is incomplete"
            )
        namespace = self.connection.execute(
            "SELECT id, last_access_ns FROM namespaces WHERE name = ?",
            (DEFAULT_NAMESPACE,),
        ).fetchone()
        if namespace is None:
            raise CacheDatabaseError(
                "context cache database default namespace is missing"
            )
        namespace_id, last_access_ns = namespace
        roots = self.connection.execute(
            "SELECT COUNT(*) FROM namespace_roots WHERE namespace_id = ?",
            (namespace_id,),
        ).fetchone()[0]
        files, text_files, skipped_files = self.connection.execute(
            """SELECT COUNT(DISTINCT f.id),
                      COUNT(DISTINCT CASE WHEN f.state = 'text' THEN f.id END),
                      COUNT(DISTINCT CASE WHEN f.state <> 'text' THEN f.id END)
               FROM namespace_roots AS nr
               JOIN root_files AS rf ON rf.root_id = nr.root_id
               JOIN files AS f ON f.id = rf.file_id
               WHERE nr.namespace_id = ?""",
            (namespace_id,),
        ).fetchone()
        return ContextCacheInfo(
            path=self.path.absolute().as_posix(),
            schema_version=int(schema_version),
            namespace=DEFAULT_NAMESPACE,
            database_bytes=database_bytes,
            wal_bytes=wal_bytes,
            shm_bytes=shm_bytes,
            roots=int(roots),
            files=int(files),
            text_files=int(text_files),
            skipped_files=int(skipped_files),
            last_access_ns=int(last_access_ns),
        )

    def clear_default_namespace(self) -> ContextCacheClearReport:
        """Clear default associations and rows made orphaned by that clear."""
        connection = self.connection
        before_bytes = 0
        committed = False
        primary_error = None
        secondary_errors = []
        post_commit_errors = []
        associations_removed = 0
        roots_removed = 0
        files_removed = 0
        try:
            connection.execute("PRAGMA locking_mode = EXCLUSIVE")
            connection.execute("BEGIN EXCLUSIVE")
            before_bytes = self.aggregate_size_bytes()
            namespace = connection.execute(
                "SELECT id FROM namespaces WHERE name = ?",
                (DEFAULT_NAMESPACE,),
            ).fetchone()
            if namespace is not None:
                namespace_id = namespace[0]
                associations_removed = connection.execute(
                    "SELECT COUNT(*) FROM namespace_roots WHERE namespace_id = ?",
                    (namespace_id,),
                ).fetchone()[0]
                connection.execute(
                    "DELETE FROM namespace_roots WHERE namespace_id = ?",
                    (namespace_id,),
                )
            roots_removed = connection.execute(
                """DELETE FROM roots
                   WHERE NOT EXISTS (
                       SELECT 1 FROM namespace_roots
                       WHERE namespace_roots.root_id = roots.id
                   )"""
            ).rowcount
            files_removed = connection.execute(
                """DELETE FROM files
                   WHERE NOT EXISTS (
                       SELECT 1 FROM root_files
                       WHERE root_files.file_id = files.id
                   )"""
            ).rowcount
            connection.commit()
            committed = True
            try:
                self._maintain_after_clear()
            except Exception as error:
                post_commit_errors.append(error)
        except BaseException as error:
            primary_error = error
            if connection.in_transaction:
                try:
                    connection.rollback()
                except BaseException as rollback_error:
                    secondary_errors.append(rollback_error)
            raise
        finally:
            try:
                self._restore_normal_locking()
            except Exception as error:
                if committed:
                    post_commit_errors.append(error)
                else:
                    secondary_errors.append(error)
            if secondary_errors:
                cleanup_error = secondary_errors[0]
                if len(secondary_errors) > 1:
                    cleanup_error = BaseExceptionGroup(
                        "context cache clear cleanup failed",
                        secondary_errors,
                    )
                if primary_error is not None:
                    raise primary_error from cleanup_error
                raise cleanup_error
        after_bytes = self._measure_after_clear(post_commit_errors)
        self._raise_post_commit_clear_failure(post_commit_errors)
        return ContextCacheClearReport(
            associations_removed=int(associations_removed),
            roots_removed=int(roots_removed),
            files_removed=int(files_removed),
            before_bytes=before_bytes,
            after_bytes=after_bytes,
        )

    def _measure_after_clear(self, post_commit_errors: list[Exception]) -> int:
        try:
            return self.aggregate_size_bytes()
        except Exception as error:
            post_commit_errors.append(error)
            return 0

    @staticmethod
    def _raise_post_commit_clear_failure(errors: list[Exception]) -> None:
        if not errors:
            return
        post_commit_error = errors[0]
        if len(errors) > 1:
            post_commit_error = ExceptionGroup(
                "context cache clear post-commit failures",
                errors,
            )
        raise CacheDatabaseUnavailable(
            "context cache clear was committed but post-commit maintenance failed"
        ) from post_commit_error

    def _maintain_after_clear(self) -> None:
        """Reclaim physical storage after the logical clear committed."""
        checkpoint = self._checkpoint_wal()
        if checkpoint[0] != 0:
            raise CacheDatabaseUnavailable(
                "context cache checkpoint remained busy after clear"
            )
        if self._freelist_pages():
            self._run_bounded_vacuum()
            checkpoint = self._checkpoint_wal()
            if checkpoint[0] != 0:
                raise CacheDatabaseUnavailable(
                    "context cache checkpoint remained busy after vacuum"
                )

    def begin_scan(self, namespace: str, canonical_root: str) -> ScanToken:
        """Return an immutable in-memory scan token without writing SQLite."""
        return ScanToken(
            namespace=namespace,
            canonical_root=canonical_root,
            started_ns=_next_scan_started_ns(),
            nonce=str(uuid.uuid4()),
        )

    def begin_scans_if_admitted(
        self,
        namespace: str,
        canonical_roots: Iterable[str],
        max_bytes: int,
    ) -> dict[str, ScanToken] | None:
        """Prepare scan tokens after a read-only physical-capacity preflight."""
        if max_bytes < 0:
            raise ValueError("max_bytes must not be negative")
        roots = tuple(dict.fromkeys(canonical_roots))
        if not roots:
            return {}
        if (self.aggregate_size_bytes() >= max_bytes
                or self._projected_aggregate_size() > max_bytes):
            return None

        return {root: self.begin_scan(namespace, root) for root in roots}

    def roots_requiring_scan(
        self,
        namespace: str,
        roots_with_inventory: Iterable[tuple[str, bool]],
    ) -> tuple[str, ...]:
        """Return roots whose current inventory requires cache publication."""
        required = []
        for canonical_root, has_inventory in roots_with_inventory:
            if has_inventory:
                required.append(canonical_root)
                continue
            row = self.connection.execute(
                """SELECT EXISTS (
                           SELECT 1 FROM namespace_roots AS nr
                           JOIN namespaces AS n ON n.id = nr.namespace_id
                           JOIN roots AS r ON r.id = nr.root_id
                           WHERE n.name = ? AND r.canonical_path = ?
                       ), EXISTS (
                           SELECT 1 FROM root_files AS rf
                           JOIN roots AS r ON r.id = rf.root_id
                           WHERE r.canonical_path = ?
                       )""",
                (namespace, canonical_root, canonical_root),
            ).fetchone()
            is_published, has_cached_files = map(bool, row)
            if not is_published or has_cached_files:
                required.append(canonical_root)
        return tuple(required)

    def commit_scan(
        self,
        scan_token: ScanToken,
        files: Iterable[CachedFile],
        max_bytes: int | None = None,
    ) -> tuple[CachedFile, ...] | None:
        """Atomically publish the deterministic prefix admitted by quota."""
        if max_bytes is not None and max_bytes < 0:
            raise ValueError("max_bytes must not be negative")
        if not isinstance(scan_token, ScanToken):
            raise CacheDatabaseError("context cache scan token is invalid")
        namespace = scan_token.namespace
        canonical_root = scan_token.canonical_root

        cached_files = tuple(files)
        connection = self.connection
        timestamp = time.time_ns()
        admitted = []
        if (max_bytes is not None
                and (self.aggregate_size_bytes() >= max_bytes
                     or self._projected_aggregate_size() > max_bytes)):
            return None

        primary_error = None
        secondary_errors = []
        try:
            if max_bytes is not None:
                connection.execute("PRAGMA locking_mode = EXCLUSIVE")
                connection.execute("PRAGMA cache_spill = OFF")
            try:
                connection.execute(
                    "BEGIN EXCLUSIVE" if max_bytes is not None else "BEGIN IMMEDIATE"
                )
            except sqlite3.OperationalError as error:
                if "locked" in str(error).casefold():
                    return None
                raise
            if (max_bytes is not None
                    and (self.aggregate_size_bytes() >= max_bytes
                         or self._projected_aggregate_size() > max_bytes)):
                connection.rollback()
                return None
            current_root = connection.execute(
                """SELECT id, scan_started_ns, scan_nonce FROM roots
                   WHERE canonical_path = ?""",
                (canonical_root,),
            ).fetchone()
            if current_root is not None:
                published_started_ns = int(current_root[1])
                if published_started_ns >= scan_token.started_ns:
                    raise CacheDatabaseError("context cache scan token is stale")
            connection.execute(
                """INSERT INTO namespaces (name, last_access_ns)
                   VALUES (?, ?)
                   ON CONFLICT(name) DO UPDATE SET
                       last_access_ns = excluded.last_access_ns""",
                (namespace, timestamp),
            )
            namespace_id = connection.execute(
                "SELECT id FROM namespaces WHERE name = ?", (namespace,)
            ).fetchone()[0]
            connection.execute(
                """INSERT INTO roots (
                       canonical_path, last_access_ns, scan_started_ns, scan_nonce
                   ) VALUES (?, ?, 0, '')
                   ON CONFLICT(canonical_path) DO UPDATE SET
                       last_access_ns = excluded.last_access_ns""",
                (canonical_root, timestamp),
            )
            root_id = connection.execute(
                "SELECT id FROM roots WHERE canonical_path = ?",
                (canonical_root,),
            ).fetchone()[0]
            connection.execute(
                """INSERT INTO namespace_roots (namespace_id, root_id)
                   VALUES (?, ?)
                   ON CONFLICT(namespace_id, root_id) DO NOTHING""",
                (namespace_id, root_id),
            )

            for cached_file in cached_files:
                if max_bytes is not None:
                    connection.execute("SAVEPOINT cache_admission")
                signature = cached_file.signature
                connection.execute(
                    """INSERT INTO files (
                           canonical_path, device, inode, size_bytes,
                           mtime_ns, ctime_ns, state, content_sha256,
                           folded_text, created_ns, validated_ns, last_access_ns
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(canonical_path) DO UPDATE SET
                           device = excluded.device,
                           inode = excluded.inode,
                           size_bytes = excluded.size_bytes,
                           mtime_ns = excluded.mtime_ns,
                           ctime_ns = excluded.ctime_ns,
                           state = excluded.state,
                           content_sha256 = excluded.content_sha256,
                           folded_text = excluded.folded_text,
                           validated_ns = excluded.validated_ns,
                           last_access_ns = excluded.last_access_ns""",
                    (
                        cached_file.canonical_path,
                        signature.device,
                        signature.inode,
                        signature.size_bytes,
                        signature.mtime_ns,
                        signature.ctime_ns,
                        cached_file.state,
                        cached_file.content_sha256,
                        cached_file.folded_text,
                        timestamp,
                        timestamp,
                        timestamp,
                    ),
                )
                file_id = connection.execute(
                    "SELECT id FROM files WHERE canonical_path = ?",
                    (cached_file.canonical_path,),
                ).fetchone()[0]
                connection.execute(
                    """INSERT INTO root_files (
                           root_id, file_id, relative_path, last_seen_scan
                       ) VALUES (?, ?, ?, ?)
                       ON CONFLICT(root_id, file_id) DO UPDATE SET
                           relative_path = excluded.relative_path,
                           last_seen_scan = excluded.last_seen_scan""",
                    (root_id, file_id, cached_file.relative_path, scan_token.nonce),
                )
                if (max_bytes is not None
                        and self._projected_aggregate_size() > max_bytes):
                    connection.execute("ROLLBACK TO cache_admission")
                    connection.execute("RELEASE cache_admission")
                    break
                if max_bytes is not None:
                    connection.execute("RELEASE cache_admission")
                admitted.append(cached_file)

            connection.execute(
                """DELETE FROM root_files
                   WHERE root_id = ? AND last_seen_scan <> ?""",
                (root_id, scan_token.nonce),
            )
            connection.execute(
                """UPDATE roots SET
                       scan_generation = scan_generation + 1,
                       scan_started_ns = ?, scan_nonce = ?, last_access_ns = ?
                   WHERE id = ?""",
                (scan_token.started_ns, scan_token.nonce, timestamp, root_id),
            )
            if (max_bytes is not None
                    and self._projected_aggregate_size() > max_bytes):
                connection.rollback()
                return None
            connection.commit()
        except BaseException as error:
            primary_error = error
            if connection.in_transaction:
                try:
                    connection.rollback()
                except BaseException as rollback_error:
                    secondary_errors.append(rollback_error)
            raise
        finally:
            if max_bytes is not None:
                try:
                    connection.execute("PRAGMA cache_spill = ON")
                except BaseException as error:
                    secondary_errors.append(error)
                try:
                    self._restore_normal_locking()
                except BaseException as error:
                    secondary_errors.append(error)
            if secondary_errors:
                cleanup_error = secondary_errors[0]
                if len(secondary_errors) > 1:
                    cleanup_error = BaseExceptionGroup(
                        "context cache transaction cleanup failed",
                        secondary_errors,
                    )
                if primary_error is not None:
                    raise primary_error from cleanup_error
                raise cleanup_error
        return tuple(admitted)

    def _restore_normal_locking(self) -> None:
        """Restore normal locking and force release on the next file access."""
        self.connection.execute("PRAGMA locking_mode = NORMAL")
        self.connection.execute(
            "SELECT name FROM sqlite_schema ORDER BY name LIMIT 1"
        ).fetchone()

    def iter_root_files(
        self, namespace: str, canonical_root: str
    ) -> Iterator[CachedFile]:
        """Iterate cached files associated with a namespace root."""
        timestamp = time.time_ns()
        self.connection.execute(
            """UPDATE roots SET last_access_ns = ?
               WHERE canonical_path = ?
                 AND EXISTS (
                     SELECT 1 FROM namespace_roots AS nr
                     JOIN namespaces AS n ON n.id = nr.namespace_id
                     WHERE nr.root_id = roots.id AND n.name = ?
                 )""",
            (timestamp, canonical_root, namespace),
        )
        self.connection.commit()
        rows = self.connection.execute(
            """SELECT f.canonical_path, rf.relative_path,
                      f.device, f.inode, f.size_bytes, f.mtime_ns, f.ctime_ns,
                      f.state, f.folded_text, f.content_sha256
               FROM namespace_roots AS nr
               JOIN namespaces AS n ON n.id = nr.namespace_id
               JOIN roots AS r ON r.id = nr.root_id
               JOIN root_files AS rf ON rf.root_id = r.id
               JOIN files AS f ON f.id = rf.file_id
               WHERE n.name = ? AND r.canonical_path = ?
               ORDER BY rf.relative_path, f.canonical_path""",
            (namespace, canonical_root),
        ).fetchall()
        for row in rows:
            yield _cached_file_from_row(row)

    def get_cached_file(
        self,
        canonical_path: str,
        signature: FileSignature,
        max_file_bytes: int,
    ) -> CachedFile | None:
        """Return a reusable cached file with an identical signature."""
        rows = self.connection.execute(
            """SELECT f.canonical_path, rf.relative_path,
                      f.device, f.inode, f.size_bytes, f.mtime_ns, f.ctime_ns,
                      f.state, f.folded_text, f.content_sha256, f.id
               FROM files AS f
               LEFT JOIN root_files AS rf ON rf.file_id = f.id
               WHERE f.canonical_path = ?
                 AND f.device IS ?
                 AND f.inode IS ?
                 AND f.size_bytes = ?
                 AND f.mtime_ns = ?
                 AND f.ctime_ns = ?
               ORDER BY rf.root_id""",
            (
                canonical_path,
                signature.device,
                signature.inode,
                signature.size_bytes,
                signature.mtime_ns,
                signature.ctime_ns,
            ),
        ).fetchall()
        if len(rows) != 1 or rows[0][1] is None:
            return None
        row = rows[0]
        if signature.size_bytes > max_file_bytes and row[7] != "file_too_large":
            return None
        if row[7] == "file_too_large" and signature.size_bytes <= max_file_bytes:
            return None
        self.connection.execute(
            "UPDATE files SET last_access_ns = ? WHERE id = ?",
            (time.time_ns(), row[10]),
        )
        self.connection.execute(
            """UPDATE roots SET last_access_ns = ?
               WHERE id = (
                   SELECT root_id FROM root_files WHERE file_id = ?
               )""",
            (time.time_ns(), row[10]),
        )
        self.connection.commit()
        normalized = tuple(row[:10])
        return _cached_file_from_row(normalized)

    def get_cached_content(
        self,
        canonical_path: str,
        signature: FileSignature,
        max_file_bytes: int,
    ) -> CachedFile | None:
        """Return reusable content without requiring one root association."""
        row = self.connection.execute(
            """SELECT canonical_path, '', device, inode, size_bytes,
                      mtime_ns, ctime_ns, state, folded_text, content_sha256, id
               FROM files
               WHERE canonical_path = ?
                 AND device IS ?
                 AND inode IS ?
                 AND size_bytes = ?
                 AND mtime_ns = ?
                 AND ctime_ns = ?""",
            (
                canonical_path,
                signature.device,
                signature.inode,
                signature.size_bytes,
                signature.mtime_ns,
                signature.ctime_ns,
            ),
        ).fetchone()
        if row is None:
            return None
        if signature.size_bytes > max_file_bytes and row[7] != "file_too_large":
            return None
        if row[7] == "file_too_large" and signature.size_bytes <= max_file_bytes:
            return None
        return _cached_file_from_row(tuple(row[:10]))

    def get_cached_contents(
        self, canonical_paths: Iterable[str]
    ) -> dict[str, CachedFile]:
        """Return cached content for canonical paths without root associations."""
        paths = tuple(dict.fromkeys(canonical_paths))
        if not paths:
            return {}

        cached_by_path: dict[str, CachedFile] = {}
        timestamp = time.time_ns()
        updated = False
        for start in range(0, len(paths), _BATCH_LOOKUP_CHUNK_SIZE):
            chunk = paths[start:start + _BATCH_LOOKUP_CHUNK_SIZE]
            placeholders = ", ".join("?" for _ in chunk)
            rows = self.connection.execute(
                f"""SELECT canonical_path, '', device, inode, size_bytes,
                           mtime_ns, ctime_ns, state, folded_text, content_sha256
                    FROM files
                    WHERE canonical_path IN ({placeholders})""",
                chunk,
            ).fetchall()
            if not rows:
                continue
            cached_by_path.update(
                (str(row[0]), _cached_file_from_row(tuple(row)))
                for row in rows
            )
            self.connection.execute(
                f"""UPDATE files SET last_access_ns = ?
                    WHERE canonical_path IN ({placeholders})""",
                (timestamp, *chunk),
            )
            updated = True
        if updated:
            self.connection.commit()
        return {
            path: cached_by_path[path]
            for path in paths if path in cached_by_path
        }

    def aggregate_size_bytes(self) -> int:
        """Return the current byte size of the database and WAL sidecars."""
        return sum(self._storage_sizes())

    def _storage_sizes(self) -> tuple[int, int, int]:
        sizes = []
        for path in (self.path, *self._sidecar_paths()):
            try:
                sizes.append(path.stat(follow_symlinks=False).st_size)
            except FileNotFoundError:
                sizes.append(0)
        return tuple(sizes)

    def _projected_aggregate_size(self) -> int:
        """Return a conservative aggregate size for a possible write."""
        page_size = self.connection.execute("PRAGMA page_size").fetchone()[0]
        page_count = self.connection.execute("PRAGMA page_count").fetchone()[0]
        try:
            current_database = self.path.stat(follow_symlinks=False).st_size
        except FileNotFoundError:
            current_database = 0
        projected_database = max(current_database, page_size * page_count)
        write_ahead_log, shared_memory = self._sidecar_paths()
        try:
            write_ahead_log_bytes = write_ahead_log.stat(
                follow_symlinks=False
            ).st_size
        except FileNotFoundError:
            write_ahead_log_bytes = 0
        try:
            shared_memory_bytes = shared_memory.stat(
                follow_symlinks=False
            ).st_size
        except FileNotFoundError:
            shared_memory_bytes = 32 * 1024
        projected_wal = 32 + page_count * (page_size + 24)
        existing_frames = max(
            0,
            (write_ahead_log_bytes - 32) // (page_size + 24),
        )
        total_frames = existing_frames + page_count
        wal_index_blocks = max(1, (total_frames + 4_095) // 4_096)
        projected_shared_memory = 32 * 1024 * (1 + wal_index_blocks)
        return (
            projected_database
            + write_ahead_log_bytes
            + projected_wal
            + max(shared_memory_bytes, projected_shared_memory)
        )

    def enforce_quota(
        self,
        protected_root: Union[str, os.PathLike, Iterable[str]],
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> CacheMaintenanceReport:
        """Evict roots not in the protected set until quota or candidates end."""
        if max_bytes < 0:
            raise ValueError("max_bytes must not be negative")
        if isinstance(protected_root, (str, os.PathLike)):
            protected_roots = (os.fspath(protected_root),)
        else:
            protected_roots = tuple(protected_root)
        before_bytes = self.aggregate_size_bytes()
        associations_removed = 0
        roots_removed = 0
        files_removed = self._collect_orphan_files()
        vacuum_available = True
        checkpoint_busy = self._checkpoint_wal()[0] != 0
        if (not checkpoint_busy and self._freelist_pages()
                and self.aggregate_size_bytes() > max_bytes):
            self._run_bounded_vacuum()
            vacuum_available = False
            checkpoint_busy = self._checkpoint_wal()[0] != 0

        placeholders = ", ".join("?" for _ in protected_roots)
        where_clause = (
            f"WHERE canonical_path NOT IN ({placeholders})"
            if protected_roots else ""
        )
        candidates = self.connection.execute(
            f"""SELECT id FROM roots
                {where_clause}
                ORDER BY last_access_ns, id""",
            protected_roots,
        ).fetchall()
        for (root_id,) in candidates:
            if checkpoint_busy or self.aggregate_size_bytes() <= max_bytes:
                break
            connection = self.connection
            try:
                connection.execute("BEGIN IMMEDIATE")
                association_count = connection.execute(
                    "SELECT COUNT(*) FROM root_files WHERE root_id = ?",
                    (root_id,),
                ).fetchone()[0]
                root_count = connection.execute(
                    "DELETE FROM roots WHERE id = ?", (root_id,)
                ).rowcount
                file_count = connection.execute(
                    """DELETE FROM files
                       WHERE NOT EXISTS (
                           SELECT 1 FROM root_files WHERE root_files.file_id = files.id
                       )"""
                ).rowcount
                connection.commit()
            except BaseException:
                if connection.in_transaction:
                    connection.rollback()
                raise
            associations_removed += association_count
            roots_removed += root_count
            files_removed += file_count
            checkpoint_busy = self._checkpoint_wal()[0] != 0
            if (not checkpoint_busy and vacuum_available and self._freelist_pages()
                    and self.aggregate_size_bytes() > max_bytes):
                self._run_bounded_vacuum()
                vacuum_available = False
                checkpoint_busy = self._checkpoint_wal()[0] != 0

        self._checkpoint_wal()
        return CacheMaintenanceReport(
            associations_removed=associations_removed,
            roots_removed=roots_removed,
            files_removed=files_removed,
            before_bytes=before_bytes,
            after_bytes=self.aggregate_size_bytes(),
        )

    def _collect_orphan_files(self) -> int:
        connection = self.connection
        try:
            connection.execute("BEGIN IMMEDIATE")
            removed = connection.execute(
                """DELETE FROM files
                   WHERE NOT EXISTS (
                       SELECT 1 FROM root_files WHERE root_files.file_id = files.id
                   )"""
            ).rowcount
            connection.commit()
        except BaseException:
            if connection.in_transaction:
                connection.rollback()
            raise
        return removed

    def _checkpoint_wal(self) -> tuple[int, int, int]:
        """Return SQLite's busy, log-frame, and checkpointed-frame counts."""
        result = self.connection.execute(
            "PRAGMA wal_checkpoint(TRUNCATE)"
        ).fetchone()
        return int(result[0]), int(result[1]), int(result[2])

    def _run_bounded_vacuum(self) -> None:
        """Reclaim at most the per-call maintenance budget."""
        self.connection.execute("PRAGMA incremental_vacuum(128)")

    def _freelist_pages(self) -> int:
        return self.connection.execute("PRAGMA freelist_count").fetchone()[0]

    @staticmethod
    def _identity(path: Path) -> tuple[int, int]:
        result = path.stat(follow_symlinks=False)
        return result.st_dev, result.st_ino

    @staticmethod
    def _is_link(path: Path) -> bool:
        try:
            attributes = getattr(path.lstat(), "st_file_attributes", 0) or 0
        except FileNotFoundError:
            attributes = 0
        reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if os.name == "nt" and attributes & reparse_point:
            return True
        is_junction = getattr(path, "is_junction", None)
        return path.is_symlink() or (is_junction is not None and is_junction())

    def _prepare_directory(self) -> Path:
        directory = self.path.parent
        if self.path == default_cache_path():
            if os.name == "nt":
                base = Path(os.environ["LOCALAPPDATA"])
                parts = ("Cereja", "cache")
            elif sys.platform == "darwin":
                base = Path.home() / "Library" / "Caches"
                parts = ("Cereja",)
            else:
                cache_home = os.environ.get("XDG_CACHE_HOME")
                base = Path(cache_home) if cache_home else Path.home() / ".cache"
                parts = ("cereja",)
            if self._is_link(base) or not base.is_dir():
                raise CacheDatabaseError("context cache base directory is unsafe")
            current = base
            for part in parts:
                current = current / part
                if current.exists():
                    self._validate_secure_directory(current)
                else:
                    current.mkdir(mode=0o700)
                    self._validate_secure_directory(current)
            return current

        if self._is_link(directory):
            raise CacheDatabaseError("context cache directory must not be a symlink")
        if directory.exists():
            self._validate_secure_directory(directory)
        else:
            if not directory.parent.is_dir() or self._is_link(directory.parent):
                raise CacheDatabaseError("context cache directory parent must already exist")
            directory.mkdir(mode=0o700)
            self._validate_secure_directory(directory)
        return directory

    def _validate_secure_directory(self, directory: Path) -> None:
        if self._is_link(directory) or not directory.is_dir():
            raise CacheDatabaseError("context cache directory is unsafe")
        if (_uses_posix_permissions()
                and stat.S_IMODE(directory.stat().st_mode) & 0o077):
            raise CacheDatabaseError(
                "context cache directory permissions are unsafe"
            )

    def _prepare_path(
        self,
        *,
        create: bool = False,
    ) -> _PreparedPath:
        if self._is_link(self.path):
            raise CacheDatabaseError("context cache database must not be a symlink")
        try:
            mode = self.path.lstat().st_mode
        except FileNotFoundError:
            database_existed = False
        else:
            if not stat.S_ISREG(mode):
                raise CacheDatabaseError("context cache database must be a regular file")
            database_existed = True

        if not database_existed:
            self._reject_orphan_sidecars()
            if not create:
                raise CacheDatabaseUnavailable(
                    "context cache database is unavailable"
                )

        directory = self._prepare_directory()

        directory_identity = self._identity(directory)
        if not database_existed:
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
            flags |= getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(self.path, flags, 0o600)
            try:
                result = os.fstat(descriptor)
                file_identity = (result.st_dev, result.st_ino)
                if _uses_posix_permissions() and hasattr(os, "fchmod"):
                    os.fchmod(descriptor, 0o600)
            finally:
                os.close(descriptor)
            if self._identity(directory) != directory_identity:
                raise CacheDatabaseError(
                    "context cache directory identity changed"
                )
            if self._identity(self.path) != file_identity:
                raise CacheDatabaseError(
                    "context cache database identity changed"
                )
        else:
            file_identity = self._identity(self.path)
        self._validate_secure_file(self.path)
        self._validate_sidecars()
        self._reject_existing_rollback_journal()
        sidecars = self._existing_sidecars()
        database_is_empty = self.path.stat(follow_symlinks=False).st_size == 0
        if database_is_empty and sidecars:
            raise CacheDatabaseUnavailable(
                "empty context cache has existing SQLite sidecars"
            )
        if database_is_empty and database_existed:
            raise CacheDatabaseUnavailable(
                "context cache database identity is not recognized"
            )
        initialize_database = database_is_empty and not database_existed
        return initialize_database, directory_identity, file_identity, sidecars

    def _database_exists(self) -> bool:
        return self.path.exists() or self._is_link(self.path)

    def _reject_orphan_sidecars(self) -> None:
        orphan_sidecars = (
            *self._sidecar_paths(),
            Path(f"{self.path}-journal"),
        )
        if any(
            sidecar.exists() or self._is_link(sidecar)
            for sidecar in orphan_sidecars
        ):
            raise CacheDatabaseUnavailable(
                "context cache sidecar exists without a database"
            )

    def _validate_identity(
        self, directory_identity: tuple[int, int], file_identity: tuple[int, int]
    ) -> None:
        if self._is_link(self.path) or self._is_link(self.path.parent):
            raise CacheDatabaseError("context cache path identity changed")
        if self._identity(self.path.parent) != directory_identity:
            raise CacheDatabaseError("context cache directory identity changed")
        if self._identity(self.path) != file_identity:
            raise CacheDatabaseError("context cache database identity changed")

    def _validate_secure_file(self, path: Path) -> None:
        if self._is_link(path) or not path.is_file():
            raise CacheDatabaseError("context cache file is unsafe")
        if _uses_posix_permissions() and stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise CacheDatabaseError("context cache file permissions are unsafe")

    def _existing_sidecars(self) -> dict[Path, tuple[int, int]]:
        return {
            sidecar: self._identity(sidecar) for sidecar in self._sidecar_paths()
            if sidecar.exists() or self._is_link(sidecar)
        }

    def _sidecar_paths(self) -> tuple[Path, Path]:
        return Path(f"{self.path}-wal"), Path(f"{self.path}-shm")

    def _validate_sidecars(self) -> None:
        if any(
            sidecar.exists() or self._is_link(sidecar)
            for sidecar in self._sidecar_paths()
        ):
            raise CacheDatabaseUnavailable(
                "context cache has existing SQLite sidecars"
            )

    def _reject_existing_rollback_journal(self) -> None:
        journal = Path(f"{self.path}-journal")
        if journal.exists() or self._is_link(journal):
            raise CacheDatabaseUnavailable(
                "context cache has an existing rollback journal"
            )

    def _secure_new_sidecars(self, existing: dict[Path, tuple[int, int]]) -> None:
        for sidecar in self._sidecar_paths():
            present = sidecar.exists() or self._is_link(sidecar)
            if sidecar in existing:
                if not present or self._identity(sidecar) != existing[sidecar]:
                    raise CacheDatabaseError("context cache sidecar identity changed")
                self._validate_secure_file(sidecar)
            elif present:
                if _uses_posix_permissions():
                    sidecar.chmod(0o600)
                self._validate_secure_file(sidecar)
                existing[sidecar] = self._identity(sidecar)

    def _configure_connection(self, database_is_empty: bool) -> None:
        connection = self.connection
        connection.execute("PRAGMA foreign_keys = ON")
        if database_is_empty:
            connection.execute("PRAGMA auto_vacuum = INCREMENTAL")
            connection.execute("VACUUM")
            journal_mode = connection.execute(
                "PRAGMA journal_mode = WAL"
            ).fetchone()[0]
        else:
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        if journal_mode.lower() != "wal":
            raise CacheDatabaseUnavailable("context cache database cannot enable WAL mode")
        connection.execute("PRAGMA wal_autocheckpoint = 0")
        if connection.execute("PRAGMA wal_autocheckpoint").fetchone()[0] != 0:
            raise CacheDatabaseUnavailable(
                "context cache database cannot disable automatic checkpoints"
            )
        connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")

    def _verify_or_create_schema(self) -> None:
        application_id = self.connection.execute("PRAGMA application_id").fetchone()[0]
        schema_version = self.connection.execute("PRAGMA user_version").fetchone()[0]
        tables = self.table_names()
        if application_id == 0 and schema_version == 0 and not tables:
            self._create_schema()
            return
        if self._validate_existing_schema():
            self._migrate_legacy_schema()

    def _validate_existing_schema(self) -> bool:
        """Return whether a recognized existing cache needs supported migration."""
        application_id = self.connection.execute(
            "PRAGMA application_id"
        ).fetchone()[0]
        schema_version = self.connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]
        tables = self.table_names()
        if application_id != APPLICATION_ID:
            raise CacheDatabaseUnavailable(
                "context cache database has an unknown application id"
            )
        if schema_version != SCHEMA_VERSION:
            raise CacheDatabaseUnavailable(
                "context cache database has an unsupported schema version"
            )
        if self.connection.execute("PRAGMA auto_vacuum").fetchone()[0] != 2:
            raise CacheDatabaseUnavailable(
                "context cache database auto_vacuum is incompatible"
            )
        if tables != _TABLE_NAMES:
            raise CacheDatabaseUnavailable(
                "context cache database schema is incomplete"
            )
        namespace = self.connection.execute(
            "SELECT id FROM namespaces WHERE name = ?", (DEFAULT_NAMESPACE,)
        ).fetchone()
        if namespace is None:
            raise CacheDatabaseUnavailable(
                "context cache database default namespace is missing"
            )
        if self._schema_objects_match(_LEGACY_SCHEMA_DDL):
            return True
        self._validate_schema_structure()
        return False

    def _schema_objects_match(self, schema_ddl: dict[str, str]) -> bool:
        expected_objects = {
            ("table", name, name, _canonical_ddl(ddl))
            for name, ddl in schema_ddl.items()
        }
        expected_objects.update(
            ("index", name, table, None)
            for name, table in _EXPECTED_AUTOINDEXES
        )
        actual_objects = {
            (kind, name, table, None if ddl is None else _canonical_ddl(ddl))
            for kind, name, table, ddl in self.connection.execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_schema"
            )
        }
        return actual_objects == expected_objects

    def _migrate_legacy_schema(self) -> None:
        connection = self.connection
        try:
            connection.execute("BEGIN IMMEDIATE")
            if self._schema_objects_match(_LEGACY_SCHEMA_DDL):
                connection.execute(
                    "ALTER TABLE roots ADD COLUMN "
                    "scan_started_ns INTEGER NOT NULL DEFAULT 0"
                )
                connection.execute(
                    "ALTER TABLE roots ADD COLUMN "
                    "scan_nonce TEXT NOT NULL DEFAULT ''"
                )
            elif not self._schema_objects_match(_SCHEMA_DDL):
                raise CacheDatabaseUnavailable(
                    "context cache database schema changed during migration"
                )
            self._validate_schema_structure()
            connection.commit()
        except BaseException:
            connection.rollback()
            raise

    def _validate_schema_structure(self) -> None:
        if not self._schema_objects_match(_SCHEMA_DDL):
            raise CacheDatabaseUnavailable(
                "context cache database schema objects differ"
            )
        actual_ddl = dict(self.connection.execute(
            "SELECT name, sql FROM sqlite_schema WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%'"
        ))
        expected_ddl = {
            name: _canonical_ddl(ddl) for name, ddl in _SCHEMA_DDL.items()
        }
        if {name: _canonical_ddl(ddl) for name, ddl in actual_ddl.items()} != expected_ddl:
            raise CacheDatabaseUnavailable(
                "context cache database schema DDL differs"
            )
        for table, expected in _EXPECTED_COLUMNS.items():
            actual = tuple(
                (row[1], row[2].upper(), row[3], row[5])
                for row in self.connection.execute(f'PRAGMA table_info("{table}")')
            )
            if actual != expected:
                raise CacheDatabaseUnavailable(
                    f"context cache database schema differs: {table}"
                )
        for (table, column), expected in _EXPECTED_COLUMN_DEFAULTS.items():
            defaults = {
                row[1]: row[4]
                for row in self.connection.execute(f'PRAGMA table_info("{table}")')
            }
            if defaults.get(column) != expected:
                raise CacheDatabaseUnavailable(
                    f"context cache database schema differs: {table}.{column}"
                )
        for table, expected in _EXPECTED_FOREIGN_KEYS.items():
            actual = {
                (row[3], row[2], row[4], row[5].upper(), row[6].upper(), row[7].upper())
                for row in self.connection.execute(f'PRAGMA foreign_key_list("{table}")')
            }
            if actual != expected:
                raise CacheDatabaseUnavailable(
                    f"context cache database schema differs: {table}"
                )
        for table, expected in _EXPECTED_UNIQUE_COLUMNS.items():
            actual = set()
            for index in self.connection.execute(f'PRAGMA index_list("{table}")'):
                if index[2]:
                    actual.add(tuple(
                        row[2] for row in self.connection.execute(
                            f'PRAGMA index_info("{index[1]}")'
                        )
                    ))
            if actual != expected:
                raise CacheDatabaseUnavailable(
                    f"context cache database schema differs: {table}"
                )
        files_sql = self.connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'files'"
        ).fetchone()[0]
        state_check = re.search(
            r"CHECK\s*\(\s*state\s+IN\s*\(([^)]*)\)\s*\)", files_sql, re.IGNORECASE
        )
        states = () if state_check is None else tuple(
            item.strip().strip("'") for item in state_check.group(1).split(",")
        )
        if states != ("text", "binary_file", "invalid_utf8", "file_too_large"):
            raise CacheDatabaseUnavailable(
                "context cache database schema differs: files state"
            )

    def _create_schema(self) -> None:
        timestamp = time.time_ns()
        schema_ddl = ";\n".join(_SCHEMA_DDL.values())
        self.connection.executescript(
            f"""
                BEGIN;
                PRAGMA application_id = {APPLICATION_ID};
                PRAGMA user_version = {SCHEMA_VERSION};
                {schema_ddl};
                INSERT INTO namespaces (name, last_access_ns)
                    VALUES ('{DEFAULT_NAMESPACE}', {timestamp});
                COMMIT;
            """
        )
        checkpoint = self._checkpoint_wal()
        if checkpoint[0] != 0:
            raise CacheDatabaseUnavailable(
                "context cache identity could not be published"
            )

    def _close_connection(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None


def _uses_posix_permissions() -> bool:
    return os.name != "nt"


def _acquire_descriptor_lock(
    descriptor: int,
    exclusive: bool,
    *,
    wait: bool = True,
):
    deadline = time.monotonic() + BUSY_TIMEOUT_MS / 1000
    while True:
        try:
            if os.name == "nt":
                return _acquire_windows_descriptor_lock(
                    descriptor, exclusive
                )
            import fcntl
            operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            fcntl.flock(descriptor, operation | fcntl.LOCK_NB)
            return None
        except (BlockingIOError, PermissionError):
            if not wait:
                raise
            if time.monotonic() >= deadline:
                raise CacheDatabaseUnavailable(
                    "context cache database is locked"
                ) from None
            time.sleep(0.01)


def _release_descriptor_lock(descriptor: int, platform_state) -> None:
    if os.name == "nt":
        _release_windows_descriptor_lock(descriptor, platform_state)
        return
    import fcntl
    fcntl.flock(descriptor, fcntl.LOCK_UN)


def _acquire_windows_descriptor_lock(descriptor: int, exclusive: bool):
    import ctypes
    import msvcrt
    from ctypes import wintypes

    unsigned_pointer = (
        ctypes.c_ulonglong
        if ctypes.sizeof(ctypes.c_void_p) == 8
        else ctypes.c_ulong
    )

    class Overlapped(ctypes.Structure):
        _fields_ = [
            ("Internal", unsigned_pointer),
            ("InternalHigh", unsigned_pointer),
            ("Offset", wintypes.DWORD),
            ("OffsetHigh", wintypes.DWORD),
            ("hEvent", wintypes.HANDLE),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    operation = kernel32.LockFileEx
    operation.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(Overlapped),
    ]
    operation.restype = wintypes.BOOL
    flags = 0x00000001 | (0x00000002 if exclusive else 0)
    overlapped = Overlapped()
    handle = msvcrt.get_osfhandle(descriptor)
    if not operation(handle, flags, 0, 1, 0, ctypes.byref(overlapped)):
        error = ctypes.get_last_error()
        if error in (32, 33):
            raise BlockingIOError(error, "context cache database is locked")
        raise ctypes.WinError(error)
    return overlapped


def _release_windows_descriptor_lock(descriptor: int, overlapped) -> None:
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    operation = kernel32.UnlockFileEx
    operation.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(type(overlapped)),
    ]
    operation.restype = wintypes.BOOL
    handle = msvcrt.get_osfhandle(descriptor)
    if not operation(handle, 0, 1, 0, ctypes.byref(overlapped)):
        raise ctypes.WinError(ctypes.get_last_error())


def _database_header_identity(header: bytes) -> tuple[int, int]:
    if (len(header) < _SQLITE_IDENTITY_BYTES
            or header[:len(_SQLITE_HEADER)] != _SQLITE_HEADER):
        raise CacheDatabaseUnavailable(
            "context cache database identity is not recognized"
        )
    schema_version = int.from_bytes(
        header[_SQLITE_USER_VERSION_OFFSET:_SQLITE_USER_VERSION_OFFSET + 4],
        "big",
    )
    application_id = int.from_bytes(
        header[
            _SQLITE_APPLICATION_ID_OFFSET:_SQLITE_APPLICATION_ID_OFFSET + 4
        ],
        "big",
    )
    return application_id, schema_version


def _database_page_size(header: bytes) -> int:
    encoded = int.from_bytes(
        header[_SQLITE_PAGE_SIZE_OFFSET:_SQLITE_PAGE_SIZE_OFFSET + 2],
        "big",
    )
    page_size = 65_536 if encoded == 1 else encoded
    if (page_size < 512 or page_size > 65_536
            or page_size & (page_size - 1)):
        raise CacheDatabaseUnavailable(
            "context cache database page size is invalid"
        )
    return page_size


def _stable_file_identity(path: Path) -> tuple[int, int, int, int, int]:
    result = path.stat(follow_symlinks=False)
    return (
        result.st_dev,
        result.st_ino,
        result.st_size,
        result.st_mtime_ns,
        result.st_ctime_ns,
    )


def _next_scan_started_ns() -> int:
    """Return process-monotonic wall time for deterministic local ordering."""
    global _LAST_SCAN_STARTED_NS
    with _SCAN_TOKEN_LOCK:
        _LAST_SCAN_STARTED_NS = max(time.time_ns(), _LAST_SCAN_STARTED_NS + 1)
        return _LAST_SCAN_STARTED_NS


def _canonical_ddl(ddl: str) -> str:
    return re.sub(r"\s+", "", ddl).rstrip(";").casefold()


def _cached_file_from_row(row: tuple[object, ...]) -> CachedFile:
    return CachedFile(
        canonical_path=str(row[0]),
        relative_path=str(row[1]),
        signature=FileSignature(
            device=row[2],
            inode=row[3],
            size_bytes=int(row[4]),
            mtime_ns=int(row[5]),
            ctime_ns=int(row[6]),
        ),
        state=str(row[7]),
        folded_text=None if row[8] is None else str(row[8]),
        content_sha256=None if row[9] is None else str(row[9]),
    )
