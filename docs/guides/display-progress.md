# Display and Progress

Use `Progress` to show terminal progress while iterating over a sequence.

```python
import time
import cereja as cj

items = ["Cereja", "is", "easy"]

for item in cj.Progress.prog(items):
    print(f"current: {item}")
    time.sleep(0.2)
```

The progress display uses Cereja's console handling so regular system messages stay above the active progress line.

## Custom Progress

```python
import time
import cereja as cj

progress = cj.Progress("Import")

for item in progress(range(100)):
    time.sleep(0.01)
```

## Custom State

```python
import cereja as cj


class CounterState(cj.display.State):
    def display(self, current_value, max_value, *args, **kwargs):
        return f"{current_value}/{max_value}"

    def done(self, *args, **kwargs):
        return "done"


progress = cj.Progress("Files")
progress[0] = CounterState
```

Custom states are useful when percentages are less useful than domain-specific information, such as number of files
processed.
