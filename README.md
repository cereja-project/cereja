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

*Cereja was written only with the Standard Python Library, and it was a great way to improve knowledge in the Language
also to avoid the rewriting of code.*

## Getting Started DEV

Don't be shy \0/ ... Clone the repository and submit a function or module you made or use some function you liked.

See [CONTRIBUTING](CONTRIBUTING.md) 💻

## Setup

* [Python 3.6+](https://www.python.org/downloads/ "Download python")
* [Pip3](https://pip.pypa.io "Download Pip")

## Install

```
pip install --user cereja
```

or for all users

```
pip install cereja
```

## Cereja Example usage

See some of the Cereja tools

To access the *Cereja's* tools you need to import it `import cereja as cj`.

### 📝 [FileIO](docs/file.md)

#### Create new files

```python
import cereja as cj

file_json = cj.FileIO.create('./json_new_file.json', data={'k': 'v', 'k2': 'v2'})

file_txt = cj.FileIO.create('./txt_new_file.txt', ['line1', 'line2', 'line3'])

file_json.save()
file_txt.save()

print(file_json.exists)
# True
print(file_txt.exists)
# True


# see what you can do .txt file
print(cj.can_do(file_txt))

# see what you can do .json file
print(cj.can_do(file_json))
```

#### Load and edit files

```python
import cereja as cj

file_json = cj.FileIO.load('./json_new_file.json')

print(file_json.data)
# {'k': 'v', 'k2': 'v2'}

file_json.add(key='new_key', value='value')
print(file_json.data)
# {'k': 'v', 'k2': 'v2', 'new_key': 'value'}

file_txt = cj.FileIO.load('./txt_new_file.txt')

print(file_txt.data)
# ['line1', 'line2', 'line3']

file_txt.add('line4')
print(file_txt.data)
# ['line1', 'line2', 'line3', 'line4']

file_txt.save(exist_ok=True)  # Override
file_json.save(exist_ok=True)  # Override
```

### 📍 Path

```python
import cereja as cj

file_path = cj.Path('/my/path/file.ext')
print(cj.can_do(file_path))
# ['change_current_dir', 'cp', 'created_at', 'exists', 'get_current_dir', 'is_dir', 'is_file', 'is_hidden', 'is_link', 'join', 'last_access', 'list_dir', 'list_files', 'mv', 'name', 'parent', 'parent_name', 'parts', 'path', 'rm', 'root', 'rsplit', 'sep', 'split', 'stem', 'suffix', 'updated_at', 'uri']
```

### 🆗 HTTP Requests

```python
import cereja as cj

# Change url, headers and data values.
url = 'localhost:8000/example'
headers = {'Authorization': 'TOKEN'} # optional
data = {'q': 'test'} # optional

response = cj.request.post(url, data=data, headers=headers)

if response.code == 200:
    data = response.data
    # have a fun!
```

### ⏳ [Progress](docs/display.md)

```python
import cereja as cj
import time

my_iterable = ['Cereja', 'is', 'very', 'easy']

for i in cj.Progress.prog(my_iterable):
    print(f"current: {i}")
    time.sleep(2)

# Output on terminal ...

# 🍒 Sys[out] » current: Cereja 
# 🍒 Sys[out] » current: is 
# 🍒 Cereja Progress » [▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▱▱▱▱▱▱▱▱▱▱▱▱▱▱] - 50.00% - 🕢 00:00:02 estimated


```

### 🧠 [Data Preparation](docs/ml.md)

📊 **Freq**

```python
import cereja as cj

freq = cj.Freq([1, 2, 3, 3, 10, 10, 4, 4, 4, 4])
# Output -> Freq({1: 1, 2: 1, 3: 2, 10: 2, 4: 4})

freq.most_common(2)
# Output -> {4: 4, 3: 2}

freq.least_freq(2)
# Output -> {2: 1, 1: 1}

freq.probability
# Output -> OrderedDict([(4, 0.4), (3, 0.2), (10, 0.2), (1, 0.1), (2, 0.1)])

freq.sample(min_freq=1, max_freq=2)
# Output -> {3: 2, 10: 2, 1: 1, 2: 1}

# Save json file.
freq.to_json('./freq.json')
```

🧹 **Text Preprocess**

```python
import cereja as cj

text = "Oi tudo bem?? meu nome é joab!"

text = cj.preprocess.remove_extra_chars(text)
print(text)
# Output -> 'Oi tudo bem? meu nome é joab!'

text = cj.preprocess.separate(text, sep=['?', '!'])
# Output -> 'Oi tudo bem ? meu nome é joab !'

text = cj.preprocess.accent_remove(text)
# Output -> 'Oi tudo bem ? meu nome e joab !'

# and more ..

# You can use class Preprocessor ...
preprocessor = cj.Preprocessor(stop_words=(),
                               punctuation='!?,.', to_lower=True, is_remove_punctuation=False,
                               is_remove_stop_words=False,
                               is_remove_accent=True)

print(preprocessor.preprocess(text))
# Output -> 'oi tudo bem ? meu nome e joab !'

print(preprocessor.preprocess(text, is_destructive=True))
# Output -> 'oi tudo bem meu nome e joab'

```

🔣 **Tokenizer**

```python
import cereja as cj

text = ['oi tudo bem meu nome é joab']

tokenizer = cj.Tokenizer(text, use_unk=True)

# tokens 0 to 9 is UNK
# hash_ used to replace UNK
token_sequence, hash_ = tokenizer.encode('meu nome é Neymar Júnior')
# Output -> [([10, 12, 11, 0, 1], 'eeb755960ce70c')]

decoded_sequence = tokenizer.decode(token_sequence, hash_=hash_)
# Output -> 'meu nome é Neymar Júnior'

```

⏸ **Corpus**

Great training and test separator.

```python
import cereja as cj

X = ['how are you?', 'my name is Joab', 'I like coffee', 'how are you joab?', 'how', 'we are the world']
Y = ['como você está?', 'meu nome é Joab', 'Eu gosto de café', 'Como você está joab?', 'como', 'Nós somos o mundo']

corpus = cj.Corpus(source_data=X, target_data=Y, source_name='en', target_name='pt')
print(corpus)  # Corpus(examples: 6 - source_vocab_size: 13 - target_vocab_size:15)
print(corpus.source)  # LanguageData(examples: 6 - vocab_size: 13)
print(corpus.target)  # LanguageData(examples: 6 - vocab_size: 15)

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
train, test = corpus.split_data()  # default percent of training is 80%
```

### 🔢 Array

```python
import cereja as cj

cj.array.is_empty(data)  # False
cj.array.get_shape(data)  # (2, 3)

data = cj.array.flatten(data)  # [1, 2, 3, 3, 3, 3]
cj.array.prod(data)  # 162
cj.array.sub(data)  # -13
cj.array.div(data)  # 0.006172839506172839

cj.array.rand_n(0.0, 2.0, n=3)  # [0.3001196087729699, 0.639679494102923, 1.060200897124107]
cj.array.rand_n(1, 10)  # 5.086403830031244
cj.array.array_randn((3, 3,
                      3))  # [[[0.015077210355770374, 0.014298110484612511, 0.030410666810216064], [0.029319083335697604, 0.0072365209507707666, 0.010677361074992], [0.010576754075922935, 0.04146379877648334, 0.02188348813336284]], [[0.0451851551098092, 0.037074906805326824, 0.0032484586475421007], [0.025633380630695347, 0.010312669541918484, 0.0373624007621097], [0.047923908102496145, 0.0027939333359724224, 0.05976224377251878]], [[0.046869510719106486, 0.008325638358172866, 0.0038702998343255893], [0.06475268683502387, 0.0035638592537234623, 0.06551037943638163], [0.043317416824708604, 0.06579372884523939, 0.2477564291871006]]]
cj.chunk(data=[1, 2, 3, 4], batch_size=3, fill_with=0)  # [[1, 2, 3], [4, 0, 0]]
cj.array.remove_duplicate_items(['hi', 'hi', 'ih'])  # ['hi', 'ih'] 
cj.array.get_cols([['line1_col1', 'line1_col2'],
                   ['line2_col1', 'line2_col2']])  # [['line1_col1', 'line2_col1'], ['line1_col2', 'line2_col2']]
cj.array.dotproduct([1, 2], [1, 2])  # 5

a = cj.array.array_gen((3, 3), 1)  # [[1, 1, 1], [1, 1, 1], [1, 1, 1]]
b = cj.array.array_gen((3, 3), 1)  # [[1, 1, 1], [1, 1, 1], [1, 1, 1]]
cj.array.dot(a, b)  # [[3, 3, 3], [3, 3, 3], [3, 3, 3]]
cj.mathtools.theta_angle((2, 2), (0, -2))  # 135.0

```

### 🧰 Utils

```python
import cereja.utils.time
import cereja as cj

data = {"key1": 'value1', "key2": 'value2', "key3": 'value3', "key4": 'value4'}

cj.utils.chunk(list(range(10)), batch_size=3)
# [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]
cj.utils.chunk(list(range(10)), batch_size=3, fill_with=0, is_random=True)
# [[9, 7, 8], [0, 3, 2], [4, 1, 5], [6, 0, 0]]

# Invert Dict
cj.utils.invert_dict(data)
# Output -> {'value1': 'key1', 'value2': 'key2', 'value3': 'key3', 'value4': 'key4'}

# Get sample of large data
cj.utils.sample(data, k=2, is_random=True)
# Output -> {'key1': 'value1', 'key4': 'value4'}

cj.utils.fill([1, 2, 3, 4], max_size=20, with_=0)
# Output -> [1, 2, 3, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

cj.utils.rescale_values([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], granularity=4)
# Output -> [1, 3, 5, 7]

cj.utils.import_string('cereja.file._io.FileIO')
# Output -> <class 'cereja.file._io.FileIO'>

cj.utils.list_methods(cj.Path)
# Output -> ['change_current_dir', 'cp', 'get_current_dir', 'join', 'list_dir', 'list_files', 'mv', 'rm', 'rsplit', 'split']


cj.utils.string_to_literal('[1,2,3,4]')
# Output -> [1, 2, 3, 4]

cereja.utils.time.time_format(3600)
# Output -> '01:00:00'

cj.utils.truncate("Cereja is fun.", k=3)
# Output -> 'Cer...'

data = [[1, 2, 3], [3, 3, 3]]
cj.utils.is_iterable(data)  # True
cj.utils.is_sequence(data)  # True
cj.utils.is_numeric_sequence(data)  # True
```

[See Usage - Jupyter Notebook](./docs/cereja_example.ipynb)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details
