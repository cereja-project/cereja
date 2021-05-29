# 📝 Cereja File Package

Makes file manipulation in Python even easier.

You have everything related to the file with just one line of code.

Have a fun!

## Create and save a file

```python
from cereja.file import FileIO

file = FileIO.create('./test.txt', ['first line', 'second', '...'])  # you can see warning message if file exists!

# add new lines
# if I want to add two lines to the end of the file
# default arg `line` is -1.
# if arg `line` is -1 will add in the end of file
file.add(['added line x', 'added line y'])
print(file.data)
# output -> ['first line', 'second', '...', 'added line x', 'added line y']


file[0] = 'changed first line'
print(file.data)
# output -> ['changed first line', 'second', '...', 'added line x', 'added line y']

# Save
file.save()  # that's just it
```

## Load files

### Single File

```python
from cereja import FileIO
import cereja as cj

file = FileIO.load('path_to_file.ext')  # if the file not exists raises FileNotFoundError

# see what you can do
print(cj.can_do(file))
# you will see something like this
# ['add', 'created_at', 'data', 'delete', 'dir_name', 'dir_path', 'exists', 'ext', 'history', 'is_empty', 'last_access', 'length', 'name', 'name_without_ext', 'only_read', 'parse', 'parse_ext', 'path', 'redo', 'sample_items', 'save', 'set_path', 'size', 'undo', 'updated_at', 'was_changed']
```

### Load Files from dir

```python
from cereja import FileIO

# List of files
files = FileIO.load_files('path/to/dir', recursive=True)

for file in files:
    # file is a cereja's object
    # ... your code
    pass
```

## You need to know ...

Today Cereja can handle the following file formats, because they have special methods

* .txt
* .json
* .csv
* .zip
* .vtt/.srt