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
    ContextCacheDatabase,
    default_cache_path,
)


class ContextCacheDatabaseTest(unittest.TestCase):
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

    @unittest.skipIf(os.name == "nt", "POSIX sidecar modes are not portable on Windows")
    def test_posix_new_sidecars_are_restricted_immediately(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "context.sqlite3"
            path.touch()
            sidecar = Path(f"{path}-wal")
            sidecar.touch()
            sidecar.chmod(0o666)
            database = ContextCacheDatabase(path)
            database._secure_new_sidecars(set())
            self.assertEqual(stat.S_IMODE(sidecar.stat().st_mode), 0o600)

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
            original_stat = Path.stat
            calls = 0

            def changed_stat(candidate, *args, **kwargs):
                nonlocal calls
                result = original_stat(candidate, *args, **kwargs)
                if candidate == path:
                    calls += 1
                    if calls > 1:
                        values = list(result)
                        values[1] += 1
                        return os.stat_result(values)
                return result

            with patch("cereja.system._context.cache_db.Path.stat", changed_stat):
                with self.assertRaisesRegex(CacheDatabaseError, "identity"):
                    with ContextCacheDatabase(path):
                        pass


if __name__ == "__main__":
    unittest.main()
