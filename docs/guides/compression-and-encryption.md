# Compression and Encryption

Cereja can compress files and directories with the Python API or with the `cereja` CLI.

## Compress a File

```python
from cereja.hashtools import compress_file

output_path, stats = compress_file("report.txt", "report.txt.cjz")

print(output_path)
print(stats.strategy)
print(stats.savings_percent)
```

## Compress a Directory

```python
from cereja.hashtools import compress_dir

output_path, stats = compress_dir("dataset", "dataset.cjz")
```

When the output archive is inside the source directory, Cereja excludes the output archive from the input file list.

## Choose a Strategy

```python
from cereja.hashtools import compress_file

compress_file("data.bin", "data.bin.cjz", strategy="zlib")
```

Supported strategies include `auto`, `dict`, `rle`, `delta`, `bitpack`, `zlib`, `bz2`, `lzma`, and `hybrid`.

## Show or Hide Progress

The Python API accepts `verbose`:

```python
from cereja.hashtools import compress_dir

compress_dir("dataset", "dataset.cjz", verbose=True)
compress_dir("dataset", "dataset.cjz", verbose=False)
```

The CLI keeps progress active by default and disables it with `--quiet`.

## Encrypted Archives

```python
from cereja.hashtools import compress_file, decompress_file

compress_file("report.txt", "report.txt.cjz", password="secret")
decompress_file("report.txt.cjz", "report.txt", password="secret")
```

Passwords are required to read encrypted archives. The CLI prompts securely when `--encrypt` is used or when an encrypted
archive is decompressed.

## Direct File Encryption

Direct file encryption uses only the Python standard library.

```python
from cereja.hashtools import encrypt_file, decrypt_file

encrypt_file("report.txt", "secret", "report.txt.enc")
decrypt_file("report.txt.enc", "secret", "report.txt", overwrite=True)
```

Existing output files require `overwrite=True` in Python or `--force` in the CLI.
The input and output must be different files, including hard-link and symbolic-link
aliases. Authentication finishes before any plaintext is written. Output is
prepared in a temporary file in the destination directory and published atomically.
Without overwrite permission, publication uses a hard link and fails safely on
filesystems that do not support it. With permission, it uses atomic replacement.
These helpers process the whole file in memory; they are not streaming APIs.

### Data and format compatibility

`encrypt(data, password)` returns text and `decrypt(text, password)` returns bytes.
Strings and other non-bytes values, including dictionaries and lists, use UTF-8
encoded `str(data)`, preserving the historical contract. For JSON, explicitly pass
`json.dumps(data)` and decode the result with `json.loads`.

The historical format is preserved for both reading and writing: strict Base64
of a 16-byte salt, a 16-byte IV, ciphertext, and a 32-byte HMAC-SHA256 tag.
PBKDF2-HMAC-SHA256 derives 32 bytes with 100,000 iterations; the two 16-byte
halves serve the historical keystream and authentication roles. Salt and IV
are randomly generated for every encryption. Authentication covers the salt,
IV and ciphertext and is checked before generating the decryption keystream.
Malformed Base64 is rejected, including extraneous whitespace or punctuation.

This custom cryptographic construction is retained for compatibility. The changes
to validation and file handling do not establish its cryptographic security or
replace an independent security assessment. No new encryption format, external
backend or executable is introduced.

Encrypted compression archives retain their separate existing format.

### Crypto performance

The historical keystream reuses the HMAC state for its common key/IV prefix.
XOR uses integer operations in blocks of at most 64 KiB, preserving the same
bytes and format without external dependencies. These are CPU optimizations,
not streaming: the file helpers still load the complete input and generate the
complete keystream, and the bytes-returning XOR helper still allocates its output.

Run `python benchmarks/crypto.py --samples 7` from the checkout to compare against
the historical primitives. The benchmark alternates variants and reports median
encryption/decryption times and separate Python allocation peaks. Input buffers
are allocated before tracing; these peaks are not total process memory. It
excludes file I/O and does not establish cryptographic security.
