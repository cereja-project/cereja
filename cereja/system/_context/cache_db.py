"""Private SQLite bootstrap for the bounded text-context cache."""

import os
import re
import sqlite3
import stat
import sys
import time
from pathlib import Path
from typing import Optional, Union


APPLICATION_ID = 0x434A4358  # "CJCX"
SCHEMA_VERSION = 1
DEFAULT_NAMESPACE = "default"
DEFAULT_MAX_BYTES = 256 * 1024 * 1024
BUSY_TIMEOUT_MS = 500

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
        last_access_ns INTEGER NOT NULL
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
              ("last_access_ns", "INTEGER", 1, 0)),
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


class CacheDatabaseError(RuntimeError):
    """Raised when a cache database is not safe or compatible to use."""


class CacheDatabaseUnavailable(CacheDatabaseError):
    """Raised when the cache database cannot be opened."""


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

    @property
    def connection(self) -> sqlite3.Connection:
        """Return the open SQLite connection."""
        if self._connection is None:
            raise CacheDatabaseError("context cache database is not open")
        return self._connection

    def __enter__(self) -> "ContextCacheDatabase":
        try:
            prepared = self._prepare_path()
            database_is_empty, directory_identity, file_identity, sidecars = prepared
            self._connection = sqlite3.connect(str(self.path), timeout=0.5)
            self._validate_identity(directory_identity, file_identity)
            self._configure_connection(database_is_empty)
            self._secure_new_sidecars(sidecars)
            self._verify_or_create_schema()
            self._secure_new_sidecars(sidecars)
        except CacheDatabaseError:
            self._close_connection()
            raise
        except (OSError, sqlite3.Error) as error:
            self._close_connection()
            raise CacheDatabaseUnavailable("context cache database is unavailable") from error
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._close_connection()

    def table_names(self) -> set[str]:
        """Return the set of application tables in the open database."""
        return {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
            if not row[0].startswith("sqlite_")
        }

    @staticmethod
    def _identity(path: Path) -> tuple[int, int]:
        result = path.stat(follow_symlinks=False)
        return result.st_dev, result.st_ino

    @staticmethod
    def _is_link(path: Path) -> bool:
        try:
            attributes = getattr(path.lstat(), "st_file_attributes", 0)
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
                    if self._is_link(current) or not current.is_dir():
                        raise CacheDatabaseError("context cache directory is unsafe")
                else:
                    current.mkdir(mode=0o700)
            return current

        if self._is_link(directory):
            raise CacheDatabaseError("context cache directory must not be a symlink")
        if directory.exists():
            if not directory.is_dir():
                raise CacheDatabaseError("context cache directory must be a directory")
        else:
            if not directory.parent.is_dir() or self._is_link(directory.parent):
                raise CacheDatabaseError("context cache directory parent must already exist")
            directory.mkdir(mode=0o700)
        return directory

    def _prepare_path(
        self,
    ) -> tuple[bool, tuple[int, int], tuple[int, int], set[Path]]:
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

        directory = self._prepare_directory()

        directory_identity = self._identity(directory)
        if not database_existed:
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
            flags |= getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(self.path, flags, 0o600)
            try:
                if _uses_posix_permissions() and hasattr(os, "fchmod"):
                    os.fchmod(descriptor, 0o600)
            finally:
                os.close(descriptor)
        file_identity = self._identity(self.path)
        self._validate_secure_file(self.path)
        self._validate_sidecars()
        sidecars = self._existing_sidecars()
        database_is_empty = self.path.stat(follow_symlinks=False).st_size == 0
        return database_is_empty, directory_identity, file_identity, sidecars

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
        for sidecar in self._sidecar_paths():
            if sidecar.exists() or self._is_link(sidecar):
                self._validate_secure_file(sidecar)

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
        journal_mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
        if journal_mode.lower() != "wal":
            raise CacheDatabaseUnavailable("context cache database cannot enable WAL mode")
        connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")

    def _verify_or_create_schema(self) -> None:
        application_id = self.connection.execute("PRAGMA application_id").fetchone()[0]
        schema_version = self.connection.execute("PRAGMA user_version").fetchone()[0]
        tables = self.table_names()
        if application_id == 0 and schema_version == 0 and not tables:
            self._create_schema()
            return
        if application_id != APPLICATION_ID:
            raise CacheDatabaseError("context cache database has an unknown application id")
        if schema_version != SCHEMA_VERSION:
            raise CacheDatabaseError("context cache database has an unsupported schema version")
        if self.connection.execute("PRAGMA auto_vacuum").fetchone()[0] != 2:
            raise CacheDatabaseError("context cache database auto_vacuum is incompatible")
        if tables != _TABLE_NAMES:
            raise CacheDatabaseError("context cache database schema is incomplete")
        self._validate_schema_structure()
        namespace = self.connection.execute(
            "SELECT id FROM namespaces WHERE name = ?", (DEFAULT_NAMESPACE,)
        ).fetchone()
        if namespace is None:
            raise CacheDatabaseError("context cache database default namespace is missing")

    def _validate_schema_structure(self) -> None:
        expected_objects = {
            ("table", name, name, _canonical_ddl(ddl))
            for name, ddl in _SCHEMA_DDL.items()
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
        if actual_objects != expected_objects:
            raise CacheDatabaseError("context cache database schema objects differ")
        actual_ddl = dict(self.connection.execute(
            "SELECT name, sql FROM sqlite_schema WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%'"
        ))
        expected_ddl = {
            name: _canonical_ddl(ddl) for name, ddl in _SCHEMA_DDL.items()
        }
        if {name: _canonical_ddl(ddl) for name, ddl in actual_ddl.items()} != expected_ddl:
            raise CacheDatabaseError("context cache database schema DDL differs")
        for table, expected in _EXPECTED_COLUMNS.items():
            actual = tuple(
                (row[1], row[2].upper(), row[3], row[5])
                for row in self.connection.execute(f'PRAGMA table_info("{table}")')
            )
            if actual != expected:
                raise CacheDatabaseError(f"context cache database schema differs: {table}")
        for table, expected in _EXPECTED_FOREIGN_KEYS.items():
            actual = {
                (row[3], row[2], row[4], row[5].upper(), row[6].upper(), row[7].upper())
                for row in self.connection.execute(f'PRAGMA foreign_key_list("{table}")')
            }
            if actual != expected:
                raise CacheDatabaseError(f"context cache database schema differs: {table}")
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
                raise CacheDatabaseError(f"context cache database schema differs: {table}")
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
            raise CacheDatabaseError("context cache database schema differs: files state")

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

    def _close_connection(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None


def _uses_posix_permissions() -> bool:
    return os.name != "nt"


def _canonical_ddl(ddl: str) -> str:
    return re.sub(r"\s+", "", ddl).rstrip(";").casefold()
