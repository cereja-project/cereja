import os
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

from cereja.system import list_text_context, search_text_context
from cereja.system._context import cache as cache_module
from cereja.system._context.cache_db import (
    DEFAULT_NAMESPACE,
    CacheDatabaseUnavailable,
    ContextCacheDatabase,
)
from cereja.system._context.models import ContextCacheWarning


class ContextCacheTest(unittest.TestCase):
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
            with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=cache_path,
            ), patch("cereja.system._context.cache.DEFAULT_MAX_BYTES", 0):
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
