import os
import sqlite3
import stat
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cereja.system._context.cache_db import (
    APPLICATION_ID,
    BUSY_TIMEOUT_MS,
    SCHEMA_VERSION,
    CacheDatabaseError,
    CacheDatabaseUnavailable,
    CacheMaintenanceReport,
    CachedFile,
    ContextCacheDatabase,
    FileSignature,
    ScanToken,
    _CachePathLock,
    _LEGACY_SCHEMA_DDL,
    default_cache_path,
)


def _create_legacy_database(path):
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA auto_vacuum = INCREMENTAL")
    connection.execute("VACUUM")
    connection.execute("PRAGMA journal_mode = WAL")
    ddl = ";\n".join(_LEGACY_SCHEMA_DDL.values())
    connection.executescript(
        f"""
        PRAGMA application_id = {APPLICATION_ID};
        PRAGMA user_version = {SCHEMA_VERSION};
        {ddl};
        INSERT INTO namespaces (id, name, last_access_ns)
            VALUES (1, 'default', 1);
        """
    )
    connection.close()


def _storage_snapshot(database):
    paths = (database.path, *database._sidecar_paths())
    sizes = tuple(
        path.stat(follow_symlinks=False).st_size if path.exists() else 0
        for path in paths
    )
    return (*sizes, database.aggregate_size_bytes())


def _truncate_recognized_database(path):
    with ContextCacheDatabase(path):
        pass
    original = path.read_bytes()
    path.write_bytes(original[:128])
    return path.read_bytes()


class _FailingPragmaConnection:
    def __init__(self, connection, statement, error, *, after=False):
        self._connection = connection
        self._statement = " ".join(statement.casefold().split())
        self._error = error
        self._after = after
        self._failed = False

    def execute(self, statement, *args, **kwargs):
        normalized = " ".join(statement.casefold().split())
        if not self._failed and normalized == self._statement:
            self._failed = True
            if self._after:
                self._connection.execute(statement, *args, **kwargs)
            raise self._error
        return self._connection.execute(statement, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._connection, name)


