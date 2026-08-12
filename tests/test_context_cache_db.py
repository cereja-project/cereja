import os
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cereja.system._context.cache_db import (
    APPLICATION_ID,
    BUSY_TIMEOUT_MS,
    SCHEMA_VERSION,
    CacheDatabaseError,
    CacheMaintenanceReport,
    CachedFile,
    ContextCacheDatabase,
    FileSignature,
    default_cache_path,
)


class ContextCacheDatabaseTest(unittest.TestCase):
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
                quota = database.aggregate_size_bytes() + 1

                admitted = database.commit_scan(
                    scan, [], max_bytes=quota
                )

                self.assertIsNone(admitted)
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

                    admitted = database.commit_scan(
                        scan, [], max_bytes=10 ** 9
                    )
                finally:
                    reader.close()

                self.assertIsNone(admitted)
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

    def test_new_scan_invalidates_older_token_for_the_same_root(self):
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
            with ContextCacheDatabase(database_path) as database:
                old_scan = database.begin_scan("default", "C:/repo")
                new_scan = database.begin_scan("default", "C:/repo")
                database.commit_scan(new_scan, [new_file])
                with self.assertRaises(CacheDatabaseError):
                    database.commit_scan(old_scan, [old_file])
                rows = list(database.iter_root_files("default", "C:/repo"))
            self.assertEqual([row.folded_text for row in rows], ["new"])

    def test_new_scan_in_another_connection_invalidates_older_token(self):
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
            with ContextCacheDatabase(database_path) as first, \
                 ContextCacheDatabase(database_path) as second:
                old_scan = first.begin_scan("default", "C:/repo")
                new_scan = second.begin_scan("default", "C:/repo")
                second.commit_scan(new_scan, [new_file])
                with self.assertRaises(CacheDatabaseError):
                    first.commit_scan(old_scan, [old_file])
                rows = list(first.iter_root_files("default", "C:/repo"))
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

    def test_open_bootstraps_preexisting_empty_file_with_incremental_vacuum(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            path.touch()
            if os.name != "nt":
                path.chmod(0o600)
            with ContextCacheDatabase(path) as database:
                self.assertEqual(
                    database.connection.execute("PRAGMA auto_vacuum").fetchone()[0], 2
                )

    def test_open_rejects_schema_with_altered_column(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(path):
                pass
            connection = sqlite3.connect(path)
            connection.execute("ALTER TABLE files RENAME COLUMN folded_text TO changed_text")
            connection.commit()
            connection.close()
            with self.assertRaisesRegex(CacheDatabaseError, "schema"):
                with ContextCacheDatabase(path):
                    pass

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

    def test_open_rejects_preexisting_sidecar_replaced_during_open(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            with ContextCacheDatabase(path):
                pass
            sidecar = Path(f"{path}-wal")
            sidecar.touch()
            if os.name != "nt":
                sidecar.chmod(0o600)

            def replace_sidecar(database, database_is_empty):
                replacement = path.parent / "replacement-wal"
                replacement.touch()
                if os.name != "nt":
                    replacement.chmod(0o600)
                replacement.replace(sidecar)

            with patch.object(ContextCacheDatabase, "_configure_connection",
                              replace_sidecar):
                with self.assertRaisesRegex(CacheDatabaseError, "sidecar.*identity"):
                    with ContextCacheDatabase(path):
                        pass

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
            connection.close()
            with self.assertRaisesRegex(CacheDatabaseError, "auto_vacuum"):
                with ContextCacheDatabase(path):
                    pass

    def test_open_aborts_when_file_identity_changes_after_connect(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            path.touch()
            if os.name != "nt":
                path.chmod(0o600)
            original_identity = ContextCacheDatabase._identity
            calls = 0

            def changed_identity(candidate):
                nonlocal calls
                identity = original_identity(candidate)
                if candidate == path:
                    calls += 1
                    if calls > 1:
                        return identity[0], identity[1] + 1
                return identity

            with patch.object(
                ContextCacheDatabase, "_identity", side_effect=changed_identity
            ):
                with self.assertRaisesRegex(CacheDatabaseError, "identity"):
                    with ContextCacheDatabase(path):
                        pass


if __name__ == "__main__":
    unittest.main()
