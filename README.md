# Cereja

[![Python package](https://github.com/cereja-project/cereja/actions/workflows/pythonpackage.yml/badge.svg)](https://github.com/cereja-project/cereja/actions/workflows/pythonpackage.yml)
[![PyPI version](https://badge.fury.io/py/cereja.svg)](https://badge.fury.io/py/cereja)
[![Downloads](https://pepy.tech/badge/cereja)](https://pepy.tech/project/cereja)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Cereja is a Python utility package for developers who want reusable helpers for files, paths, progress display,
compression, hashing, text processing, data preparation, arrays, dates, and small system tasks.

The package is published on PyPI and supports Python 3.11 and newer.

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
cereja compress path/to/input
cereja decompress archive.cjz
```

Progress is enabled by default for CLI compression and decompression. Use `--quiet` for script-friendly output.

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
