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
from enum import Enum
from typing import Union, Tuple, Dict, Any
from collections import Counter

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
                  strategy: Union[str, CompressionStrategy] = 'auto') -> Tuple[str, CompressionStats]:
    """
    Compress file contents.
    
    Args:
        file_path: Path to file to compress
        output_path: Path for compressed file (if None, uses file_path + '.cjz')
        strategy: Compression strategy (default: 'auto')
    
    Returns:
        Tuple of (output_path, compression_stats)
    
    Raises:
        CompressionError: If compression fails
        FileNotFoundError: If input file doesn't exist
    """
    try:
        # Read file
        with open(file_path, 'rb') as f:
            data = f.read()
        
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


def decompress_file(file_path: str, output_path: str = None) -> str:
    """
    Decompress file contents.
    
    Args:
        file_path: Path to compressed file
        output_path: Path for decompressed file (if None, removes '.cjz' extension)
    
    Returns:
        Path to decompressed file
    
    Raises:
        CompressionError: If decompression fails
        FileNotFoundError: If input file doesn't exist
    """
    try:
        # Read compressed file
        with open(file_path, 'rb') as f:
            compressed_data = f.read()
        
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


def compress_dir(dir_path: str, output_path: str = None, 
                 strategy: Union[str, CompressionStrategy] = 'auto') -> Tuple[str, CompressionStats]:
    """
    Compress entire directory recursively.
    
    Creates a single compressed archive containing all files and subdirectories.
    Preserves directory structure and relative paths.
    
    Args:
        dir_path: Path to directory to compress
        output_path: Path for compressed archive (if None, uses dir_path + '.cjz')
        strategy: Compression strategy (default: 'auto')
    
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
    import json
    
    try:
        if not os.path.exists(dir_path):
            raise FileNotFoundError(f"Directory not found: {dir_path}")
        
        if not os.path.isdir(dir_path):
            raise NotADirectoryError(f"Path is not a directory: {dir_path}")
        
        # Collect all files recursively
        files_data = []
        total_size = 0
        
        for root, dirs, files in os.walk(dir_path):
            for filename in files:
                file_path = os.path.join(root, filename)
                # Get relative path from base directory
                rel_path = os.path.relpath(file_path, dir_path)
                
                # Read file content
                try:
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    
                    files_data.append({
                        'path': rel_path.replace('\\', '/'),  # Use forward slashes for cross-platform
                        'size': len(content),
                        'content': content
                    })
                    total_size += len(content)
                except Exception as e:
                    # Skip files that can't be read
                    print(f"Warning: Skipping {file_path}: {str(e)}")
                    continue
        
        if not files_data:
            raise CompressionError("No files found in directory")
        
        # Create archive structure
        # Format: [metadata_json_length:4bytes][metadata_json][file1_compressed][file2_compressed]...
        archive = bytearray()
        
        # Build metadata
        metadata = {
            'version': 1,
            'file_count': len(files_data),
            'total_size': total_size,
            'files': []
        }
        
        # Compress each file
        compressed_files = []
        for file_info in files_data:
            compressed_content, _ = compress(file_info['content'], strategy=strategy)
            compressed_files.append(compressed_content)
            
            metadata['files'].append({
                'path': file_info['path'],
                'original_size': file_info['size'],
                'compressed_size': len(compressed_content)
            })
        
        # Serialize metadata
        metadata_json = json.dumps(metadata).encode('utf-8')
        metadata_length = len(metadata_json)
        
        # Build archive
        archive.extend(struct.pack('>I', metadata_length))
        archive.extend(metadata_json)
        
        for compressed_content in compressed_files:
            archive.extend(compressed_content)
        
        # Determine output path
        if output_path is None:
            output_path = dir_path.rstrip('/\\') + '.cjz'
        
        # Write archive
        with open(output_path, 'wb') as f:
            f.write(archive)
        
        # Calculate stats
        stats = CompressionStats(
            total_size,
            len(archive),
            CompressionStrategy.HYBRID,  # Directory uses multiple strategies
            0
        )
        
        return output_path, stats
    
    except (FileNotFoundError, NotADirectoryError):
        raise
    except Exception as e:
        raise CompressionError(f"Directory compression failed: {str(e)}")


def decompress_dir(archive_path: str, output_dir: str = None) -> str:
    """
    Decompress directory archive.
    
    Extracts all files and recreates directory structure.
    
    Args:
        archive_path: Path to compressed archive (.cjz)
        output_dir: Path for extracted directory (if None, removes '.cjz' extension)
    
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
    import json
    
    try:
        if not os.path.exists(archive_path):
            raise FileNotFoundError(f"Archive not found: {archive_path}")
        
        # Read archive
        with open(archive_path, 'rb') as f:
            archive_data = f.read()
        
        # Read metadata length
        metadata_length = struct.unpack('>I', archive_data[0:4])[0]
        
        # Read metadata
        metadata_json = archive_data[4:4+metadata_length]
        metadata = json.loads(metadata_json.decode('utf-8'))
        
        # Determine output directory
        if output_dir is None:
            if archive_path.endswith('.cjz'):
                output_dir = archive_path[:-4]
            else:
                output_dir = archive_path + '_extracted'
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Decompress files
        offset = 4 + metadata_length
        
        for file_info in metadata['files']:
            compressed_size = file_info['compressed_size']
            compressed_content = archive_data[offset:offset+compressed_size]
            offset += compressed_size
            
            # Decompress
            decompressed_content = decompress(compressed_content)
            
            # Create file path
            file_path = os.path.join(output_dir, file_info['path'].replace('/', os.sep))
            
            # Create parent directories if needed
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Write file
            with open(file_path, 'wb') as f:
                f.write(decompressed_content)
        
        return output_dir
    
    except FileNotFoundError:
        raise
    except Exception as e:
        raise CompressionError(f"Directory decompression failed: {str(e)}")
