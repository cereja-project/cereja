# Display Package

## ⏳ Progress

See the progress of an iteration in a simple way

### Simple usage
```python
import cereja as cj
import time

my_iterable = ['Cereja', 'is', 'very', 'easy']


for i in cj.Progress.prog(my_iterable):
    print(f"current: {i}")
    time.sleep(2)

```

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
    time.sleep(1 / i)
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
        time.sleep(1 / i)
```

<div>
 <img src="https://media.giphy.com/media/W3gDDqVhgip0V9N7HA/giphy.gif">
</div>