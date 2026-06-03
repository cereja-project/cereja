# Files and Paths

Cereja includes convenience wrappers for file and path operations. Use them when you want a compact interface around
common filesystem tasks without adding third-party dependencies.

## Create and Save Files

```python
from cereja.file import FileIO

file = FileIO.create("./example.txt", ["first line", "second line"])
file.add("third line")
file.save()
```

`FileIO` keeps file data in memory until `save()` is called.

## Load Files

```python
from cereja.file import FileIO

file = FileIO.load("./example.txt")
print(file.data)

file.add("new line")
file.save(exist_ok=True)
```

`FileIO.load()` raises `FileNotFoundError` when the file does not exist.

## Load Files From a Directory

```python
from cereja.file import FileIO

files = FileIO.load_files("path/to/dir", recursive=True)

for file in files:
    print(file.path)
```

## Path Helpers

```python
import cereja as cj

path = cj.Path(".")
print(path.exists)
print(path.list_files())
```

`Path` exposes common file and directory operations such as joining paths, listing files, moving files, removing files,
and reading metadata.

## Supported File Formats

`FileIO` has specialized parsing support for common formats including:

- `.txt`
- `.json`
- `.csv`
- `.zip`
- `.vtt`
- `.srt`
