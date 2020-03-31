import io
import os
import threading
import time
from abc import ABCMeta, abstractmethod
from typing import Sequence, Any, Union, Type, AnyStr

from cereja.arraytools import is_sequence, is_iterable
from cereja.cj_types import Number
from cereja.concurrently import TaskList
from cereja.display import ConsoleBase as Console
from cereja.unicode import Unicode
from cereja.utils import percent, estimate, proportional, fill


class __Stdout:
    __stdout_buffer = io.StringIO()
    __stderr_buffer = io.StringIO()

    def _write(self):
        pass

    def write(self):
        pass


class ConsoleBase(metaclass=ABCMeta):

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def log(self, msg: str) -> str:
        pass


class State(metaclass=ABCMeta):

    def __repr__(self):
        return f"{self.name} {self.done(100, 100, 100, 0, 100)}"

    @property
    def name(self):
        return f"{self.__class__.__name__.replace('__State', '')} field"

    @abstractmethod
    def display(self, current_value: Number, max_value: Number, current_percent: Number, time_it: Number,
                n_times: int) -> str:
        pass

    @abstractmethod
    def done(self, current_value: Number, max_value: Number, current_percent: Number, time_it: Number,
             n_times: int) -> str:
        pass


class __StateLoading(State):
    sequence = (".", ".", ".")
    left_right_delimiter = "[]"
    default_char = "."
    size = 3
    n_times = 0

    @classmethod
    def display(cls, current_value: Number, max_value: Number, current_percent: Number, time_it: Number,
                n_times: int) -> str:
        idx = n_times % cls.size
        value = ''.join(cls.sequence[idx:])
        filled = fill(value, 3, with_=' ')
        l_delimiter, r_delimiter = cls.left_right_delimiter
        return f"{l_delimiter}{filled}{r_delimiter}"

    @classmethod
    def done(cls, current_value: Number, max_value: Number, current_percent: Number, time_it: Number,
             n_times: int) -> str:
        l_delimiter, r_delimiter = cls.left_right_delimiter
        return f"{l_delimiter}{cls.default_char * cls.size}{r_delimiter}"


class __StateAwaiting(__StateLoading):

    @classmethod
    def _clean(cls, result):
        return result.strip(cls.left_right_delimiter)

    @classmethod
    def display(cls, *args, **kwargs) -> str:
        result = cls._clean(super().display(*args, **kwargs))
        return f"Awaiting{result}"

    @classmethod
    def done(cls, *args, **kwargs) -> str:
        result = cls._clean(super().done(*args, **kwargs))
        return f"Awaiting{result} Done!"


class __StateBar(State):
    left_right_delimiter = "[]"
    arrow = ">"
    default_char = "="
    size = 30

    @classmethod
    def display(cls, current_value: Number, max_value: Number, current_percent: Number, time_it: Number,
                n_times: int) -> AnyStr:
        l_delimiter, r_delimiter = cls.left_right_delimiter
        prop_max_size = int(proportional(current_percent, cls.size))
        blanks = '  ' * (cls.size - prop_max_size)
        return f"{l_delimiter}{'=' * prop_max_size}{cls.arrow}{blanks}{r_delimiter}"

    @classmethod
    def done(cls, current_value: Number, max_value: Number, current_percent: Number, time_it: Number,
             n_times: int) -> str:
        l_delimiter, r_delimiter = cls.left_right_delimiter
        return f"{l_delimiter}{cls.default_char * cls.size}{r_delimiter}"


class __StatePercent(State):
    @classmethod
    def display(cls, current_value: Number, max_value: Number, current_percent: Number, time_it: Number,
                n_times: int) -> str:
        return f"{current_percent: .2f}%"

    @classmethod
    def done(cls, current_value: Number, max_value: Number, current_percent: Number, time_it: Number,
             n_times: int) -> str:
        return f"{100}%"


class __StateTime(State):
    __clock = Unicode("\U0001F55C")
    __max_sequence = 12

    @classmethod
    def time_format(cls, time_estimate: float):
        if time_estimate >= 0:
            return time.strftime('%H:%M:%S', time.gmtime(time_estimate))
        return time_estimate

    @classmethod
    def display(cls, current_value: Number, max_value: Number, current_percent: Number, time_it: Number,
                n_times: int) -> str:
        time_estimate = estimate(current_value, max_value, time_it)
        idx = int(proportional(int(current_percent), cls.__max_sequence))
        return f"{cls.__clock + idx} Estimated: {cls.time_format(time_estimate)}"

    @classmethod
    def done(cls, current_value: Number, max_value: Number, current_percent: Number, time_it: Number,
             n_times: float) -> str:
        return f"{cls.__clock} Total: {time.strftime('%H:%M:%S', time.gmtime(time_it))}"


StateBase = State
StateBar = __StateBar()
StatePercent = __StatePercent()
StateTime = __StateTime()
StateLoading = __StateLoading()
StateAwaiting = __StateAwaiting()


