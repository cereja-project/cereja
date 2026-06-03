"""
Copyright (c) 2019 The Cereja Project

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import zlib
import bz2
import lzma
import struct
import base64
import logging
from enum import Enum
from typing import Union, Tuple, Dict, Any, Optional
from collections import Counter

logger = logging.getLogger(__name__)

__all__ = [
    "compress",
    "decompress",
    "compress_file",
    "decompress_file",
    "compress_dir",
    "decompress_dir",
    "analyze_data",
    "suggest_strategy",
    "get_compression_ratio",
    "CompressionStrategy",
    "CompressionError",
    "CompressionStats",
]


class CompressionError(Exception):
    """Exception raised for compression-related errors."""
    pass


class CompressionStrategy(Enum):
    """Available compression strategies."""
    AUTO = "auto"           # Auto-select best strategy
    DICTIONARY = "dict"     # Dictionary compression for repetitive text
    RLE = "rle"            # Run-length encoding for sequences
    DELTA = "delta"        # Delta encoding for sequential numbers
    BITPACK = "bitpack"    # Bit packing for limited range values
    HYBRID = "hybrid"      # Combination of strategies
    ZLIB = "zlib"          # zlib (DEFLATE)
    BZ2 = "bz2"            # bzip2
    LZMA = "lzma"          # LZMA


class CompressionStats:
    """Statistics about compression operation."""
    
    def __init__(self, original_size: int, compressed_size: int, 
                 strategy: CompressionStrategy, time_ms: float = 0):
        self.original_size = original_size
        self.compressed_size = compressed_size
        self.strategy = strategy
        self.time_ms = time_ms
        self.ratio = self.get_ratio()
        self.savings_percent = self.get_savings_percent()
    
    def get_ratio(self) -> float:
        """Get compression ratio (original/compressed)."""
        if self.compressed_size == 0:
            return float('inf')
        return self.original_size / self.compressed_size
    
    def get_savings_percent(self) -> float:
        """Get space savings percentage."""
        if self.original_size == 0:
            return 0.0
        return ((self.original_size - self.compressed_size) / self.original_size) * 100
    
    def __repr__(self):
        return (f"CompressionStats(ratio={self.ratio:.2f}x, "
                f"savings={self.savings_percent:.1f}%, "
                f"strategy={self.strategy.value})")


# ============================================================================
# Compression Strategy Implementations
# ============================================================================

def _compress_dictionary(data: bytes) -> bytes:
    """
    Dictionary-based compression for repetitive text.
    Builds a dictionary of common patterns and replaces them with tokens.
    """
    # Find common byte sequences (2-8 bytes)
    patterns = {}
    min_pattern_len = 2
    max_pattern_len = 8
    
    # Count patterns
    for length in range(max_pattern_len, min_pattern_len - 1, -1):
        for i in range(len(data) - length + 1):
            pattern = data[i:i+length]
            if pattern not in patterns:
                patterns[pattern] = 0
            patterns[pattern] += 1
    
    # Select most frequent patterns (up to 255)
    frequent = sorted(patterns.items(), key=lambda x: x[1] * len(x[0]), reverse=True)
    dictionary = {pattern: idx for idx, (pattern, _) in enumerate(frequent[:255])}
    
    if not dictionary:
        # No patterns found, use zlib
        return b'\x00' + zlib.compress(data, level=6)
    
    # Build compressed data
    compressed = bytearray()
    i = 0
    
    while i < len(data):
        # Try to match longest pattern
        matched = False
        for length in range(max_pattern_len, min_pattern_len - 1, -1):
            if i + length <= len(data):
                pattern = data[i:i+length]
                if pattern in dictionary:
                    # Write token (255 + token_id)
                    compressed.append(255)
                    compressed.append(dictionary[pattern])
                    i += length
                    matched = True
                    break
        
        if not matched:
            # Write literal byte
            if data[i] == 255:
                # Escape 255
                compressed.extend([255, 255])
            else:
                compressed.append(data[i])
            i += 1
    
    # Build header: marker + dict_size + dictionary + compressed_data
    header = bytearray([0x01])  # Dictionary marker
    header.append(len(dictionary))
    
    for pattern, token_id in sorted(dictionary.items(), key=lambda x: x[1]):
        header.append(len(pattern))
        header.extend(pattern)
    
    return bytes(header + compressed)


def _decompress_dictionary(data: bytes) -> bytes:
    """Decompress dictionary-compressed data."""
    if data[0] == 0x00:
        # Fallback to zlib
        return zlib.decompress(data[1:])
    
    if data[0] != 0x01:
        raise CompressionError("Invalid dictionary compression format")
    
    # Read dictionary
    dict_size = data[1]
    dictionary = {}
    pos = 2
    
    for _ in range(dict_size):
        pattern_len = data[pos]
        pos += 1
        pattern = data[pos:pos+pattern_len]
        pos += pattern_len
        dictionary[len(dictionary)] = pattern
    
    # Decompress data
    decompressed = bytearray()
    i = pos
    
    while i < len(data):
        if data[i] == 255:
            if i + 1 < len(data):
                if data[i+1] == 255:
                    # Escaped 255
                    decompressed.append(255)
                    i += 2
                else:
                    # Token
                    token_id = data[i+1]
                    decompressed.extend(dictionary[token_id])
                    i += 2
            else:
                i += 1
        else:
            decompressed.append(data[i])
            i += 1
    
    return bytes(decompressed)


def _compress_rle(data: bytes) -> bytes:
    """
    Run-Length Encoding compression.
    Encodes sequences of repeated bytes efficiently.
    """
    if not data:
        return b''
    
    compressed = bytearray()
    i = 0
    
    while i < len(data):
        # Count consecutive identical bytes
        current = data[i]
        count = 1
        
        while i + count < len(data) and data[i + count] == current and count < 255:
            count += 1
        
        if count >= 3:
            # Use RLE: marker (255) + count + byte
            compressed.extend([255, count, current])
            i += count
        else:
            # Write literal bytes
            for _ in range(count):
                if current == 255:
                    # Escape 255
                    compressed.extend([255, 1, 255])
                else:
                    compressed.append(current)
            i += count
    
    return bytes(compressed)


def _decompress_rle(data: bytes) -> bytes:
    """Decompress RLE-compressed data."""
    decompressed = bytearray()
    i = 0
    
    while i < len(data):
        if data[i] == 255 and i + 2 < len(data):
            # RLE sequence
            count = data[i + 1]
            byte_val = data[i + 2]
            decompressed.extend([byte_val] * count)
            i += 3
        else:
            decompressed.append(data[i])
            i += 1
    
    return bytes(decompressed)


def _compress_delta(data: bytes) -> bytes:
    """
    Delta encoding compression for sequential numeric data.
    Stores differences between consecutive values.
    """
    if len(data) < 4:
        # Too small for delta encoding
        return b'\x00' + data
    
    # Try to interpret as integers
    try:
        # Assume 4-byte integers
        if len(data) % 4 != 0:
            return b'\x00' + data
        
        values = []
        for i in range(0, len(data), 4):
            val = struct.unpack('>I', data[i:i+4])[0]
            values.append(val)
        
        # Calculate deltas
        deltas = [values[0]]  # First value as-is
        for i in range(1, len(values)):
            delta = values[i] - values[i-1]
            deltas.append(delta)
        
        # Check if deltas are smaller
        max_delta = max(abs(d) for d in deltas[1:]) if len(deltas) > 1 else 0
        
        if max_delta < 256:
            # Use 1-byte deltas
            compressed = bytearray([0x01])  # 1-byte delta marker
            compressed.extend(struct.pack('>I', deltas[0]))
            for delta in deltas[1:]:
                compressed.append((delta + 256) % 256)
            return bytes(compressed)
        elif max_delta < 65536:
            # Use 2-byte deltas
            compressed = bytearray([0x02])  # 2-byte delta marker
            compressed.extend(struct.pack('>I', deltas[0]))
            for delta in deltas[1:]:
                compressed.extend(struct.pack('>h', delta))
            return bytes(compressed)
        else:
            # Deltas not beneficial
            return b'\x00' + data
    
    except Exception:
        return b'\x00' + data


def _decompress_delta(data: bytes) -> bytes:
    """Decompress delta-encoded data."""
    if data[0] == 0x00:
        return data[1:]
    
    marker = data[0]
    first_value = struct.unpack('>I', data[1:5])[0]
    values = [first_value]
    
    if marker == 0x01:
        # 1-byte deltas
        for i in range(5, len(data)):
            delta = data[i]
            if delta > 127:
                delta = delta - 256
            values.append(values[-1] + delta)
    elif marker == 0x02:
        # 2-byte deltas
        for i in range(5, len(data), 2):
            delta = struct.unpack('>h', data[i:i+2])[0]
            values.append(values[-1] + delta)
    
    # Convert back to bytes
    result = bytearray()
    for val in values:
        result.extend(struct.pack('>I', val & 0xFFFFFFFF))
    
    return bytes(result)


def _compress_bitpack(data: bytes) -> bytes:
    """
    Bit packing compression for data with limited value range.
    Uses only necessary bits per value.
    """
    if not data:
        return b''
    
    # Find max value
    max_val = max(data)
    
    # Calculate bits needed
    bits_needed = max_val.bit_length()
    
    if bits_needed >= 8:
        # No benefit
        return b'\x00' + data
    
    # Pack bits
    compressed = bytearray([bits_needed])
    bit_buffer = 0
    bit_count = 0
    
    for byte_val in data:
        bit_buffer = (bit_buffer << bits_needed) | byte_val
        bit_count += bits_needed
        
        while bit_count >= 8:
            bit_count -= 8
            compressed.append((bit_buffer >> bit_count) & 0xFF)
    
    # Write remaining bits
    if bit_count > 0:
        compressed.append((bit_buffer << (8 - bit_count)) & 0xFF)
    
    return bytes(compressed)


def _decompress_bitpack(data: bytes) -> bytes:
    """Decompress bit-packed data."""
    if data[0] == 0x00:
        return data[1:]
    
    bits_needed = data[0]
    decompressed = bytearray()
    
    bit_buffer = 0
    bit_count = 0
    
    for byte_val in data[1:]:
        bit_buffer = (bit_buffer << 8) | byte_val
        bit_count += 8
        
        while bit_count >= bits_needed:
            bit_count -= bits_needed
            value = (bit_buffer >> bit_count) & ((1 << bits_needed) - 1)
            decompressed.append(value)
    
    return bytes(decompressed)


# ============================================================================
# Data Analysis
# ============================================================================

def analyze_data(data: Union[str, bytes]) -> Dict[str, Any]:
    """
    Analyze data characteristics to suggest best compression strategy.
    
    Returns:
        Dictionary with analysis results
    """
    if isinstance(data, str):
        data = data.encode('utf-8')
    
    if not data:
        return {
            'size': 0,
            'entropy': 0,
            'repetition_ratio': 0,
            'sequential_ratio': 0,
            'unique_ratio': 0,
            'max_value': 0,
            'suggested_strategy': CompressionStrategy.ZLIB
        }
    
    size = len(data)
    
    # Calculate byte frequency
    freq = Counter(data)
    
    # Calculate entropy
    import math
    entropy = 0
    for count in freq.values():
        p = count / size
        if p > 0:
            entropy -= p * math.log2(p)
    
    # Calculate repetition ratio (RLE potential)
    runs = 0
    run_length = 1
    for i in range(1, len(data)):
        if data[i] == data[i-1]:
            run_length += 1
        else:
            if run_length >= 3:
                runs += run_length
            run_length = 1
    # Account for the last run
    if run_length >= 3:
        runs += run_length
    repetition_ratio = runs / size if size > 0 else 0
    
    # Calculate sequential ratio (Delta potential)
    sequential = 0
    if len(data) >= 8 and len(data) % 4 == 0:
        try:
            values = [struct.unpack('>I', data[i:i+4])[0] for i in range(0, len(data), 4)]
            for i in range(1, len(values)):
                if abs(values[i] - values[i-1]) < 256:
                    sequential += 1
            sequential_ratio = sequential / (len(values) - 1) if len(values) > 1 else 0
        except Exception:
            sequential_ratio = 0
    else:
        sequential_ratio = 0
    
    # Calculate unique byte ratio
    unique_ratio = len(freq) / 256
    
    return {
        'size': size,
        'entropy': entropy,
        'repetition_ratio': repetition_ratio,
        'sequential_ratio': sequential_ratio,
        'unique_ratio': unique_ratio,
        'max_value': max(data) if data else 0,
    }


def suggest_strategy(data: Union[str, bytes]) -> CompressionStrategy:
    """
    Suggest best compression strategy based on data analysis.
    
    Args:
        data: Data to analyze
    
    Returns:
        Suggested CompressionStrategy
    """
    analysis = analyze_data(data)
    
    # Decision tree based on data characteristics
    # Check RLE first for extremely repetitive data
    if analysis['repetition_ratio'] > 0.9:
        return CompressionStrategy.RLE
    # Check sequential (sequential integers have repeating bytes)
    elif analysis['sequential_ratio'] > 0.8:
        return CompressionStrategy.DELTA
    # Check for small value range (bitpack)
    elif analysis['max_value'] < 16 and analysis['size'] > 100:
        return CompressionStrategy.BITPACK
    # Check for very large data (LZMA is usually best)
    elif analysis['size'] > 10000:
        return CompressionStrategy.LZMA
    # Check RLE for moderately repetitive data
    elif analysis['repetition_ratio'] > 0.5:
        return CompressionStrategy.RLE
    elif analysis['entropy'] < 4 and analysis['size'] > 1000:
        return CompressionStrategy.DICTIONARY
    elif analysis['size'] > 1000:
        return CompressionStrategy.BZ2
    else:
        return CompressionStrategy.ZLIB


# ============================================================================
# Main Compression Functions
# ============================================================================

def compress(data: Union[str, bytes], strategy: Union[str, CompressionStrategy] = 'auto', 
             level: int = 6) -> Tuple[bytes, CompressionStats]:
    """
    Compress data using specified or auto-selected strategy.
    
    Args:
        data: Data to compress
        strategy: Compression strategy (default: 'auto')
        level: Compression level 1-9 for stdlib methods (default: 6)
    
    Returns:
        Tuple of (compressed_data, compression_stats)
    
    Raises:
        CompressionError: If compression fails
    """
    import time
    start_time = time.time()
    
    try:
        # Convert to bytes
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        original_size = len(data)
        
        # Convert strategy
        if isinstance(strategy, str):
            if strategy == 'auto':
                strategy = CompressionStrategy.AUTO
            else:
                strategy = CompressionStrategy(strategy)
        
        # Auto-select strategy
        if strategy == CompressionStrategy.AUTO:
            strategy = suggest_strategy(data)
        
        # Compress based on strategy
        if strategy == CompressionStrategy.DICTIONARY:
            compressed = _compress_dictionary(data)
            marker = b'\x01'
        elif strategy == CompressionStrategy.RLE:
            compressed = _compress_rle(data)
            marker = b'\x02'
        elif strategy == CompressionStrategy.DELTA:
            compressed = _compress_delta(data)
            marker = b'\x03'
        elif strategy == CompressionStrategy.BITPACK:
            compressed = _compress_bitpack(data)
            marker = b'\x04'
        elif strategy == CompressionStrategy.ZLIB:
            compressed = zlib.compress(data, level=level)
            marker = b'\x10'
        elif strategy == CompressionStrategy.BZ2:
            compressed = bz2.compress(data, compresslevel=level)
            marker = b'\x11'
        elif strategy == CompressionStrategy.LZMA:
            compressed = lzma.compress(data, preset=level)
            marker = b'\x12'
        elif strategy == CompressionStrategy.HYBRID:
            # Try multiple strategies and pick best
            strategies = [
                (CompressionStrategy.DICTIONARY, _compress_dictionary(data), b'\x01'),
                (CompressionStrategy.RLE, _compress_rle(data), b'\x02'),
                (CompressionStrategy.ZLIB, zlib.compress(data, level=level), b'\x10'),
            ]
            best = min(strategies, key=lambda x: len(x[1]))
            strategy, compressed, marker = best
        else:
            raise CompressionError(f"Unknown strategy: {strategy}")
        
        # Add marker to identify compression method
        result = marker + compressed
        
        elapsed_ms = (time.time() - start_time) * 1000
        stats = CompressionStats(original_size, len(result), strategy, elapsed_ms)
        
        return result, stats
    
    except Exception as e:
        raise CompressionError(f"Compression failed: {str(e)}")


def decompress(data: bytes) -> bytes:
    """
    Decompress data (automatically detects compression strategy).
    
    Args:
        data: Compressed data
    
    Returns:
        Decompressed data
    
    Raises:
        CompressionError: If decompression fails
    """
    try:
        if not data:
            return b''
        
        # Read marker
        marker = data[0:1]
        compressed = data[1:]
        
        if marker == b'\x01':
            return _decompress_dictionary(compressed)
        elif marker == b'\x02':
            return _decompress_rle(compressed)
        elif marker == b'\x03':
            return _decompress_delta(compressed)
        elif marker == b'\x04':
            return _decompress_bitpack(compressed)
        elif marker == b'\x10':
            return zlib.decompress(compressed)
        elif marker == b'\x11':
            return bz2.decompress(compressed)
        elif marker == b'\x12':
            return lzma.decompress(compressed)
        else:
            raise CompressionError(f"Unknown compression marker: {marker}")
    
    except Exception as e:
        raise CompressionError(f"Decompression failed: {str(e)}")


def compress_file(file_path: str, output_path: str = None,
                  strategy: Union[str, CompressionStrategy] = 'auto',
                  verbose: bool = False) -> Tuple[str, CompressionStats]:
    """
    Compress file contents.
    
    Args:
        file_path: Path to file to compress
        output_path: Path for compressed file (if None, uses file_path + '.cjz')
        strategy: Compression strategy (default: 'auto')
        verbose: Whether to show progress while compressing (default: False)
    
    Returns:
        Tuple of (output_path, compression_stats)
    
    Raises:
        CompressionError: If compression fails
        FileNotFoundError: If input file doesn't exist
    """
    import os
    from contextlib import nullcontext

    try:
        progress = _create_progress(verbose, "Compressing file", 1)

        with progress if progress is not None else nullcontext() as active_progress:
            with open(file_path, 'rb') as f:
                data = f.read()
            if active_progress is not None:
                active_progress.show_progress(1)
        
        # Compress
        compressed, stats = compress(data, strategy=strategy)
        
        # Determine output path
        if output_path is None:
            output_path = file_path + '.cjz'
        
        # Write compressed file
        with open(output_path, 'wb') as f:
            f.write(compressed)
        
        return output_path, stats
    
    except FileNotFoundError:
        raise
    except Exception as e:
        raise CompressionError(f"File compression failed: {str(e)}")


def decompress_file(file_path: str, output_path: str = None, verbose: bool = False) -> str:
    """
    Decompress file contents.
    
    Args:
        file_path: Path to compressed file
        output_path: Path for decompressed file (if None, removes '.cjz' extension)
        verbose: Whether to show progress while decompressing (default: False)
    
    Returns:
        Path to decompressed file
    
    Raises:
        CompressionError: If decompression fails
        FileNotFoundError: If input file doesn't exist
    """
    import os
    from contextlib import nullcontext

    try:
        progress = _create_progress(verbose, "Decompressing file", 1)

        with progress if progress is not None else nullcontext() as active_progress:
            with open(file_path, 'rb') as f:
                compressed_data = f.read()
            if active_progress is not None:
                active_progress.show_progress(1)
        
        # Decompress
        decompressed = decompress(compressed_data)
        
        # Determine output path
        if output_path is None:
            if file_path.endswith('.cjz'):
                output_path = file_path[:-4]
            else:
                output_path = file_path + '.decompressed'
        
        # Write decompressed file
        with open(output_path, 'wb') as f:
            f.write(decompressed)
        
        return output_path
    
    except FileNotFoundError:
        raise
    except Exception as e:
        raise CompressionError(f"File decompression failed: {str(e)}")


def get_compression_ratio(original: Union[str, bytes], compressed: bytes) -> float:
    """
    Calculate compression ratio.
    
    Args:
        original: Original data
        compressed: Compressed data
    
    Returns:
        Compression ratio (original_size / compressed_size)
    """
    if isinstance(original, str):
        original = original.encode('utf-8')
    
    if len(compressed) == 0:
        return float('inf')
    
    return len(original) / len(compressed)


_DIR_ARCHIVE_MAGIC = b"CJZD\x02"
_DIR_RECORD_FILE = b"\x01"
_DIR_RECORD_END = b"\x00"
_DIR_CHUNK_SIZE = 1024 * 1024
_DIR_STREAM_MARKERS = {
    CompressionStrategy.ZLIB: b'\x10',
    CompressionStrategy.BZ2: b'\x11',
    CompressionStrategy.LZMA: b'\x12',
}
_DIR_STREAM_STRATEGIES = {marker: strategy for strategy, marker in _DIR_STREAM_MARKERS.items()}


def _iter_directory_files(dir_path: str, exclude_path: str = None):
    import os

    exclude_abs = os.path.abspath(exclude_path) if exclude_path is not None else None

    for root, dirs, files in os.walk(dir_path):
        dirs.sort()
        files.sort()

        for filename in files:
            file_path = os.path.join(root, filename)
            if exclude_abs is not None and os.path.abspath(file_path) == exclude_abs:
                continue
            rel_path = os.path.relpath(file_path, dir_path).replace('\\', '/')
            yield file_path, rel_path


def _get_directory_file_count(dir_path: str, exclude_path: str = None) -> int:
    return sum(1 for _ in _iter_directory_files(dir_path, exclude_path=exclude_path))


def _create_progress(enabled: bool, name: str, max_value: Optional[int] = None):
    if not enabled:
        return None

    from cereja.display import Progress

    return Progress(name=name, max_value=max_value, states=("value", "bar", "percent", "time"))


def _normalize_dir_strategy(strategy: Union[str, CompressionStrategy]) -> CompressionStrategy:
    if isinstance(strategy, str):
        if strategy == 'auto':
            strategy = CompressionStrategy.AUTO
        else:
            strategy = CompressionStrategy(strategy)

    if strategy in (CompressionStrategy.BZ2, CompressionStrategy.LZMA):
        return strategy

    return CompressionStrategy.ZLIB


def _create_dir_compressor(strategy: CompressionStrategy, level: int = 6):
    if strategy == CompressionStrategy.BZ2:
        return bz2.BZ2Compressor(level)
    if strategy == CompressionStrategy.LZMA:
        return lzma.LZMACompressor(preset=level)
    return zlib.compressobj(level)


def _create_dir_decompressor(strategy: CompressionStrategy):
    if strategy == CompressionStrategy.BZ2:
        return bz2.BZ2Decompressor()
    if strategy == CompressionStrategy.LZMA:
        return lzma.LZMADecompressor()
    return zlib.decompressobj()


def _read_exact(file_obj, size: int) -> bytes:
    data = file_obj.read(size)
    if len(data) != size:
        raise CompressionError("Unexpected end of directory archive")
    return data


def _write_sized_chunk(file_obj, data: bytes) -> None:
    if data:
        file_obj.write(struct.pack('>I', len(data)))
        file_obj.write(data)


def _read_uint32(file_obj) -> int:
    return struct.unpack('>I', _read_exact(file_obj, 4))[0]


def _read_uint64(file_obj) -> int:
    return struct.unpack('>Q', _read_exact(file_obj, 8))[0]


def _count_dir_stream_files(archive_path: str) -> int:
    file_count = 0

    with open(archive_path, 'rb') as archive:
        _read_exact(archive, len(_DIR_ARCHIVE_MAGIC))

        while True:
            record_type = _read_exact(archive, 1)
            if record_type == _DIR_RECORD_END:
                break
            if record_type != _DIR_RECORD_FILE:
                raise CompressionError(f"Invalid directory archive record: {record_type}")

            path_length = _read_uint32(archive)
            _read_exact(archive, path_length)
            _read_uint64(archive)
            marker = _read_exact(archive, 1)

            if marker not in _DIR_STREAM_STRATEGIES:
                raise CompressionError(f"Unknown directory compression marker: {marker}")

            while True:
                chunk_size = _read_uint32(archive)
                if chunk_size == 0:
                    break
                _read_exact(archive, chunk_size)

            file_count += 1

    return file_count


def _safe_archive_path(output_dir: str, archive_file_path: str) -> str:
    import os

    normalized_path = archive_file_path.replace('\\', '/')
    if not normalized_path or normalized_path.startswith('/') or normalized_path.startswith('../'):
        raise CompressionError(f"Unsafe archive path: {archive_file_path}")

    output_dir_abs = os.path.abspath(output_dir)
    file_path = os.path.abspath(os.path.join(output_dir_abs, normalized_path.replace('/', os.sep)))

    if os.path.commonpath([output_dir_abs, file_path]) != output_dir_abs:
        raise CompressionError(f"Unsafe archive path: {archive_file_path}")

    return file_path


def _get_default_output_dir(archive_path: str) -> str:
    if archive_path.endswith('.cjz'):
        return archive_path[:-4]
    return archive_path + '_extracted'


def compress_dir(dir_path: str, output_path: str = None,
                 strategy: Union[str, CompressionStrategy] = 'auto',
                 verbose: bool = False) -> Tuple[str, CompressionStats]:
    """
    Compress entire directory recursively.
    
    Creates a single compressed archive containing all files and subdirectories.
    Preserves directory structure and relative paths.
    
    Args:
        dir_path: Path to directory to compress
        output_path: Path for compressed archive (if None, uses dir_path + '.cjz')
        strategy: Compression strategy (default: 'auto')
        verbose: Whether to show progress while compressing (default: False)
    
    Returns:
        Tuple of (output_path, compression_stats)
    
    Raises:
        CompressionError: If compression fails
        FileNotFoundError: If directory doesn't exist
        NotADirectoryError: If path is not a directory
    
    Example:
        >>> import cereja as cj
        >>> # Compress entire project directory
        >>> archive, stats = cj.hashtools.compress_dir('./my_project')
        >>> print(f"Compressed to {archive} with {stats.ratio:.2f}x ratio")
    """
    import os
    import time
    from contextlib import nullcontext
    
    try:
        if not os.path.exists(dir_path):
            raise FileNotFoundError(f"Directory not found: {dir_path}")
        
        if not os.path.isdir(dir_path):
            raise NotADirectoryError(f"Path is not a directory: {dir_path}")

        if output_path is None:
            output_path = dir_path.rstrip('/\\') + '.cjz'
        output_path_abs = os.path.abspath(output_path)

        start_time = time.time()
        total_size = 0
        file_count = 0
        effective_strategy = _normalize_dir_strategy(strategy)
        marker = _DIR_STREAM_MARKERS[effective_strategy]
        progress_total = max(_get_directory_file_count(dir_path, exclude_path=output_path_abs), 1) if verbose else None
        progress = _create_progress(verbose, "Compressing directory", progress_total)

        logger.info(
            "Starting directory compression: %s",
            dir_path,
            extra={
                "dir_path": dir_path,
                "output_path": output_path,
                "strategy": effective_strategy.value,
            },
        )

        with progress if progress is not None else nullcontext() as active_progress:
            with open(output_path_abs, 'wb') as archive:
                archive.write(_DIR_ARCHIVE_MAGIC)

                for file_path, rel_path in _iter_directory_files(dir_path, exclude_path=output_path_abs):
                    try:
                        original_size = os.path.getsize(file_path)
                        source = open(file_path, 'rb')
                    except OSError:
                        logger.warning("Skipping unreadable file during directory compression: %s", file_path, exc_info=True)
                        continue

                    with source:
                        path_bytes = rel_path.encode('utf-8')
                        compressor = _create_dir_compressor(effective_strategy)

                        archive.write(_DIR_RECORD_FILE)
                        archive.write(struct.pack('>I', len(path_bytes)))
                        archive.write(path_bytes)
                        archive.write(struct.pack('>Q', original_size))
                        archive.write(marker)

                        while True:
                            chunk = source.read(_DIR_CHUNK_SIZE)
                            if not chunk:
                                break
                            total_size += len(chunk)
                            _write_sized_chunk(archive, compressor.compress(chunk))

                        _write_sized_chunk(archive, compressor.flush())
                        archive.write(struct.pack('>I', 0))
                        file_count += 1
                        if active_progress is not None:
                            active_progress.show_progress(file_count)

                archive.write(_DIR_RECORD_END)

        if file_count == 0:
            try:
                os.remove(output_path_abs)
            except OSError:
                # Best effort cleanup of an archive created by this failed call.
                pass
            raise CompressionError("No files found in directory")

        elapsed_ms = (time.time() - start_time) * 1000
        compressed_size = os.path.getsize(output_path_abs)
        stats = CompressionStats(
            total_size,
            compressed_size,
            effective_strategy,
            elapsed_ms
        )

        logger.info(
            "Directory compression finished: %s",
            output_path,
            extra={
                "dir_path": dir_path,
                "output_path": output_path,
                "file_count": file_count,
                "original_size": total_size,
                "compressed_size": compressed_size,
                "strategy": effective_strategy.value,
            },
        )

        return output_path, stats

    except (FileNotFoundError, NotADirectoryError):
        raise
    except Exception as e:
        raise CompressionError(f"Directory compression failed: {str(e)}") from e


def _decompress_dir_stream(archive_path: str, output_dir: str, verbose: bool = False) -> str:
    import os
    from contextlib import nullcontext

    os.makedirs(output_dir, exist_ok=True)
    file_count = _count_dir_stream_files(archive_path) if verbose else None
    progress = _create_progress(verbose, "Decompressing directory", max(file_count or 0, 1))
    extracted_count = 0

    with progress if progress is not None else nullcontext() as active_progress:
        with open(archive_path, 'rb') as archive:
            _read_exact(archive, len(_DIR_ARCHIVE_MAGIC))

            while True:
                record_type = _read_exact(archive, 1)
                if record_type == _DIR_RECORD_END:
                    break
                if record_type != _DIR_RECORD_FILE:
                    raise CompressionError(f"Invalid directory archive record: {record_type}")

                path_length = _read_uint32(archive)
                path = _read_exact(archive, path_length).decode('utf-8')
                _read_uint64(archive)
                marker = _read_exact(archive, 1)

                if marker not in _DIR_STREAM_STRATEGIES:
                    raise CompressionError(f"Unknown directory compression marker: {marker}")

                file_path = _safe_archive_path(output_dir, path)
                parent_dir = os.path.dirname(file_path)
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)

                decompressor = _create_dir_decompressor(_DIR_STREAM_STRATEGIES[marker])
                with open(file_path, 'wb') as output_file:
                    while True:
                        chunk_size = _read_uint32(archive)
                        if chunk_size == 0:
                            break

                        compressed_chunk = _read_exact(archive, chunk_size)
                        decompressed_chunk = decompressor.decompress(compressed_chunk)
                        if decompressed_chunk:
                            output_file.write(decompressed_chunk)

                    flush = getattr(decompressor, "flush", None)
                    if flush is not None:
                        remaining = flush()
                        if remaining:
                            output_file.write(remaining)

                extracted_count += 1
                if active_progress is not None:
                    active_progress.show_progress(extracted_count)

    return output_dir


def _decompress_dir_legacy(archive_path: str, output_dir: str, verbose: bool = False) -> str:
    import os
    import json
    from contextlib import nullcontext

    with open(archive_path, 'rb') as f:
        archive_data = f.read()

    metadata_length = struct.unpack('>I', archive_data[0:4])[0]
    metadata_json = archive_data[4:4+metadata_length]
    metadata = json.loads(metadata_json.decode('utf-8'))

    os.makedirs(output_dir, exist_ok=True)

    offset = 4 + metadata_length
    progress = _create_progress(verbose, "Decompressing directory", max(len(metadata['files']), 1))

    with progress if progress is not None else nullcontext() as active_progress:
        for index, file_info in enumerate(metadata['files'], start=1):
            compressed_size = file_info['compressed_size']
            compressed_content = archive_data[offset:offset+compressed_size]
            offset += compressed_size

            decompressed_content = decompress(compressed_content)
            file_path = _safe_archive_path(output_dir, file_info['path'])
            parent_dir = os.path.dirname(file_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

            with open(file_path, 'wb') as f:
                f.write(decompressed_content)
            if active_progress is not None:
                active_progress.show_progress(index)

    return output_dir


def decompress_dir(archive_path: str, output_dir: str = None, verbose: bool = False) -> str:
    """
    Decompress directory archive.
    
    Extracts all files and recreates directory structure.
    
    Args:
        archive_path: Path to compressed archive (.cjz)
        output_dir: Path for extracted directory (if None, removes '.cjz' extension)
        verbose: Whether to show progress while decompressing (default: False)
    
    Returns:
        Path to extracted directory
    
    Raises:
        CompressionError: If decompression fails
        FileNotFoundError: If archive doesn't exist
    
    Example:
        >>> import cereja as cj
        >>> # Decompress archive
        >>> extracted_dir = cj.hashtools.decompress_dir('./my_project.cjz')
        >>> print(f"Extracted to {extracted_dir}")
    """
    import os
    
    try:
        if not os.path.exists(archive_path):
            raise FileNotFoundError(f"Archive not found: {archive_path}")

        if output_dir is None:
            output_dir = _get_default_output_dir(archive_path)

        logger.info(
            "Starting directory decompression: %s",
            archive_path,
            extra={"archive_path": archive_path, "output_dir": output_dir},
        )

        with open(archive_path, 'rb') as archive:
            magic = archive.read(len(_DIR_ARCHIVE_MAGIC))

        if magic == _DIR_ARCHIVE_MAGIC:
            result = _decompress_dir_stream(archive_path, output_dir, verbose=verbose)
        else:
            result = _decompress_dir_legacy(archive_path, output_dir, verbose=verbose)

        logger.info(
            "Directory decompression finished: %s",
            output_dir,
            extra={"archive_path": archive_path, "output_dir": output_dir},
        )
        return result
    
    except FileNotFoundError:
        raise
    except Exception as e:
        raise CompressionError(f"Directory decompression failed: {str(e)}") from e
