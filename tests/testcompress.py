import unittest
import os
import tempfile
from unittest import mock
from cereja import hashtools
from cereja.hashtools import _compress


class CompressTest(unittest.TestCase):
    """Test suite for compression utilities."""
    
    def test_compress_decompress_string(self):
        """Test basic string compression and decompression."""
        original = "Hello, Cereja! This is a test of compression. " * 10
        
        compressed, stats = hashtools.compress(original)
        self.assertIsInstance(compressed, bytes)
        self.assertLess(len(compressed), len(original))
        
        decompressed = hashtools.decompress(compressed)
        self.assertEqual(decompressed.decode('utf-8'), original)
        
        # Check stats
        self.assertGreater(stats.ratio, 1.0)
        self.assertGreater(stats.savings_percent, 0)
    
    def test_compress_decompress_bytes(self):
        """Test bytes compression and decompression."""
        original = b"Binary data test " * 20
        
        compressed, stats = hashtools.compress(original)
        decompressed = hashtools.decompress(compressed)
        
        self.assertEqual(decompressed, original)
    
    def test_dictionary_compression(self):
        """Test dictionary compression strategy."""
        # Repetitive text should use dictionary compression
        original = "the quick brown fox jumps over the lazy dog " * 50
        
        compressed, stats = hashtools.compress(original, strategy='dict')
        decompressed = hashtools.decompress(compressed)
        
        self.assertEqual(decompressed.decode('utf-8'), original)
        self.assertEqual(stats.strategy, hashtools.CompressionStrategy.DICTIONARY)
    
    def test_rle_compression(self):
        """Test RLE compression strategy."""
        # Data with long runs
        original = b'\x00' * 100 + b'\xFF' * 100 + b'\x42' * 100
        
        compressed, stats = hashtools.compress(original, strategy='rle')
        decompressed = hashtools.decompress(compressed)
        
        self.assertEqual(decompressed, original)
        self.assertEqual(stats.strategy, hashtools.CompressionStrategy.RLE)
        self.assertLess(len(compressed), len(original))
    
    def test_delta_compression(self):
        """Test delta encoding compression strategy."""
        # Sequential integers
        import struct
        values = list(range(1000, 1100))
        original = b''.join(struct.pack('>I', v) for v in values)
        
        compressed, stats = hashtools.compress(original, strategy='delta')
        decompressed = hashtools.decompress(compressed)
        
        self.assertEqual(decompressed, original)
        self.assertEqual(stats.strategy, hashtools.CompressionStrategy.DELTA)
    
    def test_bitpack_compression(self):
        """Test bit packing compression strategy."""
        # Data with small values (0-15)
        original = bytes([i % 16 for i in range(1000)])
        
        compressed, stats = hashtools.compress(original, strategy='bitpack')
        decompressed = hashtools.decompress(compressed)
        
        self.assertEqual(decompressed, original)
        self.assertEqual(stats.strategy, hashtools.CompressionStrategy.BITPACK)
        self.assertLess(len(compressed), len(original))
    
    def test_zlib_compression(self):
        """Test zlib compression strategy."""
        original = "Random text data for zlib compression test. " * 20
        
        compressed, stats = hashtools.compress(original, strategy='zlib')
        decompressed = hashtools.decompress(compressed)
        
        self.assertEqual(decompressed.decode('utf-8'), original)
        self.assertEqual(stats.strategy, hashtools.CompressionStrategy.ZLIB)
    
    def test_bz2_compression(self):
        """Test bz2 compression strategy."""
        original = "Data for bz2 compression testing. " * 50
        
        compressed, stats = hashtools.compress(original, strategy='bz2')
        decompressed = hashtools.decompress(compressed)
        
        self.assertEqual(decompressed.decode('utf-8'), original)
        self.assertEqual(stats.strategy, hashtools.CompressionStrategy.BZ2)
    
    def test_lzma_compression(self):
        """Test LZMA compression strategy."""
        original = "LZMA compression test data. " * 100
        
        compressed, stats = hashtools.compress(original, strategy='lzma')
        decompressed = hashtools.decompress(compressed)
        
        self.assertEqual(decompressed.decode('utf-8'), original)
        self.assertEqual(stats.strategy, hashtools.CompressionStrategy.LZMA)
    
    def test_auto_strategy_selection(self):
        """Test automatic strategy selection."""
        # Repetitive data should trigger RLE
        repetitive = b'\x00' * 500
        compressed, stats = hashtools.compress(repetitive, strategy='auto')
        self.assertEqual(stats.strategy, hashtools.CompressionStrategy.RLE)
        
        # Sequential data should trigger Delta
        import struct
        sequential = b''.join(struct.pack('>I', i) for i in range(100, 200))
        compressed, stats = hashtools.compress(sequential, strategy='auto')
        self.assertEqual(stats.strategy, hashtools.CompressionStrategy.DELTA)
        
        # Small values should trigger BitPack
        small_values = bytes([i % 8 for i in range(500)])
        compressed, stats = hashtools.compress(small_values, strategy='auto')
        self.assertEqual(stats.strategy, hashtools.CompressionStrategy.BITPACK)
    
    def test_hybrid_compression(self):
        """Test hybrid compression strategy."""
        original = "Mixed data for hybrid compression. " * 30
        
        compressed, stats = hashtools.compress(original, strategy='hybrid')
        decompressed = hashtools.decompress(compressed)
        
        self.assertEqual(decompressed.decode('utf-8'), original)
    
    def test_empty_data(self):
        """Test compression of empty data."""
        original = b""
        
        compressed, stats = hashtools.compress(original)
        decompressed = hashtools.decompress(compressed)
        
        self.assertEqual(decompressed, original)
    
    def test_small_data(self):
        """Test compression of small data."""
        original = b"Hi"
        
        compressed, stats = hashtools.compress(original)
        decompressed = hashtools.decompress(compressed)
        
        self.assertEqual(decompressed, original)
    
    def test_large_data(self):
        """Test compression of large data."""
        original = b"Large data test. " * 10000  # ~170KB
        
        compressed, stats = hashtools.compress(original)
        decompressed = hashtools.decompress(compressed)
        
        self.assertEqual(decompressed, original)
        self.assertGreater(stats.ratio, 5.0)  # Should compress well
    
    def test_unicode_data(self):
        """Test compression with unicode characters."""
        original = "Unicode: 你好世界 مرحبا العالم Привет мир 🌍🌎🌏 " * 20
        
        compressed, stats = hashtools.compress(original)
        decompressed = hashtools.decompress(compressed)
        
        self.assertEqual(decompressed.decode('utf-8'), original)
    
    def test_binary_data(self):
        """Test compression of binary data."""
        original = bytes(range(256)) * 10
        
        compressed, stats = hashtools.compress(original)
        decompressed = hashtools.decompress(compressed)
        
        self.assertEqual(decompressed, original)
    
    def test_incompressible_data(self):
        """Test compression of random (incompressible) data."""
        import random
        random.seed(42)
        original = bytes([random.randint(0, 255) for _ in range(1000)])
        
        compressed, stats = hashtools.compress(original)
        decompressed = hashtools.decompress(compressed)
        
        self.assertEqual(decompressed, original)
        # Random data may not compress well
    
    def test_analyze_data(self):
        """Test data analysis function."""
        # Repetitive data
        data = b'\x00' * 100
        analysis = hashtools.analyze_data(data)
        
        self.assertIn('size', analysis)
        self.assertIn('entropy', analysis)
        self.assertIn('repetition_ratio', analysis)
        self.assertEqual(analysis['size'], 100)
        self.assertGreater(analysis['repetition_ratio'], 0.9)
    
    def test_suggest_strategy(self):
        """Test strategy suggestion."""
        # Repetitive data
        repetitive = b'\xFF' * 200
        strategy = hashtools.suggest_strategy(repetitive)
        self.assertEqual(strategy, hashtools.CompressionStrategy.RLE)
        
        # Sequential data
        import struct
        sequential = b''.join(struct.pack('>I', i) for i in range(100))
        strategy = hashtools.suggest_strategy(sequential)
        self.assertEqual(strategy, hashtools.CompressionStrategy.DELTA)
        
        # Small values
        small = bytes([i % 10 for i in range(500)])
        strategy = hashtools.suggest_strategy(small)
        self.assertEqual(strategy, hashtools.CompressionStrategy.BITPACK)
    
    def test_compression_stats(self):
        """Test compression statistics."""
        original = "Test data " * 1000
        compressed, stats = hashtools.compress(original)
        
        self.assertIsInstance(stats, hashtools.CompressionStats)
        self.assertEqual(stats.original_size, len(original))
        self.assertEqual(stats.compressed_size, len(compressed))
        self.assertGreater(stats.ratio, 1.0)
        self.assertGreater(stats.savings_percent, 0)
        self.assertGreater(stats.time_ms, 0)
    
    def test_get_compression_ratio(self):
        """Test compression ratio calculation."""
        original = "Test data"
        compressed = b"compressed"
        
        ratio = hashtools.get_compression_ratio(original, compressed)
        self.assertEqual(ratio, len(original) / len(compressed))
    
    def test_compress_file(self):
        """Test file compression."""
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            temp_file = f.name
            f.write("This is test data for file compression.\n" * 100)
        
        try:
            # Compress file
            compressed_file, stats = hashtools.compress_file(temp_file)
            self.assertTrue(os.path.exists(compressed_file))
            self.assertEqual(compressed_file, temp_file + '.cjz')
            self.assertGreater(stats.ratio, 1.0)
            
            # Decompress file
            decompressed_file = hashtools.decompress_file(compressed_file)
            self.assertTrue(os.path.exists(decompressed_file))
            
            # Verify content
            with open(temp_file, 'r') as f1, open(decompressed_file, 'r') as f2:
                self.assertEqual(f1.read(), f2.read())
            
            # Cleanup
            os.remove(compressed_file)
            os.remove(decompressed_file)
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    def test_compress_file_custom_output(self):
        """Test file compression with custom output path."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            temp_file = f.name
            f.write("Custom output test data.\n" * 50)
        
        try:
            custom_output = temp_file + '.compressed'
            
            # Compress with custom output
            compressed_file, stats = hashtools.compress_file(temp_file, output_path=custom_output)
            self.assertEqual(compressed_file, custom_output)
            self.assertTrue(os.path.exists(custom_output))
            
            # Decompress with custom output
            custom_decompress = temp_file + '.restored'
            decompressed_file = hashtools.decompress_file(compressed_file, output_path=custom_decompress)
            self.assertEqual(decompressed_file, custom_decompress)
            
            # Verify content
            with open(temp_file, 'r') as f1, open(decompressed_file, 'r') as f2:
                self.assertEqual(f1.read(), f2.read())
            
            # Cleanup
            os.remove(custom_output)
            os.remove(custom_decompress)
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    def test_compress_file_with_strategy(self):
        """Test file compression with specific strategy."""
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            temp_file = f.name
            # Write repetitive binary data
            f.write(b'\x00' * 1000 + b'\xFF' * 1000)
        
        try:
            # Compress with RLE strategy
            compressed_file, stats = hashtools.compress_file(temp_file, strategy='rle')
            self.assertEqual(stats.strategy, hashtools.CompressionStrategy.RLE)
            
            # Decompress and verify
            decompressed_file = hashtools.decompress_file(compressed_file)
            
            with open(temp_file, 'rb') as f1, open(decompressed_file, 'rb') as f2:
                self.assertEqual(f1.read(), f2.read())
            
            # Cleanup
            os.remove(compressed_file)
            os.remove(decompressed_file)
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def test_compress_file_with_password_requires_password_to_decompress(self):
        """Test encrypted file archive requires the password to decompress."""
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            temp_file = f.name
            f.write(b'secret compressed file data' * 20)

        try:
            compressed_file, stats = hashtools.compress_file(temp_file, password='password')
            restored_file = temp_file + '.restored'

            self.assertTrue(hashtools.is_encrypted_archive(compressed_file))
            self.assertGreater(stats.compressed_size, 0)
            with self.assertRaises(hashtools.CompressionError):
                hashtools.decompress_file(compressed_file, output_path=restored_file)

            hashtools.decompress_file(compressed_file, output_path=restored_file, password='password')

            with open(temp_file, 'rb') as original, open(restored_file, 'rb') as restored:
                self.assertEqual(restored.read(), original.read())

            os.remove(compressed_file)
            os.remove(restored_file)
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    def test_compress_nonexistent_file(self):
        """Test compression of non-existent file."""
        with self.assertRaises(FileNotFoundError):
            hashtools.compress_file("nonexistent_file.txt")
    
    def test_decompress_nonexistent_file(self):
        """Test decompression of non-existent file."""
        with self.assertRaises(FileNotFoundError):
            hashtools.decompress_file("nonexistent_file.cjz")
    
    def test_invalid_compressed_data(self):
        """Test decompression of invalid data."""
        with self.assertRaises(hashtools.CompressionError):
            hashtools.decompress(b'\xFF\xFF\xFF')
    
    def test_compression_levels(self):
        """Test different compression levels."""
        original = "Test data for compression levels. " * 100
        
        # Test different levels for zlib
        compressed_low, stats_low = hashtools.compress(original, strategy='zlib', level=1)
        compressed_high, stats_high = hashtools.compress(original, strategy='zlib', level=9)
        
        # Higher level should compress better (or equal)
        self.assertLessEqual(len(compressed_high), len(compressed_low))
        
        # Both should decompress correctly
        self.assertEqual(hashtools.decompress(compressed_low).decode('utf-8'), original)
        self.assertEqual(hashtools.decompress(compressed_high).decode('utf-8'), original)

    def test_compress_dir_decompress_dir_preserves_nested_files(self):
        """Test directory compression and decompression with nested files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = os.path.join(temp_dir, 'source')
            output_dir = os.path.join(temp_dir, 'output')
            os.makedirs(os.path.join(source_dir, 'nested'))
            archive_path = os.path.join(temp_dir, 'archive.cjz')

            with open(os.path.join(source_dir, 'root.txt'), 'wb') as f:
                f.write(b'root data\n' * 50)
            with open(os.path.join(source_dir, 'nested', 'child.bin'), 'wb') as f:
                f.write(bytes(range(256)) * 4)

            compressed_file, stats = hashtools.compress_dir(source_dir, archive_path)
            extracted_dir = hashtools.decompress_dir(compressed_file, output_dir)

            self.assertEqual(extracted_dir, output_dir)
            self.assertEqual(stats.original_size, (len(b'root data\n') * 50) + (256 * 4))
            with open(os.path.join(output_dir, 'root.txt'), 'rb') as f:
                self.assertEqual(f.read(), b'root data\n' * 50)
            with open(os.path.join(output_dir, 'nested', 'child.bin'), 'rb') as f:
                self.assertEqual(f.read(), bytes(range(256)) * 4)

    def test_compress_dir_with_password_restores_nested_files(self):
        """Test encrypted directory archive round-trip with nested files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = os.path.join(temp_dir, 'source')
            output_dir = os.path.join(temp_dir, 'output')
            os.makedirs(os.path.join(source_dir, 'nested'))
            archive_path = os.path.join(temp_dir, 'archive.cjz')

            with open(os.path.join(source_dir, 'root.txt'), 'wb') as f:
                f.write(b'encrypted root data')
            with open(os.path.join(source_dir, 'nested', 'child.txt'), 'wb') as f:
                f.write(b'encrypted child data')

            compressed_file, stats = hashtools.compress_dir(source_dir, archive_path, password='password')

            self.assertTrue(hashtools.is_encrypted_archive(compressed_file))
            self.assertGreater(stats.compressed_size, 0)
            with self.assertRaises(hashtools.CompressionError):
                hashtools.decompress_dir(compressed_file, output_dir)

            hashtools.decompress_dir(compressed_file, output_dir, password='password')

            with open(os.path.join(output_dir, 'root.txt'), 'rb') as f:
                self.assertEqual(f.read(), b'encrypted root data')
            with open(os.path.join(output_dir, 'nested', 'child.txt'), 'rb') as f:
                self.assertEqual(f.read(), b'encrypted child data')

    def test_compress_dir_supports_streaming_and_mapped_strategies(self):
        """Test directory compression with streaming-compatible strategy mapping."""
        strategies = ('auto', 'zlib', 'bz2', 'lzma', 'rle')

        for strategy in strategies:
            with self.subTest(strategy=strategy):
                with tempfile.TemporaryDirectory() as temp_dir:
                    source_dir = os.path.join(temp_dir, 'source')
                    output_dir = os.path.join(temp_dir, 'output')
                    archive_path = os.path.join(temp_dir, f'{strategy}.cjz')
                    os.makedirs(source_dir)
                    with open(os.path.join(source_dir, 'data.txt'), 'wb') as f:
                        f.write(b'streaming directory compression\n' * 100)

                    compressed_file, stats = hashtools.compress_dir(source_dir, archive_path, strategy=strategy)
                    hashtools.decompress_dir(compressed_file, output_dir)

                    with open(os.path.join(output_dir, 'data.txt'), 'rb') as f:
                        self.assertEqual(f.read(), b'streaming directory compression\n' * 100)
                    self.assertIn(
                        stats.strategy,
                        {
                            hashtools.CompressionStrategy.ZLIB,
                            hashtools.CompressionStrategy.BZ2,
                            hashtools.CompressionStrategy.LZMA,
                        },
                    )

    def test_decompress_dir_supports_legacy_archive_format(self):
        """Test decompression of directory archives created by the legacy format."""
        import json
        import struct

        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, 'legacy.cjz')
            output_dir = os.path.join(temp_dir, 'output')
            file_content = b'legacy format data' * 20
            compressed_content, _ = hashtools.compress(file_content, strategy='zlib')
            metadata = {
                'version': 1,
                'file_count': 1,
                'total_size': len(file_content),
                'files': [
                    {
                        'path': 'nested/legacy.txt',
                        'original_size': len(file_content),
                        'compressed_size': len(compressed_content),
                    }
                ],
            }
            metadata_json = json.dumps(metadata).encode('utf-8')
            with open(archive_path, 'wb') as f:
                f.write(struct.pack('>I', len(metadata_json)))
                f.write(metadata_json)
                f.write(compressed_content)

            hashtools.decompress_dir(archive_path, output_dir)

            with open(os.path.join(output_dir, 'nested', 'legacy.txt'), 'rb') as f:
                self.assertEqual(f.read(), file_content)

    def test_compress_dir_handles_large_file_without_api_changes(self):
        """Test directory compression round-trip with a larger file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = os.path.join(temp_dir, 'source')
            output_dir = os.path.join(temp_dir, 'output')
            archive_path = os.path.join(temp_dir, 'large.cjz')
            os.makedirs(source_dir)
            chunk = b'large file compression data\n' * 1024
            with open(os.path.join(source_dir, 'large.bin'), 'wb') as f:
                for _ in range(128):
                    f.write(chunk)

            compressed_file, stats = hashtools.compress_dir(source_dir, archive_path)
            hashtools.decompress_dir(compressed_file, output_dir)

            self.assertEqual(stats.original_size, len(chunk) * 128)
            with open(os.path.join(output_dir, 'large.bin'), 'rb') as f:
                self.assertEqual(f.read(), chunk * 128)

    def test_compress_dir_does_not_include_output_archive_inside_source_dir(self):
        """Test directory compression excludes the archive being written."""
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = os.path.join(temp_dir, 'source')
            output_dir = os.path.join(temp_dir, 'output')
            archive_path = os.path.join(source_dir, 'archive.cjz')
            os.makedirs(source_dir)
            with open(os.path.join(source_dir, 'data.txt'), 'wb') as f:
                f.write(b'archive self exclusion data')

            compressed_file, stats = hashtools.compress_dir(source_dir, archive_path)
            hashtools.decompress_dir(compressed_file, output_dir)

            self.assertEqual(stats.original_size, len(b'archive self exclusion data'))
            self.assertEqual(os.listdir(output_dir), ['data.txt'])
            with open(os.path.join(output_dir, 'data.txt'), 'rb') as f:
                self.assertEqual(f.read(), b'archive self exclusion data')

    def test_decompress_dir_rejects_streaming_archive_path_traversal(self):
        """Test path traversal protection for streaming directory archives."""
        import struct

        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, 'unsafe.cjz')
            unsafe_path = b'../escape.txt'
            with open(archive_path, 'wb') as f:
                f.write(b"CJZD\x02")
                f.write(b'\x01')
                f.write(struct.pack('>I', len(unsafe_path)))
                f.write(unsafe_path)
                f.write(struct.pack('>Q', 0))
                f.write(b'\x10')

            with self.assertRaises(hashtools.CompressionError):
                hashtools.decompress_dir(archive_path, os.path.join(temp_dir, 'output'))

    def test_compress_dir_emits_info_logs(self):
        """Test directory compression logs start and finish events."""
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = os.path.join(temp_dir, 'source')
            archive_path = os.path.join(temp_dir, 'archive.cjz')
            os.makedirs(source_dir)
            with open(os.path.join(source_dir, 'data.txt'), 'wb') as f:
                f.write(b'logged compression data' * 10)

            with self.assertLogs('cereja.hashtools._compress', level='INFO') as logs:
                hashtools.compress_dir(source_dir, archive_path)

            self.assertTrue(any('Starting directory compression' in message for message in logs.output))
            self.assertTrue(any('Directory compression finished' in message for message in logs.output))

    def test_compress_dir_verbose_updates_progress(self):
        """Test directory compression updates progress when verbose is enabled."""
        class FakeProgress:
            def __init__(self):
                self.values = []

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def show_progress(self, value):
                self.values.append(value)

        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = os.path.join(temp_dir, 'source')
            archive_path = os.path.join(temp_dir, 'archive.cjz')
            os.makedirs(source_dir)
            data = b'progress compression data' * 100
            with open(os.path.join(source_dir, 'data.txt'), 'wb') as f:
                f.write(data)
            progress = FakeProgress()

            with mock.patch.object(_compress, '_create_progress', return_value=progress) as create_progress:
                hashtools.compress_dir(source_dir, archive_path, verbose=True)

            create_progress.assert_called_once()
            self.assertEqual(progress.values[-1], 1)

    def test_compress_dir_verbose_tracks_completed_file_count(self):
        """Test directory compression progress advances by completed files."""
        class FakeProgress:
            def __init__(self):
                self.values = []

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def show_progress(self, value):
                self.values.append(value)

        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = os.path.join(temp_dir, 'source')
            archive_path = os.path.join(temp_dir, 'archive.cjz')
            os.makedirs(source_dir)
            with open(os.path.join(source_dir, 'first.txt'), 'wb') as f:
                f.write(b'first file')
            with open(os.path.join(source_dir, 'second.txt'), 'wb') as f:
                f.write(b'second file')
            progress = FakeProgress()

            with mock.patch.object(_compress, '_create_progress', return_value=progress):
                hashtools.compress_dir(source_dir, archive_path, verbose=True)

            self.assertEqual(progress.values, [1, 2])

    def test_decompress_dir_verbose_updates_progress(self):
        """Test directory decompression updates progress when verbose is enabled."""
        class FakeProgress:
            def __init__(self):
                self.values = []

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def show_progress(self, value):
                self.values.append(value)

        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = os.path.join(temp_dir, 'source')
            output_dir = os.path.join(temp_dir, 'output')
            archive_path = os.path.join(temp_dir, 'archive.cjz')
            os.makedirs(source_dir)
            with open(os.path.join(source_dir, 'data.txt'), 'wb') as f:
                f.write(b'progress decompression data' * 100)
            hashtools.compress_dir(source_dir, archive_path)
            progress = FakeProgress()

            with mock.patch.object(_compress, '_create_progress', return_value=progress) as create_progress:
                hashtools.decompress_dir(archive_path, output_dir, verbose=True)

            create_progress.assert_called_once()
            self.assertEqual(progress.values[-1], 1)


if __name__ == "__main__":
    unittest.main()
