import unittest
import os
import tempfile
from cereja import hashtools


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
        original = "Test data " * 100
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


if __name__ == "__main__":
    unittest.main()
