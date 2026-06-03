# General Utilities

Cereja includes small utility helpers for arrays, dictionaries, strings, time formatting, imports, and inspection.

## Arrays

```python
import cereja as cj

data = [[1, 2, 3], [3, 3, 3]]

print(cj.array.get_shape(data))
print(cj.array.flatten(data))
print(cj.array.dotproduct([1, 2], [1, 2]))
```

## Collections

```python
import cereja as cj

items = list(range(10))
print(cj.utils.chunk(items, batch_size=3))

mapping = {"key1": "value1", "key2": "value2"}
print(cj.utils.invert_dict(mapping))
```

## Strings and Imports

```python
import cereja as cj

print(cj.utils.truncate("Cereja is useful.", k=6))
print(cj.utils.string_to_literal("[1, 2, 3]"))
print(cj.utils.import_string("cereja.file._io.FileIO"))
```

## Time Formatting

```python
import cereja.utils.time

print(cereja.utils.time.time_format(3600))
```