class ProgressBase:
    default_states = (StateBar, StatePercent, StateTime,)

    __awaiting_state = StateAwaiting

    def __init__(self, console: Console, states=None):
        self.n_times = 0
        self.started = False
        self._awaiting_update = True
        self.console = console
        self.started_time = None
        self._states = self.default_states
        self.add_state(states)
        self.max_value = 100
        self.th_awaiting = self._create_awaiting()

    def __repr__(self):
        progress_example_view = f"{self._states_view(self.max_value)}"
        state_conf = f"{self.__class__.__name__}{self._parse_states()}"
        return f"{state_conf}\n{self.console.parse(progress_example_view, title='Example States View')}"

    def _create_awaiting(self, time_: float = None):
        return threading.Thread(name="awaiting", target=self._show_awaiting, args=(time_,))

    def _show_awaiting(self, time_: float = None):
        n_times = 0
        time_it = time.time()
        while self._awaiting_update:
            self.console.replace_last_msg(self.__awaiting_state.display(0, 0, 0, 0, n_times=n_times))
            n_times += 1
            if time_ is not None:
                if (time.time() - time_it) > time_:
                    break
            time.sleep(1)
        self.console.replace_last_msg(self.__awaiting_state.done(0, 0, 0, 0, 0))

    def _parse_states(self):
        return tuple(map(lambda stt: stt.__class__.__name__, self._states))

    def _states_view(self, for_value: Number):
        self._awaiting_update = False
        self.n_times += 1
        kwargs = {
            "current_value": for_value,
            "max_value": self.max_value,
            "current_percent": self.percent_(for_value),
            "time_it": time.time() - (self.started_time or time.time()),
            "n_times": self.n_times
        }
        if for_value >= self.max_value - 1:
            def get_state(state: State):
                return state.done(**kwargs)
        else:
            def get_state(state: State):
                return state.display(**kwargs)

        result = TaskList(get_state, self._states).run()
        return ' - '.join(result)

    def add_state(self, state: Union[Type[State], Sequence[Type[State]]]):
        if state is not None:
            if not is_iterable(state):
                state = (state,)
            self._filter_and_add_state(state)

    def _filter_and_add_state(self, state: Union[Type[State], Sequence[Type[State]]]):
        filtered = tuple(
            filter(
                lambda stt: stt not in self._states,
                tuple(state)
            ))
        if any(filtered):
            self._states += filtered
            self.console.log(f"Added new states! {filtered}")

    @property
    def states(self):
        return self._parse_states()

    def percent_(self, for_value: Number) -> Number:
        return percent(for_value, self.max_value)

    def update_max_value(self, max_value: int):
        """
        You can modify the progress to another value. It is not a percentage,
        although it is purposely set to 100 by default.

        :param max_value: This number represents the maximum amount you want to achieve.
        """
        if not isinstance(max_value, (int, float, complex)):
            raise Exception(f"Current value {max_value} isn't valid.")
        self.max_value = max_value

    def show_progress(self, for_value, max_value=None):
        """
        Build progress by a value.

        :param for_value: Fraction of the "max_value" you want to achieve.
                              Remember that this value is not necessarily the percentage.
                              It is totally dependent on the "max_value"
        :param max_value: This number represents the maximum amount you want to achieve.
                          It is not a percentage, although it is purposely set to 100 by default.
        """
        if max_value is not None:
            self.update_max_value(max_value)
        build_progress = self._states_view(for_value)
        self.console.replace_last_msg(build_progress)

    def start(self):
        self.started_time = time.time()
        self._awaiting_update = True
        if not self.started:
            self.started = True
            self.console.persist_on_runtime()
            self.th_awaiting = self._create_awaiting()
            self.th_awaiting.start()
            self.n_times = 0

    def stop(self):
        if self.started:
            self._awaiting_update = False
            self.th_awaiting.join()
            self.started = False
            self.console.disable()

    def __len__(self):
        return len(self._states)

    def __getitem__(self, slice_):
        if isinstance(slice_, tuple):
            if max(slice_) > len(self):
                raise IndexError(f"{max(slice_)} isn't in progress")
            return tuple(self._states[idx] for idx in slice_ if idx < len(self))
        return self._states[slice_]

    def __enter__(self, *args, **kwargs):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if isinstance(exc_val, Exception):
            self.console.error(f'{os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}: {exc_val}')
        self.stop()


class ProgressIterator:
    def __init__(self, progress: ProgressBase, sequence: Sequence[Any]):
        self.sequence = sequence
        self.progress = progress

    def __next__(self):
        self.progress.start()
        for n, value in enumerate(self.sequence):
            if self.progress.started:
                self.progress.show_progress(for_value=n)
            yield value
        self.progress.stop()

    def __iter__(self):
        return next(self)


class Progress(ProgressBase):
    def __init__(self, name, states=None):
        super().__init__(Console(name), states=states)
        self.name = name

    def __call__(self, sequence: Sequence[Any]):
        return ProgressIterator(self, sequence)


if __name__ == "__main__":

    with Progress("Cereja") as prog1:
        for i, k in enumerate(prog1(range(100)), 1):
            time.sleep(0.05)

        for i in range(1, 600):
            time.sleep(0.05)
            prog1.show_progress(i, 600)
