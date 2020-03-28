import time
from abc import ABCMeta, abstractmethod
from typing import Sequence, Any, Union

from cereja.arraytools import is_sequence
from cereja.cj_types import Number
from cereja.concurrently import TaskList
from cereja.display import ConsoleBase
from cereja.utils import percent, estimate, proportional


class State(metaclass=ABCMeta):

    @abstractmethod
    def display(self, current_value: Number, max_value: Number, current_percent: Number, time_it: Number) -> str:
        pass

    @abstractmethod
    def done(self, current_value: Number, max_value: Number, current_percent: Number, time_it: Number) -> str:
        pass


class StateBar(State):
    left_right_delimiter = "[]"
    arrow = ">"
    default_char = "="
    size = 30

    @classmethod
    def display(cls, current_value: Number, max_value: Number, current_percent: Number, time_it: Number) -> str:
        l_delimiter, r_delimiter = cls.left_right_delimiter
        prop_max_size = int(proportional(current_percent, cls.size))
        blanks = '  ' * (cls.size - prop_max_size)
        return f"{l_delimiter}{'=' * prop_max_size}{cls.arrow}{blanks}{r_delimiter}"

    @classmethod
    def done(cls, current_value: Number, max_value: Number, current_percent: Number, time_it: Number) -> str:
        l_delimiter, r_delimiter = cls.left_right_delimiter
        return f"{l_delimiter}{cls.default_char * cls.size}{r_delimiter}"


class StatePercent(State):
    @classmethod
    def display(cls, current_value: Number, max_value: Number, current_percent: Number, time_it: Number) -> str:
        return f"{current_percent}%"

    @classmethod
    def done(cls, current_value: Number, max_value: Number, current_percent: Number, time_it: Number) -> str:
        return f"{100}%"


class StateTime(State):
    @classmethod
    def display(cls, current_value: Number, max_value: Number, current_percent: Number, time_it: Number) -> str:
        time_estimate = estimate(current_value, max_value, time_it)
        return f"Estimated: {round(time_estimate, 2)}s"

    @classmethod
    def done(cls, current_value: Number, max_value: Number, current_percent: Number, time_it: Number) -> str:
        return f"Total: {round(time_it, 2)}s"


class Progress:
    default_states = (StateBar, StatePercent, StateTime,)

    def __init__(self, sequence: Sequence[Any], states=None):
        if not is_sequence(sequence):
            raise TypeError(f"sequence is not valid.")
        self.started = False
        self.console = ConsoleBase("Progress Tools")
        self.started_time = None
        self._states = self.default_states
        self.add_state(states)
        self.sequence = sequence
        self.max_value = len(sequence)

    def __repr__(self):
        progress_example_view = f"{self._states_view(self.max_value)}"
        state_conf = f"{self.__class__.__name__}{self._parse_states()}"
        return f"{state_conf}\n{self.console.parse(progress_example_view, title='Example States View')}"

    @property
    def states(self):
        return self._parse_states()

    def _parse_states(self):
        return tuple(map(lambda stt: stt.__name__, self._states))

    def add_state(self, state: Union[State, Sequence[State]]):
        if state is not None:
            self._filter_and_add_state(state)

    def _filter_and_add_state(self, state: Union[State, Sequence[State]]):
        filtered = tuple(
            filter(
                lambda stt: issubclass(type(stt), type(State)) and stt not in self._states,
                tuple(state)
            ))
        if any(filtered):
            self._states += filtered
            self.console.log(f"Added new states! {filtered}")

    def percent_(self, for_value: Number) -> Number:
        return percent(for_value, self.max_value)

    def _states_view(self, for_value: Number):
        kwargs = {
            "current_value": for_value,
            "max_value": self.max_value,
            "current_percent": self.percent_(for_value),
            "time_it": time.time() - (self.started_time or 0)
        }
        if self.max_value - 1 == for_value:
            def get_state(state: State):
                return state.done(**kwargs)
        else:
            def get_state(state: State):
                return state.display(**kwargs)

        result = TaskList(get_state, self._states).run()
        return ' - '.join(result)

    def show_progress(self, for_value):
        mounted_display = self._states_view(for_value)
        self.console.replace_last_msg(mounted_display)

    def __next__(self):
        self.started_time = time.time()
        self.started = True
        self.console.persist_on_runtime()
        for n, value in enumerate(self.sequence):
            self.show_progress(for_value=n)
            yield value
        self.started = False
        self.console.disable()

    def __iter__(self):
        return next(self)


if __name__ == "__main__":
    prog = Progress(["joab"] * 100)
    print(prog)
    for i, k in enumerate(prog, start=1):
        time.sleep(1 / i)
        print(k)

    prog.console.disable()
