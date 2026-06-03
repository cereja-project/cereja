# Getting Started

## Requirements

- Python 3.11 or newer
- `pip`

## Installation

Install the released package from PyPI:

```bash
python -m pip install cereja
```

For local development:

```bash
git clone https://github.com/cereja-project/cereja.git
cd cereja
python -m pip install -e .
python -m unittest discover -s tests -v
```

## First Import

Most commonly used helpers are available from the top-level package:

```python
import cereja as cj

print(cj.__version__)
print(cj.can_do(cj.Path(".")))
```

You can also import from focused modules when that makes code clearer:

```python
from cereja.file import FileIO
from cereja.display import Progress
from cereja.hashtools import compress_file
```

## Common Tasks

- Use `FileIO` and `Path` for local file and path operations.
- Use `Progress` when iterating over long-running work in a terminal.
- Use `cereja.hashtools` for hashing, compression, decompression, encryption, and decryption.
- Use `cereja.mltools` for lightweight text preprocessing and data helpers.
