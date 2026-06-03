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

```python
from cereja.hashtools import encrypt_file, decrypt_file

encrypt_file("report.txt", "secret", "report.txt.enc")
decrypt_file("report.txt.enc", "secret", "report.txt")
```
