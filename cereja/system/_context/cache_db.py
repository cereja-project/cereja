"""Private SQLite bootstrap for the bounded text-context cache."""

import os
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

_TABLE_NAMES = frozenset(
    {"metadata", "namespaces", "namespace_roots", "roots", "root_files", "files"}
)


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
    """Own the lifecycle and schema identity of one context-cache database."""

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
            database_existed = self._prepare_path()
            self._connection = sqlite3.connect(str(self.path), timeout=0.5)
            self._configure_connection(database_existed)
            self._verify_or_create_schema()
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

    def _prepare_path(self) -> bool:
        if self.path.is_symlink():
            raise CacheDatabaseError("context cache database must not be a symlink")
        try:
            mode = self.path.lstat().st_mode
        except FileNotFoundError:
            database_existed = False
        else:
            if not stat.S_ISREG(mode):
                raise CacheDatabaseError("context cache database must be a regular file")
            database_existed = True

        directory = self.path.parent
        if directory.is_symlink():
            raise CacheDatabaseError("context cache directory must not be a symlink")
        if directory.exists() and not directory.is_dir():
            raise CacheDatabaseError("context cache directory must be a directory")
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt":
            os.chmod(directory, 0o700)
        return database_existed

    def _configure_connection(self, database_existed: bool) -> None:
        connection = self.connection
        connection.execute("PRAGMA foreign_keys = ON")
        journal_mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
        if journal_mode.lower() != "wal":
            raise CacheDatabaseUnavailable("context cache database cannot enable WAL mode")
        connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        if not database_existed:
            connection.execute("PRAGMA auto_vacuum = INCREMENTAL")
            connection.execute("VACUUM")
            if os.name != "nt":
                os.chmod(self.path, 0o600)

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
        if tables != _TABLE_NAMES:
            raise CacheDatabaseError("context cache database schema is incomplete")

    def _create_schema(self) -> None:
        timestamp = time.time_ns()
        self.connection.executescript(
            f"""
                BEGIN;
                PRAGMA application_id = {APPLICATION_ID};
                PRAGMA user_version = {SCHEMA_VERSION};
                CREATE TABLE metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE namespaces (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    last_access_ns INTEGER NOT NULL
                );
                CREATE TABLE roots (
                    id INTEGER PRIMARY KEY,
                    canonical_path TEXT NOT NULL UNIQUE,
                    last_access_ns INTEGER NOT NULL
                );
                CREATE TABLE namespace_roots (
                    namespace_id INTEGER NOT NULL REFERENCES namespaces(id) ON DELETE CASCADE,
                    root_id INTEGER NOT NULL REFERENCES roots(id) ON DELETE CASCADE,
                    PRIMARY KEY (namespace_id, root_id)
                );
                CREATE TABLE files (
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
                );
                CREATE TABLE root_files (
                    root_id INTEGER NOT NULL REFERENCES roots(id) ON DELETE CASCADE,
                    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
                    relative_path TEXT NOT NULL,
                    last_seen_scan TEXT NOT NULL,
                    PRIMARY KEY (root_id, file_id)
                );
                INSERT INTO namespaces (name, last_access_ns)
                    VALUES ('{DEFAULT_NAMESPACE}', {timestamp});
                COMMIT;
            """
        )

    def _close_connection(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
