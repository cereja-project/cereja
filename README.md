# Cereja

[![Python package](https://github.com/cereja-project/cereja/actions/workflows/pythonpackage.yml/badge.svg)](https://github.com/cereja-project/cereja/actions/workflows/pythonpackage.yml)
[![PyPI version](https://badge.fury.io/py/cereja.svg)](https://badge.fury.io/py/cereja)
[![Downloads](https://pepy.tech/badge/cereja)](https://pepy.tech/project/cereja)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Cereja is a Python utility package for developers who want reusable helpers for files, paths, progress display,
compression, hashing, text processing, data preparation, arrays, dates, and small system tasks.

The package is published on PyPI and supports Python 3.11 and newer.

## Design principles

- Zero runtime dependencies
- Standard-library-first implementations
- Small, reusable and composable APIs
- Backward compatibility where practical
- Educational implementations without hiding Python internals


## Installation

```bash
python -m pip install cereja
```

## Quick Start

```python
import cereja as cj

path = cj.Path(".")
print(path.list_files())
```

```python
from cereja.file import FileIO

file = FileIO.create("./example.txt", ["first line", "second line"])
file.add("third line")
file.save()
```

## CLI

```bash
cereja --help
cereja tree .
cereja compress path/to/input
cereja decompress archive.cjz
```

Progress is enabled by default for CLI compression and decompression. Use `--quiet` for script-friendly output.

### Cereja TUI

```bash
cereja ui
cereja ui --plain
```

On a terminal supporting bracketed paste, Cereja TUI provides explicit forms for
System, Tree, Large files, Context, Archives and Download. Writes require exact-destination
review and refuse replacement. See the [Cereja TUI guide](docs/guides/ui-ledger.md)
for supported limits, Windows-only directory extraction, terminal requirements
and remaining human acceptance. Plain mode prints a reference and reads no input.

In `/large-files`, Tab completes directory paths, arrows select files, and Enter
opens file actions. Sizes use readable binary units; Details shows exact bytes.
Copy, move and permanent deletion require confirmation. Moves stay within the
same volume, and existing destinations are preserved.

Embed with `from cereja.tui import TUI`. The former
`from cereja.ledger.app import Ledger` remains an alias of the same class.

### Large files by metadata

Find the largest regular files under an explicit root without reading content:

```bash
cereja large-files path/to/data --min-size-bytes 1048576 --max-results 20 --format json
```

Hidden and binary files are included, with no repository filters or link
traversal. The Python API is `cereja.system.file_sizes.find_large_files`.
See [file sizes](docs/guides/file-sizes.md) for partial-scan reporting, limits
and reproducible benchmarks.

### Bounded context search

Search for all whitespace-separated terms in UTF-8 text under one or more
explicit roots:

```bash
cereja context search --root docs --query "context search" --extension md
cereja context search --root docs --root cereja --query "Path FileIO" --format json
```

Inventory text files without returning their content:

```bash
cereja context list --root docs --max-results 20
```

Use `--max-file-bytes`, `--max-results`, `--max-snippets`, and
`--max-snippet-chars` to bound search output. Searched source files are opened
read-only and are never modified. The commands decode only UTF-8 text, skip
binary files, and do not follow symbolic links.

The persistent cache is opt-in. When `--cache` is enabled, Cereja writes a
global per-user cache outside the searched roots. Use `--cache` to populate or
reuse it and `--refresh-cache` with `--cache` to force file content to be
reprocessed:

```bash
cereja context search --root docs --query "context search" --cache
cereja context search --root docs --query "context search" --cache --refresh-cache
```

Inspect cache metadata or clear the context-cache namespace with:

```bash
cereja context cache info --format json
cereja context cache clear
```

If the optional cache is unavailable, context search emits a
`ContextCacheWarning` and continues with a direct filesystem search.

## Development

```bash
git clone https://github.com/cereja-project/cereja.git
cd cereja
python -m pip install -e .
python -m unittest discover -s tests -v
```

Run the syntax/undefined-name lint used by CI:

```bash
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```

## Documentation

- Documentation: <https://cereja.readthedocs.io/>
- Source code: <https://github.com/cereja-project/cereja>
- Issues: <https://github.com/cereja-project/cereja/issues/new/choose>
- PyPI: <https://pypi.org/project/cereja/>
- Examples notebook: [docs/cereja_example.ipynb](docs/cereja_example.ipynb)

## Citation

If you use Cereja in academic work, please cite it. GitHub uses `CITATION.cff` for the "Cite this repository" button,
and a BibTeX entry is available in `CITATION.bib`.

## License

Cereja is distributed under the MIT License. See [LICENSE](LICENSE) for details.
