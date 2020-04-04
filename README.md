# Cereja 🍒

![Python package](https://github.com/jlsneto/cereja/workflows/Python%20package/badge.svg)
[![PyPI version](https://badge.fury.io/py/cereja.svg)](https://badge.fury.io/py/cereja)
[![Downloads](https://pepy.tech/badge/cereja)](https://pepy.tech/project/cereja)
[![MIT LICENSE](https://img.shields.io/pypi/l/pyzipcode-cli.svg)](LICENSE)
[![Issues](https://camo.githubusercontent.com/926d8ca67df15de5bd1abac234c0603d94f66c00/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f636f6e747269627574696f6e732d77656c636f6d652d627269676874677265656e2e7376673f7374796c653d666c6174)](https://github.com/jlsneto/cereja/issues/new/choose)
[![Get start on Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jlsneto/cereja/blob/master/docs/cereja_example.ipynb)

<div align="center">
 <img src="https://i.ibb.co/dp8rZ3F/cereja-logo.png">
</div>

*Cereja is a bundle of useful functions that I don't want to rewrite.*

How many times have you needed to rewrite that function or base class? Well, I thought then of joining all my lines of code, bit by bit, in one place.

Not well structured yet :( ... But you can help me !!!

## Getting Started DEV

Do not be shy \0/ ... Clone the repository and submit a function or module you made or use some function you liked.

See [CONTRIBUTING](CONTRIBUTING.md) 💻

### Prerequisites

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
> Note: If you are using Windows, you do not need to use python3, but make sure your python path settings are correct. 

### Cereja Example usage
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

##### With statement
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


[See Usage - Jupyter Notebook](./docs/cereja_example.ipynb)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details
