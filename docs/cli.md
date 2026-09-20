# Command Line Interface

Cereja exposes a `cereja` command when installed from PyPI or from the local project.

```bash
cereja --help
```

The root help is the complete command index. Each command owns its own parser and help:

```text
compress     Compress a file or directory.
decompress   Decompress a file or directory archive.
encrypt      Encrypt a file.
decrypt      Decrypt a file.
tree         Draw a repository tree.
context      Search or list bounded textual context.
security     Inspect untrusted files without executing them.
http         Send HTTP requests.
download     Download files with streaming transfers.
system       Inspect local system information.
privacy      Run tools with process-scoped privacy policies.
module       Manage Cereja module scaffolding.
```

Use command-specific help for the complete set of flags:

```bash
cereja compress --help
cereja context --help
cereja http --help
cereja system --help
cereja privacy --help
```

The CLI loads only the selected command implementation. Asking for root help or the Cereja version does not initialize unrelated command subsystems.

## Repository Tree

Draw a filtered Unicode tree for the current directory or an explicit path:

```bash
cereja tree
cereja tree path/to/repository --depth 2
```

The command includes non-ignored hidden files, shows directories before files,
and respects common `.gitignore` rules, including nested files and negated
patterns. `.git`, Python/tool caches, and compiled Python files are always
hidden. Symbolic links are shown but are not traversed.

## Compress

Compress a file or directory:

```bash
cereja compress path/to/input
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

### Encrypted archives

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

## Context

Search bounded text context:

```bash
cereja context search --root . --query "needle"
```

List text-file metadata without printing file contents:

```bash
cereja context list --root .
```

Inspect or clear the optional per-user cache:

```bash
cereja context cache info
cereja context cache clear
```

## Security

Run defensive static analysis without executing the target file:

```bash
cereja security analyze suspicious.bin
cereja security analyze suspicious.bin --format json
```

## HTTP and Downloads

Send a one-shot HTTP request:

```bash
cereja http https://example.com
```

Use the dedicated streaming transfer command for downloads:

```bash
cereja download https://example.com/archive.zip
```

See [HTTP and Transfers](guides/http.md) for the full HTTP and download interfaces.

## System Information

Inspect the local operating system and hardware:

```bash
cereja system info
cereja system info --full
cereja system info --json
```

Sensitive machine identifiers remain opt-in:

```bash
cereja system info --full --sensitive
```

See [System Information](guides/system-info.md) for platform behavior and privacy details.

## Process Privacy

Run a child command with Hugging Face Hub access and telemetry disabled:

```bash
cereja privacy huggingface run -- python app.py
```

Open an offline child shell:

```bash
cereja privacy huggingface shell
```

Inspect the current environment without printing token values:

```bash
cereja privacy huggingface status
cereja privacy huggingface status --json
```

Temporarily permit one model download while keeping telemetry disabled:

```bash
cereja privacy huggingface download -- hf download org/model
cereja privacy huggingface download --no-token -- hf download org/public-model
```

The privacy command changes only the child-process environment. It does not edit shell
profiles, persist credentials, or enforce an operating-system network sandbox.

See [Process Privacy](guides/privacy.md) for the full policy and security boundary.

## Module Scaffolding

Create a Cereja module file relative to the package source:

```bash
cereja module create path/to/module.py
```

The historical form remains available as a compatibility alias:

```bash
cereja --startmodule path/to/module.py
```

New scripts should prefer `cereja module create`.