class ContextCacheDatabaseTest(unittest.TestCase):
    def test_connection_disables_automatic_wal_checkpointing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                automatic_checkpoint_pages = database.connection.execute(
                    "PRAGMA wal_autocheckpoint"
                ).fetchone()[0]

            self.assertEqual(automatic_checkpoint_pages, 0)

    def test_begin_scan_is_in_memory_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                database._checkpoint_wal()
                baseline = database.aggregate_size_bytes()

                token = database.begin_scan("default", "C:/repo")

                self.assertEqual(token.namespace, "default")
                self.assertEqual(token.canonical_root, "C:/repo")
                self.assertEqual(database.aggregate_size_bytes(), baseline)
                self.assertEqual(
                    database.connection.execute(
                        "SELECT COUNT(*) FROM roots"
                    ).fetchone()[0],
                    0,
                )

    def test_begin_scan_orders_tied_clock_values_by_begin_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            nonces = [
                uuid.UUID("00000000-0000-0000-0000-000000000002"),
                uuid.UUID("00000000-0000-0000-0000-000000000001"),
            ]
            with ContextCacheDatabase(database_path) as database, \
                 patch("cereja.system._context.cache_db.time.time_ns", return_value=7), \
                 patch("cereja.system._context.cache_db.uuid.uuid4", side_effect=nonces):
                old_scan = database.begin_scan("default", "C:/repo")
                new_scan = database.begin_scan("default", "C:/repo")

            self.assertLess(old_scan.started_ns, new_scan.started_ns)

    def test_refused_scan_preflight_does_not_change_physical_storage(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                database.connection.execute(
                    "UPDATE namespaces SET last_access_ns = last_access_ns + 1"
                )
                database.connection.commit()
                baseline = _storage_snapshot(database)
                self.assertGreater(baseline[1], 0)

                scans = database.begin_scans_if_admitted(
                    "default", ["C:/repo"], max_bytes=0
                )

                self.assertIsNone(scans)
                self.assertEqual(_storage_snapshot(database), baseline)

    def test_scan_preflight_includes_conservative_physical_projection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                database._checkpoint_wal()
                aggregate = database.aggregate_size_bytes()
                projected = database._projected_aggregate_size()
                self.assertGreater(projected, aggregate)
                max_bytes = aggregate + (projected - aggregate) // 2
                baseline = _storage_snapshot(database)

                scans = database.begin_scans_if_admitted(
                    "default", ["C:/repo"], max_bytes=max_bytes
                )

                self.assertIsNone(scans)
                self.assertEqual(_storage_snapshot(database), baseline)

    def test_refused_bounded_commit_does_not_change_physical_storage(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                scan = database.begin_scan("default", "C:/repo")
                database.connection.execute(
                    "UPDATE namespaces SET last_access_ns = last_access_ns + 1"
                )
                database.connection.commit()
                baseline = _storage_snapshot(database)
                self.assertGreater(baseline[1], 0)

                admitted = database.commit_scan(scan, [], max_bytes=0)

                self.assertIsNone(admitted)
                self.assertEqual(_storage_snapshot(database), baseline)

    def test_preflight_and_bounded_commit_never_run_maintenance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                statements = []
                database.connection.set_trace_callback(statements.append)
                scans = database.begin_scans_if_admitted(
                    "default", ["C:/repo"], max_bytes=10 ** 9
                )

                admitted = database.commit_scan(
                    scans["C:/repo"], [], max_bytes=10 ** 9
                )
                database.connection.set_trace_callback(None)

                self.assertEqual(admitted, ())
                maintenance = [
                    statement
                    for statement in statements
                    if "wal_checkpoint" in statement.casefold()
                    or "incremental_vacuum" in statement.casefold()
                ]
                self.assertEqual(maintenance, [])

    def test_reader_after_preflight_leaves_root_generation_and_storage_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                seed = database.begin_scan("default", "C:/repo")
                database.commit_scan(seed, [])
                database._checkpoint_wal()
                baseline = database.aggregate_size_bytes()
                generation = database.connection.execute(
                    "SELECT scan_generation FROM roots WHERE canonical_path = 'C:/repo'"
                ).fetchone()[0]
                scans = database.begin_scans_if_admitted(
                    "default", ["C:/repo"], 10 ** 9
                )
                reader = sqlite3.connect(database_path)
                try:
                    reader.execute("BEGIN")
                    reader.execute("SELECT COUNT(*) FROM roots").fetchone()
                    admitted = database.commit_scan(
                        scans["C:/repo"], [], max_bytes=10 ** 9
                    )
                finally:
                    reader.close()

                self.assertIsNone(admitted)
                self.assertEqual(database.aggregate_size_bytes(), baseline)
                self.assertEqual(
                    database.connection.execute(
                        "SELECT scan_generation FROM roots WHERE canonical_path = 'C:/repo'"
                    ).fetchone()[0],
                    generation,
                )

    def test_bounded_commit_releases_exclusive_lock_before_returning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as first:
                scan = first.begin_scan("default", "C:/repo")
                self.assertEqual(first.commit_scan(scan, [], max_bytes=10 ** 9), ())
                shared = _CachePathLock(database_path)
                shared.acquire(False, wait=False)
                shared.release()

    def test_first_published_token_wins_when_scan_timestamps_are_equal(self):
        nonce_pairs = (
            (
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000002",
            ),
            (
                "00000000-0000-0000-0000-000000000002",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        for winning_nonce, losing_nonce in nonce_pairs:
            with self.subTest(
                    winning_nonce=winning_nonce, losing_nonce=losing_nonce), \
                    tempfile.TemporaryDirectory() as temp_dir:
                database_path = Path(temp_dir) / "context.sqlite3"
                winning_file = CachedFile(
                    "C:/repo/a.txt", "a.txt",
                    FileSignature(None, None, 1, 2, 2),
                    "text", "winner", None,
                )
                losing_file = CachedFile(
                    "C:/repo/a.txt", "a.txt",
                    FileSignature(None, None, 1, 1, 1),
                    "text", "loser", None,
                )
                with ContextCacheDatabase(database_path) as database:
                    winning_scan = ScanToken(
                        "default", "C:/repo", 7, winning_nonce
                    )
                    losing_scan = ScanToken(
                        "default", "C:/repo", 7, losing_nonce
                    )
                    database.commit_scan(winning_scan, [winning_file])
                    baseline = _storage_snapshot(database)
                    generation = database.connection.execute(
                        "SELECT scan_generation FROM roots"
                    ).fetchone()[0]

                    with self.assertRaises(CacheDatabaseError):
                        database.commit_scan(losing_scan, [losing_file])

                    self.assertEqual(_storage_snapshot(database), baseline)
                    self.assertEqual(
                        database.connection.execute(
                            "SELECT scan_generation FROM roots"
                        ).fetchone()[0],
                        generation,
                    )
                    rows = list(database.iter_root_files("default", "C:/repo"))
                self.assertEqual(
                    [row.folded_text for row in rows], ["winner"]
                )

    def test_replayed_token_cannot_publish_a_different_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            first_file = CachedFile(
                "C:/repo/a.txt", "a.txt", FileSignature(None, None, 1, 1, 1),
                "text", "first", None,
            )
            changed_file = CachedFile(
                "C:/repo/a.txt", "a.txt", FileSignature(None, None, 1, 2, 2),
                "text", "changed", None,
            )
            with ContextCacheDatabase(database_path) as database:
                scan = database.begin_scan("default", "C:/repo")
                database.commit_scan(scan, [first_file])
                baseline = _storage_snapshot(database)

                with self.assertRaises(CacheDatabaseError):
                    database.commit_scan(scan, [changed_file])

                self.assertEqual(_storage_snapshot(database), baseline)
                rows = list(database.iter_root_files("default", "C:/repo"))
            self.assertEqual([row.folded_text for row in rows], ["first"])

    def test_bounded_commit_restores_normal_locking_when_size_check_fails(
            self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                connection = database.connection
                scan = database.begin_scan("default", "C:/repo")
                current_size = database.aggregate_size_bytes()
                with patch.object(
                    database,
                    "aggregate_size_bytes",
                    side_effect=(
                        current_size,
                        RuntimeError("size check failed"),
                    ),
                ), self.assertRaisesRegex(RuntimeError, "size check failed"):
                    database.commit_scan(scan, [], max_bytes=10 ** 9)

                self.assertEqual(
                    connection.execute("PRAGMA locking_mode").fetchone()[0],
                    "normal",
                )
                self.assertNotEqual(
                    connection.execute("PRAGMA cache_spill").fetchone()[0],
                    0,
                )

    def test_bounded_commit_restores_normal_locking_when_cache_spill_fails(
            self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                connection = database.connection
                database._connection = _FailingPragmaConnection(
                    connection,
                    "PRAGMA cache_spill = OFF",
                    RuntimeError("cache spill setup failed"),
                    after=True,
                )
                scan = database.begin_scan("default", "C:/repo")
                with self.assertRaisesRegex(
                    RuntimeError, "cache spill setup failed"
                ):
                    database.commit_scan(scan, [], max_bytes=10 ** 9)

                self.assertEqual(
                    connection.execute("PRAGMA locking_mode").fetchone()[0],
                    "normal",
                )
                self.assertNotEqual(
                    connection.execute("PRAGMA cache_spill").fetchone()[0],
                    0,
                )

    def test_cache_spill_restore_failure_does_not_skip_lock_restore(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                connection = database.connection
                database._connection = _FailingPragmaConnection(
                    connection,
                    "PRAGMA cache_spill = ON",
                    RuntimeError("cache spill restore failed"),
                )
                scan = database.begin_scan("default", "C:/repo")
                with self.assertRaisesRegex(
                    RuntimeError, "cache spill restore failed"
                ):
                    database.commit_scan(scan, [], max_bytes=10 ** 9)

                self.assertEqual(
                    connection.execute("PRAGMA locking_mode").fetchone()[0],
                    "normal",
                )

    def test_commit_error_is_preserved_when_cache_spill_restore_also_fails(
            self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                connection = database.connection
                database._connection = _FailingPragmaConnection(
                    connection,
                    "PRAGMA cache_spill = ON",
                    RuntimeError("cache spill restore failed"),
                )
                scan = database.begin_scan("default", "C:/repo")
                initial_projection = database._projected_aggregate_size()
                with patch.object(
                    database,
                    "_projected_aggregate_size",
                    side_effect=(
                        initial_projection,
                        ValueError("projection failed"),
                    ),
                ), self.assertRaisesRegex(
                    ValueError, "projection failed"
                ) as caught:
                    database.commit_scan(scan, [], max_bytes=10 ** 9)

                self.assertIsInstance(
                    caught.exception.__cause__, RuntimeError
                )
                self.assertEqual(
                    connection.execute("PRAGMA locking_mode").fetchone()[0],
                    "normal",
                )

    def test_primary_error_chains_both_pragma_restoration_errors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                connection = database.connection
                database._connection = _FailingPragmaConnection(
                    connection,
                    "PRAGMA cache_spill = ON",
                    RuntimeError("cache spill restore failed"),
                )
                scan = database.begin_scan("default", "C:/repo")
                initial_projection = database._projected_aggregate_size()
                with patch.object(
                    database,
                    "_projected_aggregate_size",
                    side_effect=(
                        initial_projection,
                        ValueError("projection failed"),
                    ),
                ), patch.object(
                    database,
                    "_restore_normal_locking",
                    side_effect=RuntimeError("locking restore failed"),
                ), self.assertRaisesRegex(
                    ValueError, "projection failed"
                ) as caught:
                    database.commit_scan(scan, [], max_bytes=10 ** 9)

                cleanup_group = caught.exception.__cause__
                self.assertIsInstance(cleanup_group, BaseExceptionGroup)
                self.assertEqual(
                    [str(error) for error in cleanup_group.exceptions],
                    [
                        "cache spill restore failed",
                        "locking restore failed",
                    ],
                )
                database._restore_normal_locking()

    def test_exclusive_setup_error_restores_normal_locking(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                connection = database.connection
                database._connection = _FailingPragmaConnection(
                    connection,
                    "PRAGMA locking_mode = EXCLUSIVE",
                    RuntimeError("exclusive setup failed"),
                    after=True,
                )
                scan = database.begin_scan("default", "C:/repo")
                with self.assertRaisesRegex(
                    RuntimeError, "exclusive setup failed"
                ):
                    database.commit_scan(scan, [], max_bytes=10 ** 9)

                self.assertEqual(
                    connection.execute("PRAGMA locking_mode").fetchone()[0],
                    "normal",
                )
                self.assertNotEqual(
                    connection.execute("PRAGMA cache_spill").fetchone()[0],
                    0,
                )

    def test_commit_scan_at_physical_quota_is_read_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                scans = database.begin_scans_if_admitted(
                    "default", ["C:/repo"], 10 ** 9
                )
                database._checkpoint_wal()
                quota = database.aggregate_size_bytes()

                admitted = database.commit_scan(
                    scans["C:/repo"], [], max_bytes=quota
                )

                self.assertIsNone(admitted)

    def test_stale_deletion_rolls_back_when_projected_wal_exceeds_quota(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                files = [
                    CachedFile(
                        f"C:/repo/{index}.txt",
                        f"{index}.txt",
                        FileSignature(None, None, 1_000, index, index),
                        "text",
                        "x" * 1_000,
                        None,
                    )
                    for index in range(20)
                ]
                seed = database.begin_scan("default", "C:/repo")
                database.commit_scan(seed, files)
                database._checkpoint_wal()
                scan = database.begin_scan("default", "C:/repo")
                database._checkpoint_wal()
                quota = 10 ** 9
                baseline = _storage_snapshot(database)
                statements = []
                database.connection.set_trace_callback(statements.append)

                with patch.object(
                    database,
                    "_projected_aggregate_size",
                    side_effect=(0, 0, quota + 1),
                ):
                    admitted = database.commit_scan(
                        scan, [], max_bytes=quota
                    )
                database.connection.set_trace_callback(None)

                self.assertIsNone(admitted)
                self.assertTrue(any(
                    "delete from root_files" in statement.casefold()
                    for statement in statements
                ))
                self.assertEqual(_storage_snapshot(database), baseline)
                self.assertEqual(
                    len(tuple(database.iter_root_files("default", "C:/repo"))),
                    len(files),
                )

    def test_busy_commit_does_not_remove_existing_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            cached = CachedFile(
                "C:/repo/file.txt",
                "file.txt",
                FileSignature(None, None, 4, 1, 1),
                "text",
                "text",
                None,
            )
            with ContextCacheDatabase(database_path) as database:
                seed = database.begin_scan("default", "C:/repo")
                database.commit_scan(seed, [cached])
                database._checkpoint_wal()
                scan = database.begin_scan("default", "C:/repo")
                database._checkpoint_wal()
                reader = sqlite3.connect(database_path)
                try:
                    reader.execute("BEGIN")
                    reader.execute("SELECT COUNT(*) FROM files").fetchone()
                    database.connection.execute(
                        "UPDATE roots SET last_access_ns = last_access_ns + 1"
                    )
                    database.connection.commit()
                    baseline = _storage_snapshot(database)

                    admitted = database.commit_scan(
                        scan, [], max_bytes=10 ** 9
                    )
                finally:
                    reader.close()

                self.assertIsNone(admitted)
                self.assertEqual(_storage_snapshot(database), baseline)
                self.assertEqual(
                    [item.relative_path for item in database.iter_root_files(
                        "default", "C:/repo"
                    )],
                    ["file.txt"],
                )

    def test_quota_admission_stops_at_first_rejected_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                scan = database.begin_scan("default", "C:/repo")
                database._checkpoint_wal()
                baseline = database.aggregate_size_bytes()
                quota = baseline * 2 + 24_000
                sizes = (8_000, 8_000, 50_000, 10)
                candidates = [
                    CachedFile(
                        f"C:/repo/{index}.txt",
                        f"{index}.txt",
                        FileSignature(None, None, size, index, index),
                        "text",
                        chr(65 + index) * size,
                        None,
                    )
                    for index, size in enumerate(sizes)
                ]

                admitted = database.commit_scan(
                    scan, candidates, max_bytes=quota
                )

                self.assertGreater(len(admitted), 0)
                self.assertLess(len(admitted), len(candidates))
                self.assertEqual(admitted, tuple(candidates[:len(admitted)]))

    def test_quota_admission_refuses_content_when_checkpoint_is_busy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                database._checkpoint_wal()
                reader = sqlite3.connect(database_path)
                try:
                    reader.execute("BEGIN")
                    reader.execute("SELECT COUNT(*) FROM files").fetchone()
                    scan = database.begin_scan("default", "C:/repo")
                    candidate = CachedFile(
                        "C:/repo/file.txt",
                        "file.txt",
                        FileSignature(None, None, 1_000, 1, 1),
                        "text",
                        "x" * 1_000,
                        None,
                    )

                    admitted = database.commit_scan(
                        scan,
                        [candidate],
                        max_bytes=database.aggregate_size_bytes() + 100_000,
                    )
                finally:
                    reader.close()

                self.assertIsNone(admitted)
                self.assertEqual(
                    database.connection.execute(
                        "SELECT COUNT(*) FROM root_files"
                    ).fetchone()[0],
                    0,
                )

    def test_windows_treats_missing_reparse_attributes_as_not_a_link(self):
        path = Path("regular-target")
        result = SimpleNamespace(st_file_attributes=None)
        with patch("cereja.system._context.cache_db.os.name", "nt"), \
             patch.object(Path, "lstat", return_value=result), \
             patch.object(Path, "is_symlink", return_value=False), \
             patch.object(Path, "is_junction", return_value=False, create=True):
            self.assertFalse(ContextCacheDatabase._is_link(path))

    def test_commit_scan_upserts_files_and_removes_only_stale_associations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                first_scan = database.begin_scan("default", "C:/repo")
                database.commit_scan(first_scan, [
                    CachedFile(
                        "C:/repo/a.txt",
                        "a.txt",
                        FileSignature(None, None, 1, 10, 11),
                        "text",
                        "a",
                        None,
                    ),
                    CachedFile(
                        "C:/repo/b.txt",
                        "b.txt",
                        FileSignature(None, None, 1, 10, 11),
                        "text",
                        "b",
                        None,
                    ),
                ])
                other_scan = database.begin_scan("default", "C:/other")
                database.commit_scan(other_scan, [CachedFile(
                    "C:/other/kept.txt",
                    "kept.txt",
                    FileSignature(None, None, 1, 10, 11),
                    "text",
                    "kept",
                    None,
                )])
                second_scan = database.begin_scan("default", "C:/repo")
                database.commit_scan(second_scan, [
                    CachedFile(
                        "C:/repo/a.txt",
                        "a.txt",
                        FileSignature(None, None, 1, 12, 13),
                        "text",
                        "changed",
                        None,
                    ),
                ])
                rows = list(database.iter_root_files("default", "C:/repo"))
                other_rows = list(database.iter_root_files("default", "C:/other"))
            self.assertEqual(
                [(row.relative_path, row.folded_text) for row in rows],
                [("a.txt", "changed")],
            )
            self.assertEqual(
                [(row.relative_path, row.folded_text) for row in other_rows],
                [("kept.txt", "kept")],
            )

    def test_abandoned_scan_does_not_delete_existing_associations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            seeded = CachedFile(
                "C:/repo/a.txt",
                "a.txt",
                FileSignature(None, None, 1, 10, 11),
                "text",
                "a",
                None,
            )
            with ContextCacheDatabase(database_path) as database:
                completed = database.begin_scan("default", "C:/repo")
                database.commit_scan(completed, [seeded])
                database.begin_scan("default", "C:/repo")
            with ContextCacheDatabase(database_path) as database:
                rows = list(database.iter_root_files("default", "C:/repo"))
            self.assertEqual([row.relative_path for row in rows], ["a.txt"])

    def test_older_scan_cannot_delete_newer_scan_associations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            new_file = CachedFile(
                "C:/repo/a.txt", "a.txt", FileSignature(None, None, 1, 12, 13),
                "text", "new", None,
            )
            with ContextCacheDatabase(database_path) as database:
                old_scan = database.begin_scan("default", "C:/repo")
                new_scan = database.begin_scan("default", "C:/repo")
                database.commit_scan(new_scan, [new_file])
                with self.assertRaises(CacheDatabaseError):
                    database.commit_scan(old_scan, [])
                rows = list(database.iter_root_files("default", "C:/repo"))
            self.assertEqual([row.folded_text for row in rows], ["new"])

    def test_new_scan_in_later_connection_invalidates_older_token(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            old_file = CachedFile(
                "C:/repo/a.txt", "a.txt", FileSignature(None, None, 1, 10, 11),
                "text", "old", None,
            )
            new_file = CachedFile(
                "C:/repo/a.txt", "a.txt", FileSignature(None, None, 1, 12, 13),
                "text", "new", None,
            )
            with ContextCacheDatabase(database_path) as first:
                old_scan = first.begin_scan("default", "C:/repo")
            with ContextCacheDatabase(database_path) as second:
                new_scan = second.begin_scan("default", "C:/repo")
                second.commit_scan(new_scan, [new_file])
            with ContextCacheDatabase(database_path) as third:
                with self.assertRaises(CacheDatabaseError):
                    third.commit_scan(old_scan, [old_file])
                rows = list(third.iter_root_files("default", "C:/repo"))
            self.assertEqual([row.folded_text for row in rows], ["new"])

    def test_commit_scan_materializes_input_before_starting_transaction(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            seeded = CachedFile(
                "C:/repo/a.txt", "a.txt", FileSignature(None, None, 1, 10, 11),
                "text", "seeded", None,
            )
            with ContextCacheDatabase(database_path) as database:
                seed_scan = database.begin_scan("default", "C:/repo")
                database.commit_scan(seed_scan, [seeded])
                failed_scan = database.begin_scan("default", "C:/repo")

                def failing_files():
                    yield CachedFile(
                        "C:/repo/b.txt", "b.txt",
                        FileSignature(None, None, 1, 12, 13),
                        "text", "partial", None,
                    )
                    database.get_cached_file(
                        "C:/repo/a.txt", FileSignature(None, None, 1, 10, 11), 100
                    )
                    raise RuntimeError("scan failed")

                with self.assertRaisesRegex(RuntimeError, "scan failed"):
                    database.commit_scan(failed_scan, failing_files())
                rows = list(database.iter_root_files("default", "C:/repo"))
            self.assertEqual([row.folded_text for row in rows], ["seeded"])

    def test_get_cached_file_requires_every_signature_field_to_match(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            cached_file = CachedFile(
                "C:/repo/a.txt",
                "a.txt",
                FileSignature(2, 3, 4, 5, 6),
                "text",
                "cached",
                "digest",
            )
            with ContextCacheDatabase(database_path) as database:
                scan = database.begin_scan("default", "C:/repo")
                database.commit_scan(scan, [cached_file])
                self.assertEqual(
                    database.get_cached_file(
                        "C:/repo/a.txt", FileSignature(2, 3, 4, 5, 6), 100
                    ),
                    cached_file,
                )
                mismatches = (
                    FileSignature(9, 3, 4, 5, 6),
                    FileSignature(2, 9, 4, 5, 6),
                    FileSignature(2, 3, 9, 5, 6),
                    FileSignature(2, 3, 4, 9, 6),
                    FileSignature(2, 3, 4, 5, 9),
                )
                for signature in mismatches:
                    with self.subTest(signature=signature):
                        self.assertIsNone(
                            database.get_cached_file(
                                "C:/repo/a.txt", signature, 100
                            )
                        )

    def test_file_too_large_cache_is_reused_only_above_current_limit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            cached_file = CachedFile(
                "C:/repo/large.txt",
                "large.txt",
                FileSignature(None, None, 20, 30, 40),
                "file_too_large",
                None,
                None,
            )
            with ContextCacheDatabase(database_path) as database:
                scan = database.begin_scan("default", "C:/repo")
                database.commit_scan(scan, [cached_file])
                self.assertEqual(
                    database.get_cached_file(
                        "C:/repo/large.txt",
                        FileSignature(None, None, 20, 30, 40),
                        19,
                    ),
                    cached_file,
                )
                self.assertIsNone(
                    database.get_cached_file(
                        "C:/repo/large.txt",
                        FileSignature(None, None, 20, 30, 40),
                        20,
                    )
                )

    def test_text_cache_is_not_reused_above_current_file_limit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            cached_file = CachedFile(
                "C:/repo/a.txt", "a.txt", FileSignature(None, None, 20, 30, 40),
                "text", "cached", None,
            )
            with ContextCacheDatabase(database_path) as database:
                scan = database.begin_scan("default", "C:/repo")
                database.commit_scan(scan, [cached_file])
                self.assertIsNone(database.get_cached_file(
                    "C:/repo/a.txt", FileSignature(None, None, 20, 30, 40), 19
                ))

    def test_get_cached_file_rejects_ambiguous_relative_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            signature = FileSignature(None, None, 1, 10, 11)
            with ContextCacheDatabase(database_path) as database:
                parent_scan = database.begin_scan("default", "C:/repo")
                database.commit_scan(parent_scan, [CachedFile(
                    "C:/repo/sub/a.txt", "sub/a.txt", signature,
                    "text", "a", None,
                )])
                child_scan = database.begin_scan("default", "C:/repo/sub")
                database.commit_scan(child_scan, [CachedFile(
                    "C:/repo/sub/a.txt", "a.txt", signature,
                    "text", "a", None,
                )])
                self.assertIsNone(database.get_cached_file(
                    "C:/repo/sub/a.txt", signature, 100
                ))

    def test_iter_root_files_refreshes_root_lru_timestamp(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                scan = database.begin_scan("default", "C:/repo")
                database.commit_scan(scan, [CachedFile(
                    "C:/repo/a.txt", "a.txt", FileSignature(None, None, 1, 10, 11),
                    "text", "a", None,
                )])
                database.connection.execute(
                    "UPDATE roots SET last_access_ns = 1 WHERE canonical_path = 'C:/repo'"
                )
                database.connection.commit()
                list(database.iter_root_files("default", "C:/repo"))
                refreshed = database.connection.execute(
                    "SELECT last_access_ns FROM roots WHERE canonical_path = 'C:/repo'"
                ).fetchone()[0]
            self.assertGreater(refreshed, 1)

    def test_aggregate_size_counts_database_and_existing_sidecars(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                expected = sum(
                    path.stat().st_size
                    for path in (
                        database_path,
                        Path(f"{database_path}-wal"),
                        Path(f"{database_path}-shm"),
                    )
                    if path.exists()
                )
                self.assertEqual(database.aggregate_size_bytes(), expected)

    def test_enforce_quota_preserves_protected_root_and_collects_orphans(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                for root, name in (
                    ("C:/old", "old.txt"),
                    ("C:/new", "new.txt"),
                    ("C:/protected", "protected.txt"),
                ):
                    scan = database.begin_scan("default", root)
                    database.commit_scan(scan, [CachedFile(
                        f"{root}/{name}",
                        name,
                        FileSignature(None, None, 1, 10, 11),
                        "text",
                        name,
                        None,
                    )])
                database.connection.execute(
                    "UPDATE roots SET last_access_ns = CASE canonical_path "
                    "WHEN 'C:/old' THEN 1 WHEN 'C:/new' THEN 2 ELSE 3 END"
                )
                database.connection.commit()

                report = database.enforce_quota("C:/protected", max_bytes=0)

                self.assertEqual(
                    report,
                    CacheMaintenanceReport(
                        associations_removed=2,
                        roots_removed=2,
                        files_removed=2,
                        before_bytes=report.before_bytes,
                        after_bytes=report.after_bytes,
                    ),
                )
                self.assertGreater(report.before_bytes, 0)
                self.assertEqual(report.after_bytes, database.aggregate_size_bytes())
                self.assertEqual(
                    [row[0] for row in database.connection.execute(
                        "SELECT canonical_path FROM roots ORDER BY canonical_path"
                    )],
                    ["C:/protected"],
                )
                self.assertEqual(
                    [row.relative_path for row in database.iter_root_files(
                        "default", "C:/protected"
                    )],
                    ["protected.txt"],
                )

    def test_enforce_quota_skips_protected_root_even_when_it_is_oldest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                for root, name in (
                    ("C:/active", "active.txt"),
                    ("C:/evictable", "evictable.txt"),
                ):
                    scan = database.begin_scan("default", root)
                    database.commit_scan(scan, [CachedFile(
                        f"{root}/{name}",
                        name,
                        FileSignature(None, None, 64_000, 10, 11),
                        "text",
                        name * 4_000,
                        None,
                    )])
                database.connection.execute(
                    "UPDATE roots SET last_access_ns = CASE canonical_path "
                    "WHEN 'C:/active' THEN 1 ELSE 2 END"
                )
                database.connection.commit()

                report = database.enforce_quota(
                    "C:/active", max_bytes=8 * 1024
                )

                self.assertEqual(report.associations_removed, 1)
                self.assertEqual(report.roots_removed, 1)
                self.assertEqual(report.files_removed, 1)
                self.assertEqual(
                    [row[0] for row in database.connection.execute(
                        "SELECT canonical_path FROM roots"
                    )],
                    ["C:/active"],
                )
                self.assertEqual(
                    [row.relative_path for row in database.iter_root_files(
                        "default", "C:/active"
                    )],
                    ["active.txt"],
                )

    def test_enforce_quota_collects_orphans_without_evictable_roots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            first_files = [
                CachedFile(
                    f"C:/protected/{name}",
                    name,
                    FileSignature(None, None, 1, 10, 11),
                    "text",
                    name,
                    None,
                )
                for name in ("kept.txt", "orphan.txt")
            ]
            with ContextCacheDatabase(database_path) as database:
                first_scan = database.begin_scan("default", "C:/protected")
                database.commit_scan(first_scan, first_files)
                second_scan = database.begin_scan("default", "C:/protected")
                database.commit_scan(second_scan, first_files[:1])

                report = database.enforce_quota("C:/protected", max_bytes=0)

                self.assertEqual(report.associations_removed, 0)
                self.assertEqual(report.roots_removed, 0)
                self.assertEqual(report.files_removed, 1)
                self.assertEqual(
                    database.connection.execute("SELECT COUNT(*) FROM files").fetchone()[0],
                    1,
                )

    def test_enforce_quota_uses_one_bounded_vacuum_after_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                for root, text in (
                    ("C:/oldest", "x"),
                    ("C:/old", "z"),
                    ("C:/protected", "y"),
                ):
                    scan = database.begin_scan("default", root)
                    database.commit_scan(scan, [CachedFile(
                        f"{root}/large.txt",
                        "large.txt",
                        FileSignature(None, None, 2_000_000, 10, 11),
                        "text",
                        text * 2_000_000,
                        None,
                    )])
                statements = []
                database.connection.set_trace_callback(statements.append)

                report = database.enforce_quota("C:/protected", max_bytes=0)

                self.assertEqual(report.roots_removed, 2)
                maintenance = [
                    statement.casefold() for statement in statements
                    if "wal_checkpoint" in statement or "incremental_vacuum" in statement
                ]
                self.assertEqual(maintenance.count("pragma incremental_vacuum(128)"), 1)
                vacuum_index = maintenance.index("pragma incremental_vacuum(128)")
                self.assertEqual(
                    maintenance[vacuum_index - 1], "pragma wal_checkpoint(truncate)"
                )
                self.assertEqual(maintenance[-1], "pragma wal_checkpoint(truncate)")

    def test_enforce_quota_stops_after_one_root_reaches_physical_quota(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                for root, text in (
                    ("C:/oldest", "x"),
                    ("C:/newer", "z"),
                    ("C:/protected", "y"),
                ):
                    scan = database.begin_scan("default", root)
                    database.commit_scan(scan, [CachedFile(
                        f"{root}/large.txt",
                        "large.txt",
                        FileSignature(None, None, 2_000_000, 10, 11),
                        "text",
                        text * 2_000_000,
                        None,
                    )])
                database.connection.execute(
                    "UPDATE roots SET last_access_ns = CASE canonical_path "
                    "WHEN 'C:/oldest' THEN 1 WHEN 'C:/newer' THEN 2 ELSE 3 END"
                )
                database.connection.commit()
                database.connection.execute(
                    "PRAGMA wal_checkpoint(TRUNCATE)"
                ).fetchone()
                quota = database.aggregate_size_bytes() - 1

                report = database.enforce_quota("C:/protected", max_bytes=quota)

                self.assertEqual(report.roots_removed, 1)
                self.assertLessEqual(report.after_bytes, quota)
                self.assertEqual(
                    [row[0] for row in database.connection.execute(
                        "SELECT canonical_path FROM roots ORDER BY canonical_path"
                    )],
                    ["C:/newer", "C:/protected"],
                )

    def test_enforce_quota_stops_when_reader_blocks_physical_measurement(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(database_path) as database:
                for root, text in (
                    ("C:/oldest", "x"),
                    ("C:/newer", "z"),
                    ("C:/protected", "y"),
                ):
                    scan = database.begin_scan("default", root)
                    database.commit_scan(scan, [CachedFile(
                        f"{root}/large.txt",
                        "large.txt",
                        FileSignature(None, None, 2_000_000, 10, 11),
                        "text",
                        text * 2_000_000,
                        None,
                    )])
                database.connection.execute(
                    "UPDATE roots SET last_access_ns = CASE canonical_path "
                    "WHEN 'C:/oldest' THEN 1 WHEN 'C:/newer' THEN 2 ELSE 3 END"
                )
                database.connection.commit()
                database.connection.execute(
                    "PRAGMA wal_checkpoint(TRUNCATE)"
                ).fetchone()
                quota = database.aggregate_size_bytes() - 1

                reader = sqlite3.connect(database_path)
                try:
                    reader.execute("BEGIN")
                    reader.execute("SELECT COUNT(*) FROM files").fetchone()
                    statements = []
                    database.connection.set_trace_callback(statements.append)
                    report = database.enforce_quota(
                        "C:/protected", max_bytes=quota
                    )
                    roots = [row[0] for row in database.connection.execute(
                        "SELECT canonical_path FROM roots ORDER BY canonical_path"
                    )]
                    database.connection.set_trace_callback(None)
                finally:
                    reader.close()

                checkpoint = database.connection.execute(
                    "PRAGMA wal_checkpoint(TRUNCATE)"
                ).fetchone()
                database.connection.execute("PRAGMA incremental_vacuum(128)")
                checkpoint = database.connection.execute(
                    "PRAGMA wal_checkpoint(TRUNCATE)"
                ).fetchone()
                settled_size = database.aggregate_size_bytes()

                self.assertEqual(report.roots_removed, 1)
                self.assertGreater(report.after_bytes, quota)
                self.assertFalse(any(
                    "incremental_vacuum" in statement.casefold()
                    for statement in statements
                ))
                self.assertEqual(roots, ["C:/newer", "C:/protected"])
                self.assertEqual(checkpoint[0], 0)
                self.assertLessEqual(settled_size, quota)

    def test_windows_rejects_any_reparse_point_attribute(self):
        path = Path("reparse-target")
        result = SimpleNamespace(st_file_attributes=0x400)
        with patch("cereja.system._context.cache_db.os.name", "nt"), \
             patch.object(Path, "lstat", return_value=result), \
             patch.object(Path, "is_symlink", return_value=False):
            self.assertTrue(ContextCacheDatabase._is_link(path))

    def test_windows_default_path_uses_local_app_data(self):
        with patch("cereja.system._context.cache_db.os.name", "nt"), \
             patch.dict(os.environ, {"LOCALAPPDATA": "C:/Users/test/AppData/Local"}):
            self.assertEqual(
                default_cache_path(),
                Path("C:/Users/test/AppData/Local/Cereja/cache/context.sqlite3"),
            )

    def test_open_creates_identified_versioned_schema(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(path) as database:
                table_names = database.table_names()
                self.assertEqual(
                    database.connection.execute("PRAGMA foreign_keys").fetchone()[0], 1
                )
                self.assertEqual(
                    database.connection.execute("PRAGMA busy_timeout").fetchone()[0],
                    BUSY_TIMEOUT_MS,
                )
                self.assertEqual(
                    database.connection.execute("PRAGMA journal_mode").fetchone()[0],
                    "wal",
                )
                self.assertEqual(
                    database.connection.execute("PRAGMA auto_vacuum").fetchone()[0], 2
                )
            connection = sqlite3.connect(path)
            self.assertEqual(
                connection.execute("PRAGMA application_id").fetchone()[0],
                APPLICATION_ID,
            )
            self.assertEqual(
                connection.execute("PRAGMA user_version").fetchone()[0],
                SCHEMA_VERSION,
            )
            self.assertEqual(
                table_names,
                {"metadata", "namespaces", "namespace_roots", "roots", "root_files", "files"},
            )
            self.assertEqual(
                connection.execute("SELECT name FROM namespaces").fetchall(),
                [("default",)],
            )
            connection.close()

    def test_open_leaves_unknown_application_database_byte_for_byte_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            connection = sqlite3.connect(path)
            connection.execute(f"PRAGMA application_id = {APPLICATION_ID + 1}")
            connection.execute("CREATE TABLE foreign_data (value TEXT)")
            connection.execute("INSERT INTO foreign_data VALUES ('keep me')")
            connection.commit()
            connection.close()
            if os.name != "nt":
                path.chmod(0o600)
            before = path.read_bytes()

            with self.assertRaises(CacheDatabaseUnavailable):
                with ContextCacheDatabase(path):
                    pass

            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(path.parent.glob(f"{path.name}.quarantine-*")), [])

    def test_open_does_not_mutate_unknown_database_active_wal_or_shm(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            writer = sqlite3.connect(path)
            try:
                writer.execute("PRAGMA journal_mode = WAL")
                writer.execute("PRAGMA wal_autocheckpoint = 0")
                writer.execute(f"PRAGMA application_id = {APPLICATION_ID + 1}")
                writer.execute("CREATE TABLE foreign_data (value TEXT)")
                writer.commit()
                storage_paths = (
                    path,
                    Path(f"{path}-wal"),
                    Path(f"{path}-shm"),
                )
                if os.name != "nt":
                    for item in storage_paths:
                        item.chmod(0o600)
                before = tuple(item.read_bytes() for item in storage_paths)

                with self.assertRaises(CacheDatabaseUnavailable):
                    with ContextCacheDatabase(path):
                        pass

                after = tuple(item.read_bytes() for item in storage_paths)
            finally:
                writer.close()

            self.assertEqual(after, before)
            self.assertEqual(list(path.parent.glob(f"{path.name}.quarantine-*")), [])

    def test_known_wal_cannot_override_unknown_main_database_identity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            source_path = directory / "source.sqlite3"
            foreign_path = directory / "context.sqlite3"
            with ContextCacheDatabase(source_path):
                source_wal = Path(f"{source_path}-wal").read_bytes()
                connection = sqlite3.connect(foreign_path)
                connection.execute(
                    f"PRAGMA application_id = {APPLICATION_ID + 1}"
                )
                connection.execute("CREATE TABLE foreign_data (value TEXT)")
                connection.execute(
                    "INSERT INTO foreign_data VALUES ('keep me')"
                )
                connection.commit()
                connection.close()
                foreign_wal = Path(f"{foreign_path}-wal")
                foreign_wal.write_bytes(source_wal)
                if os.name != "nt":
                    foreign_path.chmod(0o600)
                    foreign_wal.chmod(0o600)
                before = (foreign_path.read_bytes(), foreign_wal.read_bytes())

                with self.assertRaises(CacheDatabaseUnavailable):
                    with ContextCacheDatabase(foreign_path):
                        pass

                self.assertEqual(
                    (foreign_path.read_bytes(), foreign_wal.read_bytes()),
                    before,
                )
                self.assertFalse(Path(f"{foreign_path}-shm").exists())
                self.assertEqual(
                    list(directory.glob(f"{foreign_path.name}.quarantine-*")),
                    [],
                )

    def test_open_leaves_future_schema_version_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(path):
                pass
            connection = sqlite3.connect(path)
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
            connection.commit()
            connection.close()
            before = path.read_bytes()

            with self.assertRaises(CacheDatabaseUnavailable):
                with ContextCacheDatabase(path):
                    pass

            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(path.parent.glob(f"{path.name}.quarantine-*")), [])

    def test_known_wal_cannot_downgrade_future_main_database_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            source_path = directory / "source.sqlite3"
            future_path = directory / "context.sqlite3"
            with ContextCacheDatabase(future_path):
                pass
            connection = sqlite3.connect(future_path)
            connection.execute(
                f"PRAGMA user_version = {SCHEMA_VERSION + 1}"
            )
            connection.commit()
            connection.close()
            with ContextCacheDatabase(source_path):
                source_wal = Path(f"{source_path}-wal").read_bytes()
                future_wal = Path(f"{future_path}-wal")
                future_wal.write_bytes(source_wal)
                if os.name != "nt":
                    future_wal.chmod(0o600)
                before = (future_path.read_bytes(), future_wal.read_bytes())

                with self.assertRaises(CacheDatabaseUnavailable):
                    with ContextCacheDatabase(future_path):
                        pass

                self.assertEqual(
                    (future_path.read_bytes(), future_wal.read_bytes()),
                    before,
                )
                self.assertFalse(Path(f"{future_path}-shm").exists())
                self.assertEqual(
                    list(directory.glob(f"{future_path.name}.quarantine-*")),
                    [],
                )

    def test_open_leaves_recognized_version_zero_database_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(path):
                pass
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE legacy_payload (value TEXT)")
            connection.execute("INSERT INTO legacy_payload VALUES ('obsolete')")
            connection.execute("PRAGMA user_version = 0")
            connection.commit()
            connection.close()
            storage_paths = (
                path,
                Path(f"{path}-wal"),
                Path(f"{path}-shm"),
                Path(f"{path}-journal"),
            )
            before = tuple(
                item.read_bytes() if item.exists() else None
                for item in storage_paths
            )

            with self.assertRaises(CacheDatabaseUnavailable):
                with ContextCacheDatabase(path):
                    pass

            after = tuple(
                item.read_bytes() if item.exists() else None
                for item in storage_paths
            )
            self.assertEqual(after, before)
            self.assertEqual(list(path.parent.glob(f"{path.name}.quarantine-*")), [])

    def test_unsupported_version_stays_unavailable_after_active_opener_closes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(path) as active:
                active.connection.execute("PRAGMA user_version = 0")
                active.connection.commit()
                storage_paths = (
                    path,
                    Path(f"{path}-wal"),
                    Path(f"{path}-shm"),
                    Path(f"{path}-journal"),
                )
                before = tuple(
                    item.read_bytes() if item.exists() else None
                    for item in storage_paths
                )
                with self.assertRaises(CacheDatabaseUnavailable):
                    with ContextCacheDatabase(path):
                        pass
                after = tuple(
                    item.read_bytes() if item.exists() else None
                    for item in storage_paths
                )
                self.assertEqual(after, before)

            before = tuple(
                item.read_bytes() if item.exists() else None
                for item in storage_paths
            )
            with self.assertRaises(CacheDatabaseUnavailable):
                with ContextCacheDatabase(path):
                    pass
            self.assertEqual(tuple(
                item.read_bytes() if item.exists() else None
                for item in storage_paths
            ), before)

    def test_open_leaves_recognized_corrupt_database_and_journal_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            corrupt_bytes = _truncate_recognized_database(path)
            journal_path = Path(f"{path}-journal")
            journal_path.write_bytes(b"foreign journal sentinel")
            if os.name != "nt":
                journal_path.chmod(0o600)
            storage_paths = (
                path,
                Path(f"{path}-wal"),
                Path(f"{path}-shm"),
                journal_path,
            )
            before = tuple(
                item.read_bytes() if item.exists() else None
                for item in storage_paths
            )
            directory_before = {
                item.name: item.read_bytes()
                for item in path.parent.iterdir()
                if item.is_file()
            }

            with self.assertRaises(CacheDatabaseUnavailable):
                with ContextCacheDatabase(path):
                    pass

            self.assertEqual(tuple(
                item.read_bytes() if item.exists() else None
                for item in storage_paths
            ), before)
            self.assertEqual({
                item.name: item.read_bytes()
                for item in path.parent.iterdir()
                if item.is_file()
            }, directory_before)
            self.assertEqual(path.read_bytes(), corrupt_bytes)
            self.assertEqual(list(path.parent.glob(f"{path.name}.quarantine-*")), [])
            self.assertEqual(
                list(path.parent.glob(".cereja-context-cache-retired-*")),
                [],
            )

    def test_open_leaves_invalid_wal_and_shm_unchanged(self):
        for wal_bytes in (b"", b"!"):
            with self.subTest(wal_bytes=wal_bytes), \
                 tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / "context.sqlite3"
                with ContextCacheDatabase(path):
                    pass
                wal_path = Path(f"{path}-wal")
                shm_path = Path(f"{path}-shm")
                wal_path.write_bytes(wal_bytes)
                shm_path.write_bytes(b"foreign shm sentinel")
                if os.name != "nt":
                    for item in (wal_path, shm_path):
                        item.chmod(0o600)
                storage_paths = (path, wal_path, shm_path)
                before = tuple(item.read_bytes() for item in storage_paths)

                with self.assertRaises(CacheDatabaseUnavailable):
                    with ContextCacheDatabase(path):
                        pass

                self.assertEqual(
                    tuple(item.read_bytes() for item in storage_paths),
                    before,
                )
                self.assertEqual(
                    list(path.parent.glob(f"{path.name}.quarantine-*")), []
                )

    def test_open_leaves_valid_wal_with_invalid_shm_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            source_path = directory / "source.sqlite3"
            path = directory / "context.sqlite3"
            source = ContextCacheDatabase(source_path)
            source.__enter__()
            try:
                source.connection.execute(
                    "UPDATE namespaces SET last_access_ns = last_access_ns + 1"
                )
                source.connection.commit()
                path.write_bytes(source_path.read_bytes())
                wal_path = Path(f"{path}-wal")
                wal_path.write_bytes(Path(f"{source_path}-wal").read_bytes())
                shm_path = Path(f"{path}-shm")
                shm_path.write_bytes(b"S" * 32768)
                if os.name != "nt":
                    for item in (path, wal_path, shm_path):
                        item.chmod(0o600)
                before = tuple(
                    item.read_bytes() for item in (path, wal_path, shm_path)
                )

                with self.assertRaises(CacheDatabaseUnavailable):
                    with ContextCacheDatabase(path):
                        pass

                self.assertEqual(
                    tuple(item.read_bytes() for item in (path, wal_path, shm_path)),
                    before,
                )
            finally:
                source.__exit__(None, None, None)

    def test_open_rejects_legitimate_active_wal_and_shm_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            owner = ContextCacheDatabase(path)
            owner.__enter__()
            try:
                owner.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                wal_path = Path(f"{path}-wal")
                shm_path = Path(f"{path}-shm")
                self.assertEqual(wal_path.stat().st_size, 0)
                self.assertGreaterEqual(shm_path.stat().st_size, 136)
                before = (
                    path.read_bytes(),
                    wal_path.read_bytes(),
                    shm_path.read_bytes(),
                )

                real_connect = sqlite3.connect
                with patch(
                    "cereja.system._context.cache_db.sqlite3.connect",
                    wraps=real_connect,
                ) as connect, self.assertRaises(CacheDatabaseUnavailable):
                    with ContextCacheDatabase(path):
                        pass

                self.assertEqual(
                    (
                        path.read_bytes(),
                        wal_path.read_bytes(),
                        shm_path.read_bytes(),
                    ),
                    before,
                )
                self.assertFalse(any(
                    call.args and call.args[0] == str(path)
                    for call in connect.call_args_list
                ))
            finally:
                owner.__exit__(None, None, None)

    def test_shared_lock_does_not_bypass_existing_sidecar_rejection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(path):
                pass
            wal_path = Path(f"{path}-wal")
            shm_path = Path(f"{path}-shm")
            wal_path.write_bytes(b"")
            shm_path.write_bytes(b"S" * 32768)
            if os.name != "nt":
                wal_path.chmod(0o600)
                shm_path.chmod(0o600)
            before = (path.read_bytes(), wal_path.read_bytes(), shm_path.read_bytes())
            lock = _CachePathLock(path)
            lock.acquire(False)
            try:
                with self.assertRaises(CacheDatabaseUnavailable):
                    with ContextCacheDatabase(path):
                        pass
            finally:
                lock.release()

            self.assertEqual(
                (path.read_bytes(), wal_path.read_bytes(), shm_path.read_bytes()),
                before,
            )

    def test_open_leaves_orphan_shm_beside_valid_database_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(path):
                pass
            shm_path = Path(f"{path}-shm")
            shm_path.write_bytes(b"foreign shm sentinel")
            if os.name != "nt":
                shm_path.chmod(0o600)
            before = (path.read_bytes(), shm_path.read_bytes())

            with self.assertRaises(CacheDatabaseUnavailable):
                with ContextCacheDatabase(path):
                    pass

            self.assertEqual(
                (path.read_bytes(), shm_path.read_bytes()),
                before,
            )

    def test_open_leaves_orphan_sidecar_without_creating_database(self):
        for suffix in ("-wal", "-shm", "-journal"):
            with self.subTest(suffix=suffix), \
                 tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / "context.sqlite3"
                sidecar = Path(f"{path}{suffix}")
                sidecar.write_bytes(b"orphan sidecar sentinel")
                if os.name != "nt":
                    sidecar.chmod(0o600)
                before = sidecar.read_bytes()

                with self.assertRaises(CacheDatabaseError):
                    with ContextCacheDatabase(path):
                        pass

                self.assertFalse(path.exists())
                self.assertEqual(sidecar.read_bytes(), before)

    def test_open_leaves_empty_database_with_existing_sidecar_unchanged(self):
        for suffix in ("-wal", "-shm", "-journal"):
            with self.subTest(suffix=suffix), \
                 tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / "context.sqlite3"
                path.touch()
                sidecar = Path(f"{path}{suffix}")
                sidecar.write_bytes(b"preexisting sidecar sentinel")
                if os.name != "nt":
                    path.chmod(0o600)
                    sidecar.chmod(0o600)
                before = (path.read_bytes(), sidecar.read_bytes())

                with self.assertRaises(CacheDatabaseError):
                    with ContextCacheDatabase(path):
                        pass

                self.assertEqual(
                    (path.read_bytes(), sidecar.read_bytes()),
                    before,
                )

    def test_open_leaves_symlink_and_non_regular_targets_untouched(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            target = directory / "target.sqlite3"
            corrupt_bytes = _truncate_recognized_database(target)
            symlink = directory / "linked.sqlite3"
            try:
                symlink.symlink_to(target)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")

            with self.assertRaises(CacheDatabaseError):
                with ContextCacheDatabase(symlink):
                    pass
            with self.assertRaises(CacheDatabaseError):
                with ContextCacheDatabase(directory):
                    pass

            self.assertTrue(symlink.is_symlink())
            self.assertEqual(target.read_bytes(), corrupt_bytes)
            self.assertTrue(directory.is_dir())
            self.assertEqual(list(directory.glob("*.quarantine-*")), [])

    def test_open_migrates_valid_previous_layout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            connection = sqlite3.connect(path)
            connection.execute("PRAGMA auto_vacuum = INCREMENTAL")
            connection.execute("VACUUM")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                f"""
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
                    last_access_ns INTEGER NOT NULL,
                    scan_generation INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE namespace_roots (
                    namespace_id INTEGER NOT NULL
                        REFERENCES namespaces(id) ON DELETE CASCADE,
                    root_id INTEGER NOT NULL
                        REFERENCES roots(id) ON DELETE CASCADE,
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
                        state IN (
                            'text', 'binary_file', 'invalid_utf8', 'file_too_large'
                        )
                    ),
                    content_sha256 TEXT,
                    folded_text TEXT,
                    created_ns INTEGER NOT NULL,
                    validated_ns INTEGER NOT NULL,
                    last_access_ns INTEGER NOT NULL
                );
                CREATE TABLE root_files (
                    root_id INTEGER NOT NULL
                        REFERENCES roots(id) ON DELETE CASCADE,
                    file_id INTEGER NOT NULL
                        REFERENCES files(id) ON DELETE CASCADE,
                    relative_path TEXT NOT NULL,
                    last_seen_scan TEXT NOT NULL,
                    PRIMARY KEY (root_id, file_id)
                );
                INSERT INTO namespaces (id, name, last_access_ns)
                    VALUES (1, 'default', 1);
                INSERT INTO roots (
                    id, canonical_path, last_access_ns, scan_generation
                ) VALUES (1, 'C:/legacy', 2, 4);
                INSERT INTO namespace_roots (namespace_id, root_id)
                    VALUES (1, 1);
                """
            )
            connection.close()

            with ContextCacheDatabase(path) as database:
                root = database.connection.execute(
                    "SELECT scan_generation, scan_started_ns, scan_nonce "
                    "FROM roots WHERE canonical_path = 'C:/legacy'"
                ).fetchone()

            self.assertEqual(root, (4, 0, ""))

    def test_failed_supported_migration_rolls_back_storage_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            _create_legacy_database(path)
            storage = (
                path,
                Path(f"{path}-wal"),
                Path(f"{path}-shm"),
                Path(f"{path}-journal"),
            )
            before = tuple(
                item.read_bytes() if item.exists() else None for item in storage
            )

            with patch.object(
                ContextCacheDatabase,
                "_validate_schema_structure",
                side_effect=CacheDatabaseUnavailable("validation failed"),
            ), self.assertRaisesRegex(CacheDatabaseUnavailable, "validation failed"):
                with ContextCacheDatabase(path):
                    pass

            self.assertEqual(tuple(
                item.read_bytes() if item.exists() else None for item in storage
            ), before)
            connection = sqlite3.connect(f"file:{path}?immutable=1", uri=True)
            try:
                columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(roots)")
                }
            finally:
                connection.close()
            self.assertNotIn("scan_started_ns", columns)
            self.assertNotIn("scan_nonce", columns)

    def test_supported_migration_validates_only_before_commit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            _create_legacy_database(path)
            original = ContextCacheDatabase._validate_schema_structure
            calls = 0

            def validate(database):
                nonlocal calls
                calls += 1
                return original(database)

            with patch.object(
                ContextCacheDatabase,
                "_validate_schema_structure",
                validate,
            ):
                with ContextCacheDatabase(path):
                    pass

            self.assertEqual(calls, 1)

    def test_migration_with_existing_wal_fails_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            source_path = directory / "source.sqlite3"
            path = directory / "context.sqlite3"
            _create_legacy_database(source_path)
            source = sqlite3.connect(source_path)
            source.execute("PRAGMA wal_autocheckpoint = 0")
            source.execute("UPDATE namespaces SET last_access_ns = 2")
            source.commit()
            try:
                path.write_bytes(source_path.read_bytes())
                wal_path = Path(f"{path}-wal")
                wal_path.write_bytes(Path(f"{source_path}-wal").read_bytes())
                if os.name != "nt":
                    path.chmod(0o600)
                    wal_path.chmod(0o600)
                before = (path.read_bytes(), wal_path.read_bytes())

                with self.assertRaises(CacheDatabaseUnavailable):
                    with ContextCacheDatabase(path):
                        pass

                self.assertEqual((path.read_bytes(), wal_path.read_bytes()), before)
            finally:
                source.close()

    def test_open_leaves_current_schema_in_delete_mode_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(path):
                pass
            connection = sqlite3.connect(path)
            self.assertEqual(
                connection.execute("PRAGMA journal_mode = DELETE").fetchone()[0],
                "delete",
            )
            connection.close()
            storage = (
                path,
                Path(f"{path}-wal"),
                Path(f"{path}-shm"),
                Path(f"{path}-journal"),
            )
            before = tuple(
                item.read_bytes() if item.exists() else None for item in storage
            )

            with self.assertRaises(CacheDatabaseUnavailable):
                with ContextCacheDatabase(path):
                    pass

            self.assertEqual(tuple(
                item.read_bytes() if item.exists() else None for item in storage
            ), before)

    @unittest.skipIf(os.name == "nt", "POSIX permissions are not portable on Windows")
    def test_open_restricts_new_database_and_cache_directory_permissions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "cereja" / "context.sqlite3"
            with ContextCacheDatabase(path):
                pass
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_open_rejects_symlink_database_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            target = directory / "target.sqlite3"
            target.write_text("not a database", encoding="utf-8")
            path = directory / "context.sqlite3"
            try:
                path.symlink_to(target)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")
            with self.assertRaises(CacheDatabaseError):
                with ContextCacheDatabase(path):
                    pass

    def test_open_rejects_non_regular_database_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            with self.assertRaises(CacheDatabaseError):
                with ContextCacheDatabase(path):
                    pass

    def test_open_does_not_chmod_existing_cache_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir) / "existing"
            directory.mkdir()
            path = directory / "context.sqlite3"
            with patch("cereja.system._context.cache_db.os.chmod") as chmod:
                with ContextCacheDatabase(path):
                    pass
            chmod.assert_not_called()

    def test_open_does_not_create_missing_directory_ancestors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "missing" / "cereja" / "context.sqlite3"
            with self.assertRaises(CacheDatabaseError):
                with ContextCacheDatabase(path):
                    pass
            self.assertFalse(path.parent.parent.exists())

    def test_open_creates_only_default_windows_application_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir, \
             patch("cereja.system._context.cache_db.os.name", "nt"), \
             patch.dict(os.environ, {"LOCALAPPDATA": temp_dir}):
            path = default_cache_path()
            with ContextCacheDatabase(path):
                pass
            self.assertTrue(path.is_file())
            self.assertEqual(path.parent.parent.parent, Path(temp_dir))

    def test_open_leaves_preexisting_empty_file_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            path.touch()
            if os.name != "nt":
                path.chmod(0o600)
            before = path.read_bytes()

            with self.assertRaises(CacheDatabaseUnavailable):
                with ContextCacheDatabase(path):
                    pass

            self.assertEqual(path.read_bytes(), before)
            self.assertFalse(Path(f"{path}-wal").exists())
            self.assertFalse(Path(f"{path}-shm").exists())
            self.assertFalse(Path(f"{path}-journal").exists())

    def test_bootstrap_lock_failure_does_not_publish_empty_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            lock = _CachePathLock(path)
            lock.acquire(True)
            try:
                with self.assertRaises(CacheDatabaseUnavailable):
                    with ContextCacheDatabase(path):
                        pass
                self.assertFalse(path.exists())
            finally:
                lock.release()

            with ContextCacheDatabase(path):
                pass
            self.assertTrue(path.is_file())

    def test_bootstrap_connect_failure_does_not_poison_next_open(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            with patch(
                "cereja.system._context.cache_db.sqlite3.connect",
                side_effect=sqlite3.OperationalError("temporary failure"),
            ), self.assertRaises(CacheDatabaseUnavailable):
                with ContextCacheDatabase(path):
                    pass
            self.assertFalse(path.exists())

            with ContextCacheDatabase(path):
                pass
            self.assertTrue(path.is_file())

    def test_bootstrap_does_not_remove_database_that_appears_before_lock(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            original = ContextCacheDatabase._acquire_cache_lock
            published = []

            def acquire(database, exclusive):
                connection = sqlite3.connect(path)
                connection.execute("PRAGMA application_id = 12345")
                connection.execute("CREATE TABLE foreign_data(value TEXT)")
                connection.execute(
                    "INSERT INTO foreign_data VALUES ('keep')"
                )
                connection.commit()
                connection.close()
                if os.name != "nt":
                    path.chmod(0o600)
                published.append(path.read_bytes())
                original(database, exclusive)

            with patch.object(
                ContextCacheDatabase,
                "_acquire_cache_lock",
                acquire,
            ), self.assertRaises(CacheDatabaseUnavailable):
                with ContextCacheDatabase(path):
                    pass

            self.assertEqual(path.read_bytes(), published[0])

    def test_open_and_info_reject_altered_schema_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(path):
                pass
            connection = sqlite3.connect(path)
            connection.execute("ALTER TABLE files RENAME COLUMN folded_text TO changed_text")
            connection.commit()
            connection.close()
            storage = (
                path,
                Path(f"{path}-wal"),
                Path(f"{path}-shm"),
                Path(f"{path}-journal"),
            )
            before = tuple(
                item.read_bytes() if item.exists() else None for item in storage
            )

            with self.assertRaisesRegex(CacheDatabaseUnavailable, "schema"):
                with ContextCacheDatabase(path):
                    pass
            with self.assertRaisesRegex(CacheDatabaseUnavailable, "schema"):
                ContextCacheDatabase.read_info(path)

            self.assertEqual(tuple(
                item.read_bytes() if item.exists() else None for item in storage
            ), before)

    def test_read_info_queries_private_snapshot_even_without_wal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(path):
                pass
            queried_paths = []
            original = ContextCacheDatabase._query_info

            def query(database, *args):
                queried_paths.append(database.path)
                return original(database, *args)

            with patch.object(ContextCacheDatabase, "_query_info", query):
                info = ContextCacheDatabase.read_info(path)

            self.assertEqual(info.path, path.absolute().as_posix())
            self.assertEqual(len(queried_paths), 1)
            self.assertNotEqual(queried_paths[0], path)

    def test_open_rejects_foreign_key_corruption_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(path):
                pass
            connection = sqlite3.connect(path)
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute(
                "INSERT INTO namespace_roots (namespace_id, root_id) "
                "VALUES (999, 999)"
            )
            connection.commit()
            connection.close()
            storage = (
                path,
                Path(f"{path}-wal"),
                Path(f"{path}-shm"),
                Path(f"{path}-journal"),
            )
            before = tuple(
                item.read_bytes() if item.exists() else None for item in storage
            )

            with self.assertRaises(CacheDatabaseUnavailable):
                with ContextCacheDatabase(path):
                    pass

            self.assertEqual(tuple(
                item.read_bytes() if item.exists() else None for item in storage
            ), before)

    def test_open_rejects_schema_without_default_namespace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(path):
                pass
            connection = sqlite3.connect(path)
            connection.execute("DELETE FROM namespaces WHERE name = 'default'")
            connection.commit()
            connection.close()
            with self.assertRaisesRegex(CacheDatabaseError, "namespace"):
                with ContextCacheDatabase(path):
                    pass

    def test_open_rejects_schema_without_declared_unique_constraint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(path):
                pass
            connection = sqlite3.connect(path)
            sql = connection.execute(
                "SELECT sql FROM sqlite_master WHERE name = 'namespaces'"
            ).fetchone()[0]
            connection.execute("PRAGMA writable_schema = ON")
            connection.execute(
                "UPDATE sqlite_master SET sql = ? WHERE name = 'namespaces'",
                (sql.replace("name TEXT NOT NULL UNIQUE", "name TEXT NOT NULL"),),
            )
            version = connection.execute("PRAGMA schema_version").fetchone()[0]
            connection.execute(f"PRAGMA schema_version = {version + 1}")
            connection.commit()
            connection.close()
            with self.assertRaises(CacheDatabaseError):
                with ContextCacheDatabase(path):
                    pass

    def test_open_rejects_schema_with_altered_state_constraint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(path):
                pass
            connection = sqlite3.connect(path)
            sql = connection.execute(
                "SELECT sql FROM sqlite_master WHERE name = 'files'"
            ).fetchone()[0]
            connection.execute("PRAGMA writable_schema = ON")
            connection.execute(
                "UPDATE sqlite_master SET sql = ? WHERE name = 'files'",
                (sql.replace("'file_too_large')", "'file_too_large', 'extra')"),),
            )
            version = connection.execute("PRAGMA schema_version").fetchone()[0]
            connection.execute(f"PRAGMA schema_version = {version + 1}")
            connection.commit()
            connection.close()
            with self.assertRaisesRegex(CacheDatabaseError, "schema"):
                with ContextCacheDatabase(path):
                    pass

    def test_open_rejects_schema_with_altered_collation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(path):
                pass
            connection = sqlite3.connect(path)
            sql = connection.execute(
                "SELECT sql FROM sqlite_master WHERE name = 'metadata'"
            ).fetchone()[0]
            connection.execute("PRAGMA writable_schema = ON")
            connection.execute(
                "UPDATE sqlite_master SET sql = ? WHERE name = 'metadata'",
                (sql.replace("value TEXT NOT NULL", "value TEXT COLLATE NOCASE NOT NULL"),),
            )
            version = connection.execute("PRAGMA schema_version").fetchone()[0]
            connection.execute(f"PRAGMA schema_version = {version + 1}")
            connection.commit()
            connection.close()
            with self.assertRaisesRegex(CacheDatabaseError, "schema"):
                with ContextCacheDatabase(path):
                    pass

    def test_posix_open_does_not_change_process_umask(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            with patch("cereja.system._context.cache_db.os.umask") as umask:
                with ContextCacheDatabase(path):
                    pass
            umask.assert_not_called()

    @unittest.skipIf(os.name == "nt", "POSIX file modes are not portable on Windows")
    def test_posix_bootstrap_fchmods_database_before_sqlite_open(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            with patch("cereja.system._context.cache_db.os.fchmod",
                       wraps=os.fchmod) as fchmod:
                with ContextCacheDatabase(path):
                    pass
            self.assertTrue(any(call.args[1] == 0o600 for call in fchmod.call_args_list))

    @unittest.skipIf(os.name == "nt", "POSIX sidecar modes are not portable on Windows")
    def test_posix_bootstrap_restricts_real_sqlite_sidecars(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(path):
                sidecars = [item for item in (
                    Path(f"{path}-wal"), Path(f"{path}-shm")
                ) if item.exists()]
                self.assertTrue(sidecars)
                self.assertTrue(all(
                    stat.S_IMODE(item.stat().st_mode) == 0o600
                    for item in sidecars
                ))

    def test_open_rejects_existing_valid_wal_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            source_path = directory / "source.sqlite3"
            path = directory / "context.sqlite3"
            owner = ContextCacheDatabase(source_path)
            owner.__enter__()
            try:
                owner.connection.execute(
                    "UPDATE namespaces SET last_access_ns = last_access_ns + 1"
                )
                owner.connection.commit()
                sidecar = Path(f"{path}-wal")
                path.write_bytes(source_path.read_bytes())
                sidecar.write_bytes(Path(f"{source_path}-wal").read_bytes())
                if os.name != "nt":
                    path.chmod(0o600)
                    sidecar.chmod(0o600)
                before = (path.read_bytes(), sidecar.read_bytes())

                with self.assertRaises(CacheDatabaseUnavailable):
                    with ContextCacheDatabase(path):
                        pass

                self.assertEqual(
                    (path.read_bytes(), sidecar.read_bytes()), before
                )
            finally:
                owner.__exit__(None, None, None)

    def test_open_prevents_rollback_journal_injection_before_connect(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(path):
                pass
            before = path.read_bytes()
            journal = Path(f"{path}-journal")
            real_connect = sqlite3.connect
            attempted = False

            def connect(*args, **kwargs):
                nonlocal attempted
                if args and args[0] == str(path):
                    attempted = True
                    journal.write_bytes(b"J" * 512)
                return real_connect(*args, **kwargs)

            with patch(
                "cereja.system._context.cache_db.sqlite3.connect",
                side_effect=connect,
            ), self.assertRaises(CacheDatabaseUnavailable):
                with ContextCacheDatabase(path):
                    pass

            self.assertTrue(attempted)
            self.assertEqual(path.read_bytes(), before)
            self.assertFalse(journal.exists())

    def test_open_rejects_sidecar_created_after_preflight_before_connect(self):
        for suffix in ("-wal", "-shm"):
            with self.subTest(suffix=suffix), \
                 tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / "context.sqlite3"
                with ContextCacheDatabase(path):
                    pass
                main_before = path.read_bytes()
                sidecar = Path(f"{path}{suffix}")
                sentinel = f"injected {suffix}".encode()
                reserve = ContextCacheDatabase._reserve_rollback_journal

                def reserve_then_inject(database):
                    reservation = reserve(database)
                    sidecar.write_bytes(sentinel)
                    if os.name != "nt":
                        sidecar.chmod(0o600)
                    return reservation

                real_connect = sqlite3.connect
                with patch.object(
                    ContextCacheDatabase,
                    "_reserve_rollback_journal",
                    reserve_then_inject,
                ), patch(
                    "cereja.system._context.cache_db.sqlite3.connect",
                    wraps=real_connect,
                ) as connect, self.assertRaises(CacheDatabaseUnavailable):
                    with ContextCacheDatabase(path):
                        pass

                self.assertEqual(path.read_bytes(), main_before)
                self.assertEqual(sidecar.read_bytes(), sentinel)
                self.assertFalse(any(
                    call.args and call.args[0] == str(path)
                    for call in connect.call_args_list
                ))

    def test_open_rejects_unexpected_sqlite_schema_objects(self):
        statements = (
            "CREATE VIEW unexpected_view AS SELECT 1",
            "CREATE TRIGGER unexpected_trigger AFTER INSERT ON metadata BEGIN SELECT 1; END",
            "CREATE INDEX unexpected_index ON namespaces(last_access_ns)",
        )
        for statement in statements:
            with self.subTest(statement=statement), tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / "context.sqlite3"
                with ContextCacheDatabase(path):
                    pass
                connection = sqlite3.connect(path)
                connection.execute(statement)
                connection.commit()
                connection.close()
                with self.assertRaisesRegex(CacheDatabaseError, "schema"):
                    with ContextCacheDatabase(path):
                        pass

    def test_open_rejects_symlink_cache_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "target"
            target.mkdir()
            directory = root / "cache"
            try:
                directory.symlink_to(target, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"directory symlinks unavailable: {error}")
            with self.assertRaises(CacheDatabaseError):
                with ContextCacheDatabase(directory / "context.sqlite3"):
                    pass

    def test_open_rejects_schema_with_non_incremental_vacuum(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            connection = sqlite3.connect(path)
            connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.close()
            with self.assertRaisesRegex(CacheDatabaseError, "auto_vacuum"):
                with ContextCacheDatabase(path):
                    pass

    def test_open_aborts_when_file_identity_changes_after_connect(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(path):
                pass
            original_identity = ContextCacheDatabase._identity
            real_connect = sqlite3.connect
            source_connected = False

            def changed_identity(candidate):
                identity = original_identity(candidate)
                if candidate == path and source_connected:
                    return identity[0], identity[1] + 1
                return identity

            def connect(*args, **kwargs):
                nonlocal source_connected
                connection = real_connect(*args, **kwargs)
                if args and args[0] == str(path):
                    source_connected = True
                return connection

            with patch.object(ContextCacheDatabase, "_identity",
                              side_effect=changed_identity), \
                 patch("cereja.system._context.cache_db.sqlite3.connect",
                       side_effect=connect):
                with self.assertRaisesRegex(CacheDatabaseError, "identity"):
                    with ContextCacheDatabase(path):
                        pass
            self.assertTrue(source_connected)


if __name__ == "__main__":
    unittest.main()
