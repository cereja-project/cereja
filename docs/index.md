# Cereja

Cereja is a Python utility package for developers who want reusable helpers for files, paths, progress display,
compression, hashing, text processing, data preparation, arrays, dates, and small system tasks.

The package is distributed on PyPI as `cereja` and supports Python 3.11 and newer.

```bash
python -m pip install cereja
```

```python
import cereja as cj

path = cj.Path(".")
print(path.list_files())
```

```{toctree}
:maxdepth: 2
:caption: User Guide

getting-started
cli
guides/files-and-paths
guides/display-progress
guides/compression-and-encryption
guides/text-and-data
guides/utilities
```

```{toctree}
:maxdepth: 2
:caption: Reference

api/index
```

## Project Links

- Source code: <https://github.com/cereja-project/cereja>
- Issues: <https://github.com/cereja-project/cereja/issues/new/choose>
- PyPI: <https://pypi.org/project/cereja/>
- License: MIT
