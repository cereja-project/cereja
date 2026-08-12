import os
import sqlite3
import tempfile
import unittest
import warnings
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

import cereja.system as system_module
from cereja.system import list_text_context, search_text_context
from cereja.system._context import cache as cache_module
from cereja.system._context.cache_db import (
    DEFAULT_NAMESPACE,
    CacheDatabaseUnavailable,
    ContextCacheDatabase,
)
from cereja.system._context.models import ContextCacheWarning


class ContextCacheTest(unittest.TestCase):
    def test_cache_unavailable_is_exported_through_public_facade(self):
        self.assertIs(
            system_module.CacheDatabaseUnavailable,
            CacheDatabaseUnavailable,
        )

    def test_info_reports_metadata_without_content(self):
        self.assertTrue(hasattr(system_module, "get_context_cache_info"))
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "context.sqlite3"
            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ):
                info = system_module.get_context_cache_info()
            self.assertEqual(info.path, cache_path.absolute().as_posix())
            self.assertEqual(info.schema_version, 1)
            self.assertEqual(info.namespace, "default")
            self.assertEqual(info.database_bytes, 0)
            self.assertEqual(info.wal_bytes, 0)
            self.assertEqual(info.shm_bytes, 0)
            self.assertEqual(info.roots, 0)
            self.assertEqual(info.files, 0)
            self.assertEqual(info.text_files, 0)
            self.assertEqual(info.skipped_files, 0)
            self.assertIsNone(info.last_access_ns)
            self.assertFalse(hasattr(info, "folded_text"))
            self.assertFalse(cache_path.exists())
            with self.assertRaises(FrozenInstanceError):
                info.files = 1

    def test_info_reads_existing_cache_without_mutating_storage(self):
        self.assertTrue(hasattr(system_module, "get_context_cache_info"))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            (root / "guide.md").write_text("needle", encoding="utf-8")
            (root / "binary.bin").write_bytes(b"\x00binary")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ):
                search_text_context([root], "needle", cache=True)
                storage_paths = (
                    cache_path,
                    Path(f"{cache_path}-wal"),
                    Path(f"{cache_path}-shm"),
                )
                before = tuple(
                    item.read_bytes() if item.exists() else None
                    for item in storage_paths
                )
                info = system_module.get_context_cache_info()
                after = tuple(
                    item.read_bytes() if item.exists() else None
                    for item in storage_paths
                )
            self.assertIsInstance(info, system_module.ContextCacheInfo)
            self.assertEqual(info.database_bytes, cache_path.stat().st_size)
            self.assertEqual(info.wal_bytes, 0)
            self.assertEqual(info.shm_bytes, 0)
            self.assertEqual(info.roots, 1)
            self.assertEqual(info.files, 2)
            self.assertEqual(info.text_files, 1)
            self.assertEqual(info.skipped_files, 1)
            self.assertIsInstance(info.last_access_ns, int)
            self.assertEqual(after, before)

    def test_info_rejects_unknown_main_before_creating_shared_memory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            source_path = directory / "source.sqlite3"
            cache_path = directory / "context.sqlite3"
            with ContextCacheDatabase(source_path):
                source_wal = Path(f"{source_path}-wal").read_bytes()
                connection = sqlite3.connect(cache_path)
                connection.execute("PRAGMA application_id = 12345")
                connection.execute("CREATE TABLE foreign_data (value TEXT)")
                connection.commit()
                connection.close()
                cache_wal = Path(f"{cache_path}-wal")
                cache_wal.write_bytes(source_wal)
                if os.name != "nt":
                    cache_path.chmod(0o600)
                    cache_wal.chmod(0o600)
                before = (cache_path.read_bytes(), cache_wal.read_bytes())
                with patch(
                    "cereja.system._context.cache.default_cache_path",
                    return_value=cache_path,
                ), self.assertRaises(CacheDatabaseUnavailable):
                    system_module.get_context_cache_info()

                self.assertEqual(
                    (cache_path.read_bytes(), cache_wal.read_bytes()), before
                )
                self.assertFalse(Path(f"{cache_path}-shm").exists())

    def test_info_with_wal_uses_private_snapshot_without_storage_mutation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            source_path = directory / "source.sqlite3"
            cache_path = directory / "context.sqlite3"
            with ContextCacheDatabase(source_path) as source:
                source.connection.execute(
                    "INSERT INTO metadata VALUES ('marker', 'value')"
                )
                source.connection.commit()
                cache_path.write_bytes(source_path.read_bytes())
                cache_wal = Path(f"{cache_path}-wal")
                cache_wal.write_bytes(
                    Path(f"{source_path}-wal").read_bytes()
                )
            if os.name != "nt":
                cache_path.chmod(0o600)
                cache_wal.chmod(0o600)
            before = {
                item.name: item.read_bytes()
                for item in directory.iterdir()
                if item.name.startswith(cache_path.name)
            }

            info = ContextCacheDatabase.read_info(cache_path)

            after = {
                item.name: item.read_bytes()
                for item in directory.iterdir()
                if item.name.startswith(cache_path.name)
            }
            self.assertEqual(info.wal_bytes, len(before[cache_wal.name]))
            self.assertEqual(after, before)

    def test_clear_returns_physical_size_report(self):
        self.assertTrue(hasattr(system_module, "clear_context_cache"))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            (root / "guide.md").write_text("needle", encoding="utf-8")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ):
                search_text_context([root], "needle", cache=True)
                report = system_module.clear_context_cache()
            self.assertIsInstance(report, system_module.ContextCacheClearReport)
            self.assertGreaterEqual(report.before_bytes, report.after_bytes)
            self.assertGreaterEqual(report.associations_removed, 1)
            self.assertGreaterEqual(report.roots_removed, 1)
            self.assertGreaterEqual(report.files_removed, 1)
            with self.assertRaises(FrozenInstanceError):
                report.files_removed = 0

    def test_clear_missing_cache_returns_zero_report_without_creating_it(self):
        self.assertTrue(hasattr(system_module, "clear_context_cache"))
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "missing" / "context.sqlite3"
            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ):
                report = system_module.clear_context_cache()
            self.assertEqual(
                report,
                system_module.ContextCacheClearReport(0, 0, 0, 0, 0),
            )
            self.assertFalse(cache_path.exists())

    def test_clear_removes_only_default_namespace_associations(self):
        self.assertTrue(hasattr(system_module, "clear_context_cache"))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            (root / "guide.md").write_text("needle", encoding="utf-8")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ):
                search_text_context([root], "needle", cache=True)
                with ContextCacheDatabase(cache_path) as database:
                    database.connection.execute(
                        "INSERT INTO namespaces (name, last_access_ns) VALUES ('other', 1)"
                    )
                    database.connection.execute(
                        """INSERT INTO namespace_roots (namespace_id, root_id)
                           SELECT n.id, r.id FROM namespaces AS n, roots AS r
                           WHERE n.name = 'other'"""
                    )
                    database.connection.commit()
                report = system_module.clear_context_cache()
            with ContextCacheDatabase(cache_path) as database:
                associations = database.connection.execute(
                    """SELECT n.name, COUNT(nr.root_id)
                       FROM namespaces AS n
                       LEFT JOIN namespace_roots AS nr ON nr.namespace_id = n.id
                       GROUP BY n.name ORDER BY n.name"""
                ).fetchall()
                roots = database.connection.execute(
                    "SELECT COUNT(*) FROM roots"
                ).fetchone()[0]
                files = database.connection.execute(
                    "SELECT COUNT(*) FROM files"
                ).fetchone()[0]
            self.assertEqual(report.associations_removed, 1)
            self.assertEqual(report.roots_removed, 0)
            self.assertEqual(report.files_removed, 0)
            self.assertEqual(associations, [("default", 0), ("other", 1)])
            self.assertEqual(roots, 1)
            self.assertEqual(files, 1)

    def test_clear_lock_failure_raises_without_cache_warning(self):
        self.assertTrue(hasattr(system_module, "clear_context_cache"))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            (root / "guide.md").write_text("needle", encoding="utf-8")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ):
                search_text_context([root], "needle", cache=True)
                blocker = sqlite3.connect(cache_path, timeout=0)
                try:
                    blocker.execute("BEGIN IMMEDIATE")
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter("always")
                        with self.assertRaises(CacheDatabaseUnavailable):
                            system_module.clear_context_cache()
                finally:
                    blocker.rollback()
                    blocker.close()
            self.assertFalse(any(
                item.category is ContextCacheWarning for item in caught
            ))

    def test_clear_succeeds_when_post_commit_checkpoint_reports_busy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            (root / "guide.md").write_text("needle", encoding="utf-8")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ):
                search_text_context([root], "needle", cache=True)
                with patch.object(
                    ContextCacheDatabase,
                    "_checkpoint_wal",
                    return_value=(1, 0, 0),
                ):
                    report = system_module.clear_context_cache()

            self.assertEqual(report.associations_removed, 1)
            with ContextCacheDatabase(cache_path) as database:
                self.assertEqual(
                    database.connection.execute(
                        "SELECT COUNT(*) FROM namespace_roots"
                    ).fetchone()[0],
                    0,
                )

    def test_clear_succeeds_when_post_commit_checkpoint_raises_locked(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            (root / "guide.md").write_text("needle", encoding="utf-8")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ):
                search_text_context([root], "needle", cache=True)
                with patch.object(
                    ContextCacheDatabase,
                    "_checkpoint_wal",
                    side_effect=sqlite3.OperationalError("database is locked"),
                ):
                    report = system_module.clear_context_cache()

            self.assertEqual(report.associations_removed, 1)
            with ContextCacheDatabase(cache_path) as database:
                self.assertEqual(
                    database.connection.execute(
                        "SELECT COUNT(*) FROM namespace_roots"
                    ).fetchone()[0],
                    0,
                )

    def test_clear_succeeds_when_lock_restore_fails_after_commit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            (root / "guide.md").write_text("needle", encoding="utf-8")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ):
                search_text_context([root], "needle", cache=True)
                with patch.object(
                    ContextCacheDatabase,
                    "_restore_normal_locking",
                    side_effect=sqlite3.OperationalError("restore failed"),
                ):
                    report = system_module.clear_context_cache()

            self.assertEqual(report.associations_removed, 1)
            with ContextCacheDatabase(cache_path) as database:
                self.assertEqual(
                    database.connection.execute(
                        "SELECT COUNT(*) FROM namespace_roots"
                    ).fetchone()[0],
                    0,
                )

    def test_cold_and_warm_cache_equal_direct_response(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            (root / "guide.md").write_text("Auth cache\n", encoding="utf-8")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ):
                direct = search_text_context([root], "auth cache")
                cold = search_text_context([root], "auth cache", cache=True)
                warm = search_text_context([root], "auth cache", cache=True)
            self.assertEqual(cold, direct)
            self.assertEqual(warm, direct)
            self.assertTrue(cache_path.exists())

    def test_warm_cache_reopens_only_selected_winner_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            (root / "auth.txt").write_text("Auth cache", encoding="utf-8")
            (root / "other.txt").write_text("unrelated", encoding="utf-8")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ):
                search_text_context([root], "auth", cache=True)
                original_read = cache_module._read_original_text
                reads = []

                def recording_read(path, max_file_bytes):
                    reads.append(Path(path).name)
                    return original_read(path, max_file_bytes)

                with patch(
                    "cereja.system._context.cache._read_original_text",
                    side_effect=recording_read,
                ):
                    response = search_text_context([root], "auth", cache=True)
            self.assertEqual(response.results[0].snippets[0].text, "Auth cache")
            self.assertEqual(reads, ["auth.txt"])

    def test_casefold_length_change_preserves_direct_truncation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            (root / "eszett.txt").write_text("ß", encoding="utf-8")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ):
                cached = search_text_context(
                    [root], "ss", cache=True, max_snippet_chars=1
                )
            direct = search_text_context(
                [root], "ss", max_snippet_chars=1
            )
            self.assertEqual(cached, direct)

    def test_file_shared_by_multiple_roots_remains_a_warm_hit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            outer = Path(temp_dir) / "repo"
            inner = outer / "nested"
            inner.mkdir(parents=True)
            (inner / "shared.txt").write_text("needle", encoding="utf-8")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ):
                search_text_context([outer], "missing", cache=True)
                search_text_context([inner], "missing", cache=True)
                reads = self._record_cache_reads(
                    lambda: search_text_context([outer], "missing", cache=True)
                )
            self.assertEqual(reads, [])

    def test_database_lock_warns_and_falls_back_to_direct_search(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "guide.md").write_text("needle", encoding="utf-8")
            with patch(
                "cereja.system._context.cache.ContextCacheDatabase.__enter__",
                side_effect=CacheDatabaseUnavailable("locked"),
            ), warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                response = search_text_context([root], "needle", cache=True)
            self.assertEqual(
                [item.relative_path for item in response.results], ["guide.md"]
            )
            self.assertTrue(
                any(item.category is ContextCacheWarning for item in caught)
            )

    def test_database_fallback_reuses_materialized_root_generator(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "guide.md").write_text("needle", encoding="utf-8")
            roots = (item for item in [root])
            with patch(
                "cereja.system._context.cache.ContextCacheDatabase.__enter__",
                side_effect=CacheDatabaseUnavailable("locked"),
            ), warnings.catch_warnings():
                warnings.simplefilter("ignore")
                response = search_text_context(roots, "needle", cache=True)
            self.assertEqual(
                [item.relative_path for item in response.results], ["guide.md"]
            )

    def test_database_fallback_reuses_materialized_extensions_generator(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "guide.md").write_text("needle", encoding="utf-8")
            (root / "other.txt").write_text("needle", encoding="utf-8")
            extensions = (item for item in ["md"])
            with patch(
                "cereja.system._context.cache.ContextCacheDatabase.__enter__",
                side_effect=CacheDatabaseUnavailable("locked"),
            ), warnings.catch_warnings():
                warnings.simplefilter("ignore")
                response = search_text_context(
                    [root], "needle", cache=True, extensions=extensions
                )
            self.assertEqual(
                [item.relative_path for item in response.results], ["guide.md"]
            )

    def test_mutation_lifecycle_remains_equal_to_direct_search(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            guide = root / "guide.md"
            guide.write_text("alpha", encoding="utf-8")

            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ):
                self._assert_cached_equals_direct(root, "alpha")

                added = root / "added.txt"
                added.write_text("alpha added", encoding="utf-8")
                self._assert_cached_equals_direct(root, "alpha")

                guide.write_text("bravo", encoding="utf-8")
                self._assert_cached_equals_direct(root, "bravo")

                renamed = root / "renamed.txt"
                added.rename(renamed)
                self._assert_cached_equals_direct(root, "alpha")

                renamed.unlink()
                self._assert_cached_equals_direct(root, "alpha")

                ignored = root / "ignored.txt"
                ignored.write_text("alpha ignored", encoding="utf-8")
                self._assert_cached_equals_direct(root, "alpha")
                (root / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
                self._assert_cached_equals_direct(root, "alpha")

                extension_response = search_text_context(
                    [root], "bravo", cache=True, extensions=["txt"]
                )
                extension_direct = search_text_context(
                    [root], "bravo", extensions=["txt"]
                )
                self.assertEqual(extension_response, extension_direct)

    def test_same_size_timestamp_change_and_refresh_force_reprocessing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            changed = root / "changed.txt"
            stable = root / "stable.txt"
            changed.write_text("alpha", encoding="utf-8")
            stable.write_text("stable", encoding="utf-8")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ):
                search_text_context([root], "missing", cache=True)
                previous = changed.stat().st_mtime_ns
                changed.write_text("bravo", encoding="utf-8")
                os.utime(changed, ns=(previous + 1_000_000, previous + 1_000_000))
                reads = self._record_cache_reads(
                    lambda: search_text_context([root], "missing", cache=True)
                )
                self.assertEqual(reads, ["changed.txt"])

                refreshed_reads = self._record_cache_reads(
                    lambda: search_text_context(
                        [root], "missing", cache=True, refresh_cache=True
                    )
                )
                self.assertEqual(refreshed_reads, ["changed.txt", "stable.txt"])

    def test_transient_read_failure_is_reported_but_not_persisted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            target = root / "target.txt"
            target.write_text("needle", encoding="utf-8")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            original_read = cache_module._read_cacheable_file
            failed_once = False

            def transient_read(path, signature, max_file_bytes):
                nonlocal failed_once
                if Path(path).name == "target.txt" and not failed_once:
                    failed_once = True
                    raise FileNotFoundError(path)
                return original_read(path, signature, max_file_bytes)

            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ), patch(
                "cereja.system._context.cache._read_cacheable_file",
                side_effect=transient_read,
            ):
                first = search_text_context([root], "needle", cache=True)
                second = search_text_context([root], "needle", cache=True)
            self.assertEqual(first.results, ())
            self.assertEqual(first.skipped[0].reason, "disappeared")
            self.assertEqual(second.results[0].relative_path, "target.txt")

    def test_failed_inventory_does_not_destructively_synchronize_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            target = root / "target.txt"
            target.write_text("needle", encoding="utf-8")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ):
                search_text_context([root], "needle", cache=True)
                target.unlink()

                def failing_inventory(*args, **kwargs):
                    raise OSError("inventory failed")
                    yield

                with patch(
                    "cereja.system._context.cache.iter_repository_files",
                    side_effect=failing_inventory,
                ):
                    with self.assertRaisesRegex(OSError, "inventory failed"):
                        search_text_context([root], "needle", cache=True)

            with ContextCacheDatabase(cache_path) as database:
                cached = tuple(database.iter_root_files(
                    DEFAULT_NAMESPACE, cache_module._canonical_path(root)
                ))
            self.assertEqual([item.relative_path for item in cached], ["target.txt"])

    def test_quota_preserves_all_active_overlapping_roots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            outer = Path(temp_dir) / "repo"
            inner = outer / "nested"
            inner.mkdir(parents=True)
            (outer / "outer.txt").write_text("needle", encoding="utf-8")
            (inner / "inner.txt").write_text("needle", encoding="utf-8")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            with ContextCacheDatabase(cache_path) as database:
                database._checkpoint_wal()
                baseline = database.aggregate_size_bytes()
            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ), patch(
                "cereja.system._context.cache.DEFAULT_MAX_BYTES",
                baseline * 2 + 100_000,
            ):
                cached = search_text_context([outer, inner], "needle", cache=True)
            direct = search_text_context([outer, inner], "needle")
            self.assertEqual(cached, direct)

            with ContextCacheDatabase(cache_path) as database:
                roots = {
                    row[0] for row in database.connection.execute(
                        "SELECT canonical_path FROM roots"
                    )
                }
            self.assertEqual(
                roots,
                {
                    cache_module._canonical_path(outer),
                    cache_module._canonical_path(inner),
                },
            )

    def test_quota_admits_deterministic_prefix_and_keeps_cold_response_complete(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            names = [f"{index}.txt" for index in range(8)]
            for index, name in enumerate(names):
                (root / name).write_text(
                    ("unrelated" if index < 4 else "needle")
                    + f" {index} " + chr(65 + index) * 12_000,
                    encoding="utf-8",
                )
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            with ContextCacheDatabase(cache_path) as database:
                database.enforce_quota((), max_bytes=10 ** 9)
                baseline = database.aggregate_size_bytes()
            quota = baseline * 2 + 40_000

            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ), patch("cereja.system._context.cache.DEFAULT_MAX_BYTES", quota):
                cold = search_text_context(
                    [root], "needle", cache=True, max_results=20
                )
                direct = search_text_context([root], "needle", max_results=20)
                self.assertEqual(cold, direct)

                with ContextCacheDatabase(cache_path) as database:
                    persisted = tuple(row[0] for row in database.connection.execute(
                        """SELECT rf.relative_path
                           FROM root_files AS rf
                           JOIN roots AS r ON r.id = rf.root_id
                           WHERE r.canonical_path = ?
                           ORDER BY rf.relative_path""",
                        (cache_module._canonical_path(root),),
                    ))
                    database._checkpoint_wal()
                    aggregate = database.aggregate_size_bytes()
                self.assertGreater(len(persisted), 0)
                self.assertLess(len(persisted), len(names))
                self.assertLessEqual(aggregate, quota)
                self.assertEqual(
                    list(persisted),
                    names[:len(persisted)],
                )

                reads = self._record_cache_reads(
                    lambda: search_text_context(
                        [root], "needle", cache=True, max_results=20
                    )
                )
                warm = search_text_context(
                    [root], "needle", cache=True, max_results=20
                )
            self.assertEqual(warm, direct)
            self.assertEqual(reads, names[len(persisted):])

    def test_busy_checkpoint_repeated_calls_do_not_mutate_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            (root / "guide.txt").write_text("needle", encoding="utf-8")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            with ContextCacheDatabase(cache_path) as database:
                database._checkpoint_wal()
                reader = sqlite3.connect(cache_path)
                try:
                    reader.execute("BEGIN")
                    reader.execute("SELECT COUNT(*) FROM roots").fetchone()
                    seed = database.begin_scan(DEFAULT_NAMESPACE, "C:/seed")
                    database.commit_scan(seed, [])
                    baseline = database.aggregate_size_bytes()

                    with patch(
                        "cereja.system._context.cache.default_cache_path",
                        return_value=cache_path,
                    ), patch(
                        "cereja.system._context.cache.DEFAULT_MAX_BYTES",
                        baseline + 1_000_000,
                    ):
                        for _ in range(8):
                            response = search_text_context(
                                [root], "needle", cache=True
                            )
                            self.assertEqual(
                                response.results[0].relative_path, "guide.txt"
                            )

                    self.assertEqual(database.aggregate_size_bytes(), baseline)
                    self.assertIsNone(database.connection.execute(
                        "SELECT id FROM roots WHERE canonical_path = ?",
                        (cache_module._canonical_path(root),),
                    ).fetchone())
                finally:
                    reader.close()

    def test_full_overhead_skips_hundreds_of_empty_root_scans(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            with ContextCacheDatabase(cache_path) as database:
                database._checkpoint_wal()
                quota = database.aggregate_size_bytes()
            roots = []
            for index in range(200):
                root = Path(temp_dir) / "roots" / str(index)
                root.mkdir(parents=True)
                roots.append(root)

            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ), patch("cereja.system._context.cache.DEFAULT_MAX_BYTES", quota):
                for root in roots:
                    response = list_text_context([root], cache=True)
                    self.assertEqual(response.results, ())

            with ContextCacheDatabase(cache_path) as database:
                database._checkpoint_wal()
                self.assertEqual(
                    database.connection.execute(
                        "SELECT COUNT(*) FROM roots"
                    ).fetchone()[0],
                    0,
                )
                self.assertLessEqual(database.aggregate_size_bytes(), quota)

    def test_warm_empty_root_is_read_only_when_quota_has_space(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "empty"
            root.mkdir()
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ):
                list_text_context([root], cache=True)
                with ContextCacheDatabase(cache_path) as database:
                    database._checkpoint_wal()
                    baseline = database.aggregate_size_bytes()
                    generation = database.connection.execute(
                        "SELECT scan_generation FROM roots WHERE canonical_path = ?",
                        (cache_module._canonical_path(root),),
                    ).fetchone()[0]

                for _ in range(8):
                    list_text_context([root], cache=True)

            with ContextCacheDatabase(cache_path) as database:
                database._checkpoint_wal()
                self.assertEqual(database.aggregate_size_bytes(), baseline)
                self.assertEqual(
                    database.connection.execute(
                        "SELECT scan_generation FROM roots WHERE canonical_path = ?",
                        (cache_module._canonical_path(root),),
                    ).fetchone()[0],
                    generation,
                )

    def test_quota_below_unavoidable_overhead_uses_memory_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            (root / "guide.txt").write_text("needle", encoding="utf-8")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            with ContextCacheDatabase(cache_path):
                pass

            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ), patch("cereja.system._context.cache.DEFAULT_MAX_BYTES", 1):
                cached = search_text_context([root], "needle", cache=True)
            direct = search_text_context([root], "needle")
            self.assertEqual(cached, direct)

            with ContextCacheDatabase(cache_path) as database:
                self.assertEqual(
                    database.connection.execute(
                        "SELECT COUNT(*) FROM roots"
                    ).fetchone()[0],
                    0,
                )

    def test_list_cache_matches_direct_and_reuses_text_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            (root / "guide.md").write_text("guide", encoding="utf-8-sig")
            (root / "data.bin").write_bytes(b"binary\x00data")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ):
                cold = list_text_context([root], cache=True)
                reads = self._record_cache_reads(
                    lambda: list_text_context([root], cache=True)
                )
            self.assertEqual(cold, list_text_context([root]))
            self.assertEqual(reads, [])

    def test_external_input_and_interrupt_errors_are_not_masked(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing"
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                with self.assertRaises(FileNotFoundError):
                    search_text_context([missing], "needle", cache=True)
            self.assertFalse(caught)

            with patch(
                "cereja.system._context.cache.iter_repository_files",
                side_effect=KeyboardInterrupt,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    search_text_context([Path(temp_dir)], "needle", cache=True)

    def _assert_cached_equals_direct(self, root, query):
        self.assertEqual(
            search_text_context([root], query, cache=True),
            search_text_context([root], query),
        )

    def _record_cache_reads(self, action):
        original_read = cache_module._read_cacheable_file
        reads = []

        def recording_read(path, signature, max_file_bytes):
            reads.append(Path(path).name)
            return original_read(path, signature, max_file_bytes)

        with patch(
            "cereja.system._context.cache._read_cacheable_file",
            side_effect=recording_read,
        ):
            action()
        return reads


if __name__ == "__main__":
    unittest.main()
