# Command Line Interface

Cereja exposes a `cereja` command when installed from PyPI or from the local project.

```bash
cereja --help
```

## Compress

Compress a file or directory:

```bash
cereja compress path/to/input
```

Choose the output path:

```bash
cereja compress path/to/input -o output.cjz
```

If the output name has no suffix, the CLI appends `.cjz`.

Progress output is enabled by default. Use `--quiet` when scripts need stable stdout:

```bash
cereja compress path/to/input --quiet
```

Available compression strategies are `auto`, `dict`, `rle`, `delta`, `bitpack`, `zlib`, `bz2`, `lzma`, and `hybrid`.

```bash
cereja compress path/to/input --strategy zlib
```

Use `--force` to overwrite an existing output file:

```bash
cereja compress path/to/input -o output.cjz --force
```

## Encrypted Archives

Create an encrypted compressed archive:

```bash
cereja compress path/to/input --encrypt
```

The CLI asks for a password and confirmation without echoing the value.

## Decompress

Decompress an archive:

```bash
cereja decompress archive.cjz
```

The CLI detects encrypted archives and prompts for the password when needed.

Use `--archive-type` to force file or directory decompression:

```bash
cereja decompress archive.cjz --archive-type dir
```

## Encrypt and Decrypt Files

Encrypt a file directly:

```bash
cereja encrypt report.txt -o report.txt.enc
```

Decrypt it:

```bash
cereja decrypt report.txt.enc -o report.txt
```
