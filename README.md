# Cereja 🍒

![Python package](https://github.com/jlsneto/cereja/workflows/Python%20package/badge.svg)
[![PyPI version](https://badge.fury.io/py/cereja.svg)](https://badge.fury.io/py/cereja)
[![Downloads](https://pepy.tech/badge/cereja)](https://pepy.tech/project/cereja)
[![MIT LICENSE](https://img.shields.io/pypi/l/pyzipcode-cli.svg)](LICENSE)
[![Issues](https://camo.githubusercontent.com/926d8ca67df15de5bd1abac234c0603d94f66c00/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f636f6e747269627574696f6e732d77656c636f6d652d627269676874677265656e2e7376673f7374796c653d666c6174)](https://github.com/jlsneto/cereja/issues/new/choose)
[![Get start on Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jlsneto/cereja/blob/master/docs/cereja_example.ipynb)

<div align="center">
 <img src="https://i.ibb.co/Fw8SSfd/cereja-logo.png" height="300" width="300" alt="CEREJA">
</div>

*Cereja is a bundle of useful functions that I don't want to rewrite.*

How many times have you needed to rewrite that function or base class? Well, I thought then of joining all my lines of code, bit by bit, in one place.

Not well structured yet :( ... But you can help me !!!

## Getting Started DEV

Don't be shy \0/ ... Clone the repository and submit a function or module you made or use some function you liked.

See [CONTRIBUTING](CONTRIBUTING.md) 💻

### Setup

* [Python 3.6+](https://www.python.org/downloads/ "Download python")
* [Pip3](https://pip.pypa.io "Download Pip")

### Installing

**Install Cereja Package**
```
python3 -m pip install --user cereja
```
or for all users
```
python3 -m pip install cereja
```
> Note: If you're using Windows, you don't need use python3, but make sure your python path settings are correct. 

### Cereja Example usage

See some of the Cereja tools

#### Filetools

Filetools has several functions, have the converters for end of line (CRLF, LF and CR), you can convert CRLF to LF or CR, or contrariwise.

##### Txt File Manipulation Example - most files
```python
import cereja as cj

data = ['first line', 'second line', 'third line']
file = cj.File('test.txt', data) # ram only, not yet saved
print(file) # FileBase<test.txt>
print(file.data) # ['first line', 'second line', 'third line']

# iterable
for line in file:
    pass

# indexable
file[0] # 'first line'
file[:3] # ['first line', 'second line', 'third line']

# Insert Data
file.insert('other line')
file.insert('other line2')
print(file.data) # ['other line2', 'other line', 'first line', 'second line', 'third line']
# it is allowed to use index assignment
file[0] = 'other line'
# can use file.append
file.append('end line')

# Data Recovery
file.undo() # You selected amendment 3
print(file.data) # ['other line2', 'other line', 'first line', 'second line', 'third line']
file.redo() # You selected amendment 4
print(file.data) # ['other line', 'other line2', 'other line', 'first line', 'second line', 'third line']

# Save Data
file.save()
```
##### File Manipulation Example - .json 
```python
import cereja as cj

data = {'key': 'value', 'key2': 'value2', 'key3': 'value3'}
file = cj.File('test.json', data) # ram only, not yet saved
print(file) # JsonFile<test.json>
print(file.data) # {'key': 'value', 'key2': 'value2', 'key3': 'value3'}

# Iterable
for key, value in file.items(): # only .json data, use .items(), .values() and .keys()
    pass

file['key'] # 'value'

# Insert Data
file['key4'] = 'value4'
print(file.data) # {'key': 'value', 'key2': 'value2', 'key3': 'value3', 'key4': 'value4'}

# Data Recovery
file.undo() # You selected amendment 1
print(file.data) # {'key': 'value', 'key2': 'value2', 'key3': 'value3'}
file.redo() # You selected amendment 2
print(file.data) # {'key': 'value', 'key2': 'value2', 'key3': 'value3', 'key4': 'value4'}

# Save Data
file.save()
```

##### File Manipulation Example - .csv File 
```python
import cereja as cj

file = cj.File('test.csv', fieldnames=['col1','col2','col3']) # ram only, not yet saved
print(file) # CsvFile<test.csv>
file.add_row([1,2,3])
print(file.lines) # [[1, 2, 3]]
file.add_row([1,2], fill_with=0)
print(file.lines) # [[1, 2, 3], [1, 2, 0]]

# convert to dict
file.to_dict() # {'col1': [1, 1], 'col2': [2, 2], 'col3': [3, 0]}

# or get generation row by row with col
print(list(file.data)) # [{'col1': 1, 'col2': 2, 'col3': 3}, {'col1': 1, 'col2': 2, 'col3': 0}]

# Iterable
for row in file:
    pass

# indexing col values
print(file['col1']) # [1, 1]
# or use index and get a row
print(file[0]) # [1, 2, 3]

# Save Data
file.save()

# Reading
file = cj.CsvFile.load('test.csv') # have a fun! lol
dir(file) # see all methods and attr
```
##### Reading Other Files
```python
import cereja as cj

file = cj.File.load('path_to_file.ext')
# now you have a file instance, have fun!
# you can insert lines, remove and save \0/
file.save(exist_ok=True) # or change path file.save(on_new_path='new_path.ext', exist_ok=True)
```

##### Convert between CRLF, LF and CR

```shell script
python3 -m pip install cereja

python3 -m cereja --crlf_to_lf "/dir_or_file_path"
```

#### Corpus
Great training and test separator.

##### Create from list data
```python
import cereja as cj

X = ['how are you?', 'my name is Joab', 'I like coffee', 'how are you joab?', 'how', 'we are the world']
Y = ['como você está?', 'meu nome é Joab', 'Eu gosto de café', 'Como você está joab?', 'como', 'Nós somos o mundo']

corpus = cj.Corpus(source_data=X, target_data=Y, source_name='en', target_name='pt')
print(corpus) # Corpus(examples: 6 - source_vocab_size: 13 - target_vocab_size:15)
print(corpus.source) # LanguageData(examples: 6 - vocab_size: 13)
print(corpus.target) # LanguageData(examples: 6 - vocab_size: 15)

corpus.source.phrases_freq
# Counter({'how are you': 1, 'my name is joab': 1, 'i like coffee': 1, 'how are you joab': 1, 'how': 1, 'we are the world': 1})

corpus.source.word_freq
# Counter({'how': 3, 'are': 3, 'you': 2, 'joab': 2, 'my': 1, 'name': 1, 'is': 1, 'i': 1, 'like': 1, 'coffee': 1, 'we': 1, 'the': 1, 'world': 1})

corpus.target.phrases_freq
# Counter({'como você está': 1, 'meu nome é joab': 1, 'eu gosto de café': 1, 'como você está joab': 1, 'como': 1, 'nós somos o mundo': 1})

corpus.target.words_freq
# Counter({'como': 3, 'você': 2, 'está': 2, 'joab': 2, 'meu': 1, 'nome': 1, 'é': 1, 'eu': 1, 'gosto': 1, 'de': 1, 'café': 1, 'nós': 1, 'somos': 1, 'o': 1, 'mundo': 1})

# split_data function guarantees test data without data identical to training
# and only with vocabulary that exists in training
train, test = corpus.split_data() # default percent of training is 80%
```
##### Read from .csv
```python
import cereja as cj

corpus = cj.Corpus.load_corpus_from_csv('path_to_file.csv', src_col_name='x_data', trg_col_name='y_data', source_name='en', target_name='pt')
# now you have a Corpus instance, have fun! (:
```
#### Progress

```python
import cereja as cj
import time

def process_data(i: int):
    # simulates some processing 
    time.sleep(cj.rand_n()/max(abs(i), 1))

my_iterable = range(1, 500)
my_progress = cj.Progress("My Progress")

for i in my_progress(my_iterable):
    process_data(i)

```
<div>
 <img src="https://media.giphy.com/media/JNxHJ0uGPqTKRUeLWc/giphy.gif">
</div>

##### Custom Display
```python
import cereja as cj
import time

progress = cj.Progress("My Progress")
print(progress)

print(progress[0])
print(progress[1])
print(progress[2])

class MyCustomState(cj.StateBase):
    def display(self, current_value, max_value, *args, **kwargs):
        return f'{current_value} -> {max_value}'
    def done(self, *args, **kwargs):
        return f'FINISHED'

progress[0] = MyCustomState

for i in progress(range(1, 500)):
    time.sleep(1/i)
```
<div>
 <img src="https://media.giphy.com/media/JnA6EErThhwTdQ5izb/giphy.gif">
</div>

##### With Statement
```python
import cereja as cj
import time

with cj.Progress("My Progress") as prog:
    time.sleep(5)
    for i in prog(range(1, 500)):
        time.sleep(1/i)
```
<div>
 <img src="https://media.giphy.com/media/W3gDDqVhgip0V9N7HA/giphy.gif">
</div>

#### Utils
```python

import cereja as cj

# Arraytools
data = [[1,2,3],[3,3,3]]
cj.is_iterable(data) # True
cj.is_sequence(data) # True
cj.is_numeric_sequence(data) # True
cj.is_empty(data) # False
cj.get_shape(data) # (2, 3)

data = cj.flatten(data) # [1, 2, 3, 3, 3, 3]
cj.prod(data) # 162
cj.sub(data) # -13
cj.div(data) # 0.006172839506172839

cj.rand_n(0.0, 2.0, n=3) # [0.3001196087729699, 0.639679494102923, 1.060200897124107]
cj.rand_n(1,10) # 5.086403830031244
cj.array_randn((3, 3, 3)) # [[[0.015077210355770374, 0.014298110484612511, 0.030410666810216064], [0.029319083335697604, 0.0072365209507707666, 0.010677361074992], [0.010576754075922935, 0.04146379877648334, 0.02188348813336284]], [[0.0451851551098092, 0.037074906805326824, 0.0032484586475421007], [0.025633380630695347, 0.010312669541918484, 0.0373624007621097], [0.047923908102496145, 0.0027939333359724224, 0.05976224377251878]], [[0.046869510719106486, 0.008325638358172866, 0.0038702998343255893], [0.06475268683502387, 0.0035638592537234623, 0.06551037943638163], [0.043317416824708604, 0.06579372884523939, 0.2477564291871006]]]
cj.group_items_in_batches(items=[1,2,3,4], items_per_batch=3, fill=0) # [[1, 2, 3], [4, 0, 0]]
cj.remove_duplicate_items(['hi', 'hi', 'ih']) # ['hi', 'ih'] 
cj.get_cols([['line1_col1','line1_col2'],['line2_col1','line2_col2']]) # [['line1_col1', 'line2_col1'], ['line1_col2', 'line2_col2']]
cj.dotproduct([1,2], [1,2]) # 5


a = cj.array_gen((3,3), 1) # [[1, 1, 1], [1, 1, 1], [1, 1, 1]]
b = cj.array_gen((3,3), 1) # [[1, 1, 1], [1, 1, 1], [1, 1, 1]]
cj.dot(a, b) # [[3, 3, 3], [3, 3, 3], [3, 3, 3]]
cj.theta_angle((2,2), (0, -2)) # 135.0
```
[See Usage - Jupyter Notebook](./docs/cereja_example.ipynb)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details
