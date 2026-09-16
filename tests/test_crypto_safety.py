"""Historical encryption compatibility and file publication contracts."""
import base64
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cereja.hashtools import _crypto as crypto

# Produced by the historical writer with salt=00..0f and IV=10..1f.
LEGACY = (
    "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh/irUcLFeOocz3z9XY9oSuk"
    "N7wlaEHvZS9M1PPru4Ej9cyNxnSy4/IsU8Qh40vLcCQ="
)


class CryptoCompatibilityTest(unittest.TestCase):
    def test_historical_fixture_read_and_write(self):
        payload = b'legacy payload\x00\xff'
        self.assertEqual(crypto.decrypt(LEGACY, 'fixture-password'), payload)
        with patch.object(crypto.secrets, 'token_bytes', side_effect=[bytes(range(16)), bytes(range(16, 32))]):
            self.assertEqual(crypto.encrypt(payload, 'fixture-password'), LEGACY)
        with self.assertRaises(crypto.CryptoError):
            crypto.decrypt(LEGACY, 'wrong')

    def test_strict_base64_before_kdf(self):
        for value in ('!!' + LEGACY, LEGACY + '\n', 'AA==', '', 'not:base64'):
            with self.subTest(value=value[:20]), patch.object(crypto, 'generate_key') as derive:
                with self.assertRaises(crypto.CryptoError):
                    crypto.decrypt(value, 'password')
                derive.assert_not_called()

    def test_authentication_before_keystream_generation(self):
        raw = base64.b64decode(LEGACY)
        for offset in (0, 16, 32, len(raw) - 1):
            changed = bytearray(raw)
            changed[offset] ^= 1
            with self.subTest(offset=offset), patch.object(crypto, '_generate_keystream') as keystream:
                with self.assertRaisesRegex(crypto.CryptoError, 'Authentication failed'):
                    crypto.decrypt(base64.b64encode(changed).decode(), 'fixture-password')
                keystream.assert_not_called()

    def test_round_trip_without_site_packages(self):
        subprocess.run([sys.executable, '-S', '-c',
                        "from cereja.hashtools import encrypt, decrypt; "
                        "assert decrypt(encrypt(b'payload', 'password'), 'password') == b'payload'"],
                       cwd=Path(__file__).resolve().parents[1], check=True, capture_output=True)

    def test_safe_error_message(self):
        class BadValue:
            def __str__(self):
                raise ValueError('private-value')
        with self.assertRaises(crypto.CryptoError) as caught:
            crypto.encrypt(BadValue(), 'password')
        self.assertNotIn('private-value', str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)


class CryptoFileTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / 'source.enc'
        self.source.write_text(LEGACY, encoding='ascii')
        self.output = self.root / 'output'

    def decrypt(self, **kwargs):
        return crypto.decrypt_file(self.source, 'fixture-password', self.output, **kwargs)

    def assert_no_temporary(self):
        self.assertEqual(list(self.root.glob('.cereja-crypto-*')), [])

    def test_existing_destination_requires_opt_in(self):
        self.output.write_bytes(b'original')
        with self.assertRaises(crypto.CryptoError):
            self.decrypt()
        self.assertEqual(self.output.read_bytes(), b'original')
        self.decrypt(overwrite=True)
        self.assertEqual(self.output.read_bytes(), b'legacy payload\x00\xff')
        self.assert_no_temporary()

    def test_authentication_failure_does_not_modify_destination(self):
        for exists in (False, True):
            if exists:
                self.output.write_bytes(b'original')
            with self.assertRaises(crypto.CryptoError):
                crypto.decrypt_file(self.source, 'wrong', self.output, overwrite=True)
            if exists:
                self.assertEqual(self.output.read_bytes(), b'original')
            else:
                self.assertFalse(self.output.exists())
            self.assert_no_temporary()

    def test_input_aliases_are_rejected(self):
        for output in (self.source, self.root / '.' / 'source.enc'):
            with self.assertRaises(crypto.CryptoError):
                crypto.decrypt_file(self.source, 'fixture-password', output, overwrite=True)
        os.link(self.source, self.output)
        with self.assertRaises(crypto.CryptoError):
            self.decrypt(overwrite=True)
        self.assertEqual(self.source.read_text(), LEGACY)

    def test_destination_creation_race_does_not_overwrite(self):
        original_link = os.link

        def racing_link(source, destination):
            Path(destination).write_bytes(b'concurrent writer')
            original_link(source, destination)

        with patch.object(crypto.os, 'link', side_effect=racing_link):
            with self.assertRaises(crypto.CryptoError):
                self.decrypt()
        self.assertEqual(self.output.read_bytes(), b'concurrent writer')
        self.assert_no_temporary()

    def test_publication_and_flush_failures_preserve_existing_file(self):
        self.output.write_bytes(b'original')
        for operation in ('replace', 'fsync'):
            with self.subTest(operation=operation), patch.object(crypto.os, operation, side_effect=OSError):
                with self.assertRaises(crypto.CryptoError):
                    self.decrypt(overwrite=True)
            self.assertEqual(self.output.read_bytes(), b'original')
            self.assert_no_temporary()

    def test_write_failure_cleans_temporary(self):
        original_temporary = tempfile.NamedTemporaryFile

        @contextmanager
        def failing_temporary(**kwargs):
            with original_temporary(**kwargs) as stream:
                with patch.object(stream, 'write', side_effect=OSError):
                    yield stream

        with patch.object(crypto.tempfile, 'NamedTemporaryFile', failing_temporary):
            with self.assertRaises(crypto.CryptoError):
                self.decrypt()
        self.assertFalse(self.output.exists())
        self.assert_no_temporary()

    def test_symbolic_link_alias_is_rejected(self):
        try:
            self.output.symlink_to(self.source)
        except OSError:
            self.skipTest('Symbolic links are unavailable')
        with self.assertRaises(crypto.CryptoError):
            self.decrypt(overwrite=True)
        self.assertEqual(self.source.read_text(), LEGACY)

    def test_unsupported_hard_links_fail_without_fallback(self):
        with patch.object(crypto.os, 'link', side_effect=OSError):
            with self.assertRaises(crypto.CryptoError):
                self.decrypt()
        self.assertFalse(self.output.exists())
        self.assert_no_temporary()


class CryptoCliTest(unittest.TestCase):
    def test_force_reaches_file_api(self):
        from cereja.commands import decrypt, encrypt
        from argparse import Namespace
        for module, name in ((encrypt, 'encrypt_file'), (decrypt, 'decrypt_file')):
            for force in (False, True):
                with self.subTest(command=name, force=force):
                    with patch.object(module, 'ensure_output_available'), patch.object(
                            module.getpass, 'getpass', return_value='password'), patch.object(
                            module, name, return_value='output') as operation, patch('builtins.print'):
                        module._handle(Namespace(input='input', output='output', force=force))
                    operation.assert_called_once_with('input', 'password', 'output', overwrite=force)
