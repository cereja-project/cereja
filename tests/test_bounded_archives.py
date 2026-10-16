"""Bounded archive acceptance on owned temporary fixtures."""
from dataclasses import replace
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

from cereja.hashtools.archive import (
    ArchiveLimits, MAGIC, file_archive, create_directory_archive,
    extract_directory_archive,
)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.write_bytes(b'hello' * 100)
        self.target = self.root / 'result'

    def assert_clean(self):
        self.assertFalse(any(p.name.startswith('.cereja-archive-') for p in self.root.iterdir()))

    def test_file_roundtrip_and_legacy_interoperability(self):
        archive = self.root / 'source.cjz'
        file_archive(self.source, archive)
        file_archive(archive, self.target, extract=True)
        self.assertEqual(self.target.read_bytes(), self.source.read_bytes())
        from cereja.hashtools import decompress_file
        legacy = self.root / 'legacy'
        decompress_file(str(archive), str(legacy), verbose=False)
        self.assertEqual(legacy.read_bytes(), self.source.read_bytes())

    def test_file_refuses_overwrite_and_collision(self):
        for target in (self.source, self.target):
            target.write_bytes(b'keep')
            with self.assertRaises(FileExistsError):
                file_archive(self.source, target)
            self.assertEqual(target.read_bytes(), b'keep')

    def test_file_expansion_and_input_bounds(self):
        self.source.write_bytes(b'\x10' + zlib.compress(b'x' * 2000))
        with self.assertRaises(ValueError):
            file_archive(self.source, self.target, extract=True,
                         limits=replace(ArchiveLimits(), max_member_bytes=100))
        self.assertFalse(self.target.exists())
        with self.assertRaises(ValueError):
            file_archive(self.source, self.target, limits=replace(ArchiveLimits(), max_input_bytes=5))

    def test_file_invalid_truncated_trailing_and_unsupported(self):
        for data in (b'bad', b'\x10' + zlib.compress(b'x')[:-2],
                     b'\x10' + zlib.compress(b'x') + b'trailing'):
            self.source.write_bytes(data)
            with self.assertRaises((ValueError, zlib.error)):
                file_archive(self.source, self.target, extract=True)
            self.assertFalse(self.target.exists())

    def test_file_commit_race_preserves_new_destination(self):
        def race():
            self.target.write_bytes(b'other writer')
        with self.assertRaises(FileExistsError):
            file_archive(self.source, self.target, committing=race)
        self.assertEqual(self.target.read_bytes(), b'other writer')

    def tree(self):
        self.source.unlink()
        self.source.mkdir()
        (self.source / 'empty').mkdir()
        (self.source / 'café').mkdir()
        (self.source / 'café' / '界.txt').write_text('fixture')

    @unittest.skipUnless(os.name == 'nt', 'Windows exclusive directory publication')
    def test_directory_roundtrip_empty_nested_unicode(self):
        self.tree()
        archive = self.root / 'tree.cjz'
        create_directory_archive(self.source, archive)
        result = extract_directory_archive(archive, self.target)
        self.assertEqual(result.members, 3)
        self.assertTrue((self.target / 'empty').is_dir())
        self.assertEqual((self.target / 'café' / '界.txt').read_text(), 'fixture')
        self.assert_clean()

    @unittest.skipUnless(os.name == 'nt', 'Windows exclusive directory publication')
    def test_empty_tree_roundtrip(self):
        self.source.unlink()
        self.source.mkdir()
        archive = self.root / 'empty.cjz'
        create_directory_archive(self.source, archive)
        extract_directory_archive(archive, self.target)
        self.assertEqual(list(self.target.iterdir()), [])

    def test_directory_create_budgets_and_inside_destination(self):
        self.tree()
        with self.assertRaises(ValueError):
            create_directory_archive(self.source, self.source / 'inside')
        with self.assertRaises(ValueError):
            create_directory_archive(self.source, self.target,
                                     limits=replace(ArchiveLimits(), max_members=1))
        self.assertFalse(self.target.exists())
        self.assert_clean()

    def crafted(self, names):
        data = bytearray(MAGIC)
        for name in names:
            raw = name.encode()
            chunk = zlib.compress(b'x')
            data += b'\x01' + struct.pack('>I', len(raw)) + raw
            data += struct.pack('>Q', 1) + b'\x10'
            data += struct.pack('>I', len(chunk)) + chunk + b'\0\0\0\0'
        self.source.write_bytes(data + b'\0')

    @unittest.skipUnless(os.name == 'nt', 'Windows exclusive directory publication')
    def test_adversarial_names_collisions_and_conflicts(self):
        for names in (['../escape'], ['/absolute'], ['C:/drive'], ['//server/share'],
                      ['a:stream'], ['a\\b'], ['NUL'], ['a.'], ['a//b'],
                      ['x', 'x'], ['X', 'x'], ['A/x', 'a/y'], ['x', 'x/y'],
                      ['x/y', 'x'], ['e\u0301', 'é']):
            with self.subTest(names=names):
                self.crafted(names)
                with self.assertRaises((ValueError, OSError)):
                    extract_directory_archive(self.source, self.target)
                self.assertFalse(self.target.exists())
                self.assert_clean()

    @unittest.skipUnless(os.name == 'nt', 'Windows exclusive directory publication')
    def test_extraction_budget_corruption_and_commit_failure(self):
        self.crafted(['a'])
        data = self.source.read_bytes()
        for broken in (data[:-3], data + b'x', MAGIC + b'\x03'):
            self.source.write_bytes(broken)
            with self.assertRaises(Exception):
                extract_directory_archive(self.source, self.target)
            self.assertFalse(self.target.exists())
            self.assert_clean()
        self.source.write_bytes(data)
        with patch('cereja.hashtools.archive.os.rename', side_effect=PermissionError('fixture')):
            with self.assertRaises(PermissionError):
                extract_directory_archive(self.source, self.target)
        self.assertFalse(self.target.exists())
        self.assert_clean()

    @unittest.skipUnless(os.name == 'nt', 'Windows exclusive directory publication')
    def test_directory_commit_race_preserves_existing_tree(self):
        self.crafted(['a'])
        def race():
            self.target.mkdir()
            (self.target / 'keep').touch()
        with self.assertRaises(OSError):
            extract_directory_archive(self.source, self.target, committing=race)
        self.assertTrue((self.target / 'keep').exists())
        self.assertFalse((self.target / 'a').exists())
        self.assert_clean()

    @unittest.skipUnless(os.name == 'nt', 'Exclusive directory publication requires Windows')
    def test_declared_size_does_not_allow_expansion_bomb(self):
        raw = b'a'
        chunk = zlib.compress(b'x' * 1000000)
        self.source.write_bytes(MAGIC + b'\x01' + struct.pack('>I', 1) + raw
                                + struct.pack('>Q', 1) + b'\x10'
                                + struct.pack('>I', len(chunk)) + chunk + b'\0\0\0\0\0')
        with self.assertRaises(ValueError):
            extract_directory_archive(self.source, self.target)
        self.assertFalse(self.target.exists())
        self.assert_clean()

    @unittest.skipUnless(os.name != 'nt', 'POSIX refusal only')
    def test_unsupported_exclusive_directory_publish_fails_closed(self):
        self.crafted(['a'])
        with self.assertRaisesRegex(ValueError, 'requires Windows'):
            extract_directory_archive(self.source, self.target)
        self.assertFalse(self.target.exists())

    def test_source_link_refused(self):
        link = self.root / 'link'
        try:
            link.symlink_to(self.source)
        except OSError:
            self.skipTest('symlink creation unavailable')
        with self.assertRaises(ValueError):
            file_archive(link, self.target)


if __name__ == '__main__':
    unittest.main()
