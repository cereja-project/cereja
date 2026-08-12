import os
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
