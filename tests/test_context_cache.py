import multiprocessing
import os
import sqlite3
import tempfile
import time
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


def _active_sidecar_snapshot(sidecars, modes=None):
    """Read active sidecars, using stable metadata for locked Windows SHM."""
    snapshots = []
    selected_modes = []
    for index, sidecar in enumerate(sidecars):
        mode = None if modes is None else modes[index]
        if mode != "metadata":
            try:
                snapshots.append(("bytes", sidecar.read_bytes()))
                selected_modes.append("bytes")
                continue
            except PermissionError:
                if (mode == "bytes" or os.name != "nt"
                        or not sidecar.name.endswith("-shm")):
                    raise
        result = sidecar.stat(follow_symlinks=False)
        snapshots.append((
            "metadata",
            result.st_dev,
            result.st_ino,
            result.st_size,
            result.st_mtime_ns,
        ))
        selected_modes.append("metadata")
    return tuple(snapshots), tuple(selected_modes)


def _hold_cache_write_transaction(
        cache_path, ready, observe, release, result_queue):
    """Hold a real SQLite write transaction until the parent releases it."""
    try:
        with ContextCacheDatabase(cache_path) as database:
            database.connection.execute("BEGIN IMMEDIATE")
            sidecars = tuple(
                Path(f"{cache_path}{suffix}")
                for suffix in ("-wal", "-shm")
            )
            if not all(path.exists() for path in sidecars):
                raise RuntimeError("write transaction did not create WAL/SHM")
            before, modes = _active_sidecar_snapshot(sidecars)
            ready.set()
            if not observe.wait(10):
                raise TimeoutError("parent did not request sidecar observation")
            after, _ = _active_sidecar_snapshot(sidecars, modes)
            result_queue.put(("ok", before, after, modes))
            if not release.wait(10):
                raise TimeoutError("parent did not release write transaction")
            database.connection.rollback()
    except BaseException as error:
        ready.set()
        result_queue.put(("error", repr(error)))


def _search_with_cache_in_process(cache_path, root, result_queue):
    """Run one public cached search in an importable spawned worker."""
    try:
        started = time.perf_counter()
        with patch(
            "cereja.system._context.cache.default_cache_path",
            return_value=Path(cache_path),
        ), warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            response = search_text_context([Path(root)], "needle", cache=True)
        result_queue.put((
            "ok",
            time.perf_counter() - started,
            tuple(item.category.__name__ for item in caught),
            response,
        ))
    except BaseException as error:
        result_queue.put(("error", repr(error)))


