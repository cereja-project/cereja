"""Private SQLite bootstrap for the bounded text-context cache."""

import os
import re
import sqlite3
import stat
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional, Union


APPLICATION_ID = 0x434A4358  # "CJCX"
SCHEMA_VERSION = 1
DEFAULT_NAMESPACE = "default"
DEFAULT_MAX_BYTES = 256 * 1024 * 1024
BUSY_TIMEOUT_MS = 500

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

    def aggregate_size_bytes(self) -> int:
        """Return the current byte size of the database and WAL sidecars."""
        total = 0
        for path in (self.path, *self._sidecar_paths()):
            try:
                total += path.stat(follow_symlinks=False).st_size
            except FileNotFoundError:
                continue
        return total

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
        if application_id != APPLICATION_ID:
            raise CacheDatabaseError("context cache database has an unknown application id")
        if schema_version != SCHEMA_VERSION:
            raise CacheDatabaseError("context cache database has an unsupported schema version")
        if self.connection.execute("PRAGMA auto_vacuum").fetchone()[0] != 2:
            raise CacheDatabaseError("context cache database auto_vacuum is incompatible")
        if tables != _TABLE_NAMES:
            raise CacheDatabaseError("context cache database schema is incomplete")
        namespace = self.connection.execute(
            "SELECT id FROM namespaces WHERE name = ?", (DEFAULT_NAMESPACE,)
        ).fetchone()
        if namespace is None:
            raise CacheDatabaseError("context cache database default namespace is missing")
        if self._schema_objects_match(_LEGACY_SCHEMA_DDL):
            self._migrate_legacy_schema()
        self._validate_schema_structure()

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
                raise CacheDatabaseError(
                    "context cache database schema changed during migration"
                )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise

    def _validate_schema_structure(self) -> None:
        if not self._schema_objects_match(_SCHEMA_DDL):
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
        for (table, column), expected in _EXPECTED_COLUMN_DEFAULTS.items():
            defaults = {
                row[1]: row[4]
                for row in self.connection.execute(f'PRAGMA table_info("{table}")')
            }
            if defaults.get(column) != expected:
                raise CacheDatabaseError(
                    f"context cache database schema differs: {table}.{column}"
                )
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