class ContextCacheTest(unittest.TestCase):
    def test_cache_unavailable_is_exported_through_public_facade(self):
        self.assertIs(
            system_module.CacheDatabaseUnavailable,
            CacheDatabaseUnavailable,
        )

    def test_cache_path_inside_searched_root_warns_without_creating_cache(self):
        for cache_relative_path in (
                Path("context.sqlite3"),
                Path(".cereja-cache") / "context.sqlite3",
        ):
            with self.subTest(cache_relative_path=cache_relative_path), \
                    tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir) / "repo"
                nested = root / "nested"
                nested.mkdir(parents=True)
                (root / "guide.md").write_text("needle", encoding="utf-8")
                cache_path = root / cache_relative_path
                if os.name == "nt":
                    searched_root = Path(os.fspath(root).swapcase())
                else:
                    searched_root = nested / ".."

                direct = search_text_context([searched_root], "needle")
                with patch(
                    "cereja.system._context.cache.default_cache_path",
                    return_value=cache_path,
                ), warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    cached = search_text_context(
                        [searched_root], "needle", cache=True
                    )

                self.assertEqual(cached, direct)
                self.assertTrue(any(
                    item.category is ContextCacheWarning for item in caught
                ))
                self.assertFalse(cache_path.exists())
                self.assertFalse(Path(f"{cache_path}-wal").exists())
                self.assertFalse(Path(f"{cache_path}-shm").exists())

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

    def test_info_rejects_legitimate_active_wal_without_storage_mutation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "context.sqlite3"
            owner = ContextCacheDatabase(cache_path)
            owner.__enter__()
            try:
                owner.connection.execute(
                    "INSERT INTO metadata VALUES ('marker', 'value')"
                )
                owner.connection.commit()
                before = {
                    item.name: item.read_bytes()
                    for item in cache_path.parent.iterdir()
                    if item.name.startswith(cache_path.name)
                }

                with self.assertRaises(CacheDatabaseUnavailable):
                    ContextCacheDatabase.read_info(cache_path)

                after = {
                    item.name: item.read_bytes()
                    for item in cache_path.parent.iterdir()
                    if item.name.startswith(cache_path.name)
                }
            finally:
                owner.__exit__(None, None, None)
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

    def test_info_and_clear_reject_orphan_sqlite_sidecars(self):
        for suffix in ("-wal", "-shm", "-journal"):
            with self.subTest(suffix=suffix), \
                 tempfile.TemporaryDirectory() as temp_dir:
                cache_path = Path(temp_dir) / "context.sqlite3"
                sidecar = Path(f"{cache_path}{suffix}")
                sidecar.write_bytes(b"orphan cache sentinel")
                if os.name != "nt":
                    sidecar.chmod(0o600)
                before = sidecar.read_bytes()

                with patch(
                    "cereja.system._context.cache.default_cache_path",
                    return_value=cache_path,
                ):
                    with self.assertRaises(CacheDatabaseUnavailable):
                        system_module.get_context_cache_info()
                    with self.assertRaises(CacheDatabaseUnavailable):
                        system_module.clear_context_cache()

                self.assertFalse(cache_path.exists())
                self.assertEqual(sidecar.read_bytes(), before)

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

    def test_concurrent_writer_sidecars_force_fast_read_only_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            (root / "guide.txt").write_text("needle", encoding="utf-8")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            direct = search_text_context([root], "needle")
            context = multiprocessing.get_context("spawn")
            ready = context.Event()
            observe = context.Event()
            release = context.Event()
            owner_results = context.Queue()
            search_results = context.Queue()
            owner = context.Process(
                target=_hold_cache_write_transaction,
                args=(cache_path, ready, observe, release, owner_results),
            )
            searcher = context.Process(
                target=_search_with_cache_in_process,
                args=(cache_path, root, search_results),
            )

            owner.start()
            try:
                self.assertTrue(ready.wait(10), "writer process did not start")
                sidecars = tuple(
                    Path(f"{cache_path}{suffix}")
                    for suffix in ("-wal", "-shm")
                )
                if not all(path.exists() for path in sidecars):
                    observe.set()
                    self.fail(owner_results.get(timeout=2))

                searcher_started = time.perf_counter()
                searcher.start()
                searcher.join(10)
                process_elapsed = time.perf_counter() - searcher_started
                self.assertFalse(
                    searcher.is_alive(), "cached search process did not finish"
                )
                self.assertLess(process_elapsed, 5)
                result = search_results.get(timeout=2)
                self.assertEqual(result[0], "ok", result)
                _, elapsed, warning_categories, response = result
                self.assertLess(elapsed, 5)
                self.assertEqual(
                    warning_categories, (ContextCacheWarning.__name__,)
                )
                self.assertEqual(response, direct)
                observe.set()
                owner_result = owner_results.get(timeout=2)
                self.assertEqual(owner_result[0], "ok", owner_result)
                _, before, after, modes = owner_result
                self.assertEqual(modes[0], "bytes")
                if os.name != "nt":
                    self.assertEqual(modes, ("bytes", "bytes"))
                self.assertEqual(after, before)
            finally:
                observe.set()
                release.set()
                if searcher.pid is not None:
                    if searcher.is_alive():
                        searcher.terminate()
                    searcher.join(10)
                owner.join(10)
                if owner.is_alive():
                    owner.terminate()
                    owner.join(10)
                owner_results.close()
                search_results.close()

            self.assertEqual(owner.exitcode, 0)
            self.assertEqual(searcher.exitcode, 0)

    def test_clear_reports_post_commit_checkpoint_busy(self):
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
                    with self.assertRaisesRegex(
                        CacheDatabaseUnavailable, "clear was committed"
                    ):
                        system_module.clear_context_cache()

            with ContextCacheDatabase(cache_path) as database:
                self.assertEqual(
                    database.connection.execute(
                        "SELECT COUNT(*) FROM namespace_roots"
                    ).fetchone()[0],
                    0,
                )

    def test_clear_reports_post_commit_checkpoint_lock_failure(self):
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
                    with self.assertRaisesRegex(
                        CacheDatabaseUnavailable, "clear was committed"
                    ):
                        system_module.clear_context_cache()

            with ContextCacheDatabase(cache_path) as database:
                self.assertEqual(
                    database.connection.execute(
                        "SELECT COUNT(*) FROM namespace_roots"
                    ).fetchone()[0],
                    0,
                )

    def test_clear_reports_lock_restore_failure_after_commit(self):
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
                    with self.assertRaisesRegex(
                        CacheDatabaseUnavailable, "clear was committed"
                    ):
                        system_module.clear_context_cache()

            with ContextCacheDatabase(cache_path) as database:
                self.assertEqual(
                    database.connection.execute(
                        "SELECT COUNT(*) FROM namespace_roots"
                    ).fetchone()[0],
                    0,
                )

    def test_clear_reports_post_commit_maintenance_io_error(self):
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
                    side_effect=sqlite3.OperationalError("disk I/O error"),
                ):
                    with self.assertRaisesRegex(
                        CacheDatabaseUnavailable, "clear was committed"
                    ):
                        system_module.clear_context_cache()

            with ContextCacheDatabase(cache_path) as database:
                self.assertEqual(
                    database.connection.execute(
                        "SELECT COUNT(*) FROM namespace_roots"
                    ).fetchone()[0],
                    0,
                )

    def test_clear_reports_post_commit_vacuum_failure(self):
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
                    "_freelist_pages",
                    return_value=1,
                ), patch.object(
                    ContextCacheDatabase,
                    "_run_bounded_vacuum",
                    side_effect=sqlite3.OperationalError("vacuum failed"),
                ):
                    with self.assertRaisesRegex(
                        CacheDatabaseUnavailable, "clear was committed"
                    ):
                        system_module.clear_context_cache()

            with ContextCacheDatabase(cache_path) as database:
                self.assertEqual(
                    database.connection.execute(
                        "SELECT COUNT(*) FROM namespace_roots"
                    ).fetchone()[0],
                    0,
                )

    def test_clear_reports_post_commit_measurement_failure(self):
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
                before_bytes = sum(
                    path.stat().st_size
                    for path in (
                        cache_path,
                        Path(f"{cache_path}-wal"),
                        Path(f"{cache_path}-shm"),
                    )
                    if path.exists()
                )
                with patch.object(
                    ContextCacheDatabase,
                    "aggregate_size_bytes",
                    side_effect=(
                        before_bytes,
                        OSError("measurement failed"),
                    ),
                ):
                    with self.assertRaisesRegex(
                        CacheDatabaseUnavailable, "clear was committed"
                    ):
                        system_module.clear_context_cache()

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

    def test_warm_cache_validates_all_files_with_one_batched_lookup(self):
        """A per-file cache query must not return during a warm scan."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            for name in ("first.txt", "second.txt", "third.txt"):
                (root / name).write_text("cached content", encoding="utf-8")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            original_batched_lookup = ContextCacheDatabase.get_cached_contents
            original_individual_lookup = ContextCacheDatabase.get_cached_content
            batched_lookups = []
            individual_lookups = []

            def record_batched_lookup(database, canonical_paths):
                canonical_paths = tuple(canonical_paths)
                batched_lookups.append(canonical_paths)
                return original_batched_lookup(database, canonical_paths)

            def record_individual_lookup(*args, **kwargs):
                individual_lookups.append((args, kwargs))
                return original_individual_lookup(*args, **kwargs)

            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ):
                search_text_context([root], "missing", cache=True)
                with patch.object(
                    ContextCacheDatabase,
                    "get_cached_contents",
                    new=record_batched_lookup,
                ), patch.object(
                    ContextCacheDatabase,
                    "get_cached_content",
                    new=record_individual_lookup,
                ):
                    reads = self._record_cache_reads(
                        lambda: search_text_context([root], "missing", cache=True)
                    )

            expected_paths = {
                cache_module._canonical_path(root / name)
                for name in ("first.txt", "second.txt", "third.txt")
            }
            self.assertEqual(reads, [])
            self.assertEqual(len(batched_lookups), 1)
            self.assertEqual(set(batched_lookups[0]), expected_paths)
            self.assertEqual(individual_lookups, [])

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

    def test_cached_match_score_and_selection_characterization(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            (root / "b-auth.txt").write_text(
                "AUTH cache\nauth cache", encoding="utf-8"
            )
            (root / "A-auth.txt").write_text(
                "auth cache\nauth cache", encoding="utf-8"
            )
            (root / "ignored.txt").write_text("auth only", encoding="utf-8")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"

            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ):
                response = search_text_context(
                    [root], "auth cache", cache=True, max_results=1
                )

            self.assertEqual(len(response.results), 1)
            result = response.results[0]
            self.assertEqual(result.relative_path, "A-auth.txt")
            self.assertEqual(result.score, 1004)
            self.assertEqual(result.match_count, 4)
            self.assertTrue(response.truncated)

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

    def test_recognized_corruption_warns_and_falls_back_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            (root / "guide.md").write_text("needle", encoding="utf-8")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            with ContextCacheDatabase(cache_path):
                pass
            cache_path.write_bytes(cache_path.read_bytes()[:128])
            storage_paths = (
                cache_path,
                Path(f"{cache_path}-wal"),
                Path(f"{cache_path}-shm"),
                Path(f"{cache_path}-journal"),
            )
            before = tuple(
                item.read_bytes() if item.exists() else None
                for item in storage_paths
            )

            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ), warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                response = search_text_context([root], "needle", cache=True)

            self.assertEqual(
                [item.relative_path for item in response.results], ["guide.md"]
            )
            self.assertTrue(
                any(item.category is ContextCacheWarning for item in caught)
            )
            self.assertEqual(tuple(
                item.read_bytes() if item.exists() else None
                for item in storage_paths
            ), before)

    def test_active_sidecars_warn_and_fall_back_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            (root / "guide.md").write_text("needle", encoding="utf-8")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            owner = ContextCacheDatabase(cache_path)
            owner.__enter__()
            try:
                owner.connection.execute(
                    "INSERT INTO metadata VALUES ('marker', 'value')"
                )
                owner.connection.commit()
                storage_paths = (
                    cache_path,
                    Path(f"{cache_path}-wal"),
                    Path(f"{cache_path}-shm"),
                    Path(f"{cache_path}-journal"),
                )
                before = tuple(
                    item.read_bytes() if item.exists() else None
                    for item in storage_paths
                )

                with patch(
                    "cereja.system._context.cache.default_cache_path",
                    return_value=cache_path,
                ), warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    response = search_text_context(
                        [root], "needle", cache=True
                    )

                self.assertEqual(
                    [item.relative_path for item in response.results],
                    ["guide.md"],
                )
                self.assertTrue(any(
                    item.category is ContextCacheWarning for item in caught
                ))
                self.assertEqual(tuple(
                    item.read_bytes() if item.exists() else None
                    for item in storage_paths
                ), before)
            finally:
                owner.__exit__(None, None, None)

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

    def test_warm_cache_reprocesses_when_file_limit_crosses_file_size(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            target = root / "target.txt"
            target.write_text("content", encoding="utf-8")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ):
                search_text_context(
                    [root], "missing", cache=True, max_file_bytes=10
                )
                reduced_limit_reads = self._record_cache_reads(
                    lambda: search_text_context(
                        [root], "missing", cache=True, max_file_bytes=3
                    )
                )
                restored_limit_reads = self._record_cache_reads(
                    lambda: search_text_context(
                        [root], "content", cache=True, max_file_bytes=10
                    )
                )

            self.assertEqual(reduced_limit_reads, ["target.txt"])
            self.assertEqual(restored_limit_reads, ["target.txt"])

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

    def test_synchronization_publishes_only_admitted_root_scans(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            outer = Path(temp_dir) / "outer"
            inner = Path(temp_dir) / "inner"
            outer.mkdir()
            inner.mkdir()
            (outer / "outer.txt").write_text("outer", encoding="utf-8")
            (inner / "inner.txt").write_text("inner", encoding="utf-8")
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            outer_root = cache_module._canonical_path(outer)
            original_begin = ContextCacheDatabase.begin_scans_if_admitted
            original_commit = ContextCacheDatabase.commit_scan
            commit_calls = []

            def admit_only_outer(database, namespace, roots, max_bytes):
                tokens = original_begin(database, namespace, roots, max_bytes)
                return {outer_root: tokens[outer_root]}

            def record_commit(*args, **kwargs):
                commit_calls.append((args, kwargs))
                return original_commit(*args, **kwargs)

            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ), patch.object(
                ContextCacheDatabase,
                "begin_scans_if_admitted",
                new=admit_only_outer,
            ), patch.object(
                ContextCacheDatabase,
                "commit_scan",
                new=record_commit,
            ):
                response = search_text_context(
                    [outer, inner], "missing", cache=True
                )

            self.assertEqual(response.results, ())
            self.assertEqual(
                [call[0][1].canonical_root for call in commit_calls],
                [outer_root],
            )

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
                (root / "partial.txt").write_text("needle", encoding="utf-8")
                original_inventory = cache_module.iter_repository_files

                def failing_inventory(*args, **kwargs):
                    yield next(iter(original_inventory(*args, **kwargs)))
                    raise OSError("inventory failed")

                commit_calls = []
                original_commit = ContextCacheDatabase.commit_scan

                def record_commit(*args, **kwargs):
                    commit_calls.append((args, kwargs))
                    return original_commit(*args, **kwargs)

                with patch(
                    "cereja.system._context.cache.iter_repository_files",
                    side_effect=failing_inventory,
                ), patch.object(
                    ContextCacheDatabase,
                    "commit_scan",
                    new=record_commit,
                ), warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    with self.assertRaisesRegex(OSError, "inventory failed"):
                        search_text_context([root], "needle", cache=True)
                self.assertFalse(caught)
                self.assertEqual(commit_calls, [])

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

    def test_quota_pressure_evicts_old_root_and_protects_active_new_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            old_root = base / "old"
            new_root = base / "new"
            old_root.mkdir()
            new_root.mkdir()
            (old_root / "old.txt").write_text(
                "old " + "x" * 2_000_000, encoding="utf-8"
            )
            (new_root / "new.txt").write_text("new", encoding="utf-8")
            cache_path = base / "cache" / "context.sqlite3"

            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ):
                search_text_context(
                    [old_root], "old", cache=True, max_file_bytes=3_000_000
                )
                search_text_context([new_root], "new", cache=True)

                with ContextCacheDatabase(cache_path) as database:
                    database._checkpoint_wal()
                    quota = database.aggregate_size_bytes() - 1

                with patch(
                    "cereja.system._context.cache.DEFAULT_MAX_BYTES", quota
                ):
                    response = search_text_context(
                        [new_root], "new", cache=True
                    )

            self.assertEqual(response.results[0].relative_path, "new.txt")
            with ContextCacheDatabase(cache_path) as database:
                database._checkpoint_wal()
                roots = [
                    row[0] for row in database.connection.execute(
                        "SELECT canonical_path FROM roots ORDER BY canonical_path"
                    )
                ]
                files = [
                    row[0] for row in database.connection.execute(
                        "SELECT canonical_path FROM files ORDER BY canonical_path"
                    )
                ]
                aggregate = database.aggregate_size_bytes()

            self.assertEqual(roots, [cache_module._canonical_path(new_root)])
            self.assertEqual(files, [cache_module._canonical_path(new_root / "new.txt")])
            self.assertLessEqual(aggregate, quota)

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
                        with warnings.catch_warnings():
                            warnings.simplefilter(
                                "ignore", ContextCacheWarning
                            )
                            for _ in range(8):
                                response = search_text_context(
                                    [root], "needle", cache=True
                                )
                                self.assertEqual(
                                    response.results[0].relative_path,
                                    "guide.txt",
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

    def test_active_root_over_quota_stays_searchable_without_admission(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            for index in range(4):
                (root / f"{index}.txt").write_text(
                    f"needle {index} " + "x" * 4_096,
                    encoding="utf-8",
                )
            cache_path = Path(temp_dir) / "cache" / "context.sqlite3"
            with ContextCacheDatabase(cache_path):
                pass

            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ), patch(
                "cereja.system._context.cache.DEFAULT_MAX_BYTES", 8 * 1024
            ):
                cached = search_text_context([root], "needle", cache=True)
            direct = search_text_context([root], "needle")
            self.assertEqual(cached, direct)
            self.assertEqual(
                [result.relative_path for result in cached.results],
                ["0.txt", "1.txt", "2.txt", "3.txt"],
            )

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
