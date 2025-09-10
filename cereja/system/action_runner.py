import threading
import time
from typing import Any, Dict, List, Tuple, Union
from cereja import Window, Timer

T_POINT = Tuple[int, int]


class Instruction:
    """
    Represents a single instruction: move, click or hotkey.
    """
    VALID_TYPES = {'move', 'click', 'hotkey', 'wait'}

    def __init__(self,
                 param: Union[int, Tuple[int, int], str],
                 delay_after: float = 0.1,
                 **kwargs):
        instruction_type = kwargs.get('type')
        if instruction_type not in self.VALID_TYPES:
            raise ValueError(f"Invalid instruction type: {instruction_type}. Must be one of {self.VALID_TYPES}")

        self.type = instruction_type
        self.param = param
        self.delay_after = delay_after

        # Configure timer based on instruction type
        timer_duration = param if instruction_type == 'wait' else delay_after
        self.timer = Timer(timer_duration, start=False, auto_reset=False)

    @property
    def is_ready(self) -> bool:
        """
        Check if the instruction is ready to be executed.
        """
        # For wait instructions, start timer if not started and return not ready
        if not self.timer.started:
            if self.type == 'wait':
                self.timer.start()
                return False
            return True

        # For regular instructions, they're ready if the timer has elapsed
        return self.timer.is_timeout

    def execute(self,
                window: Window,
                positions: List[Dict[str, Any]],
                hotkeys: List[Dict[str, Any]]):
        """
        Execute this instruction once in the window context.
        """
        if self.type == 'move':
            ori_idx, dest_idx = self.param
            p1 = positions[ori_idx]['point']
            p2 = positions[dest_idx]['point']
            window.mouse.drag_to(p1, p2)

        elif self.type == 'click':
            pos_idx, button = self.param
            pt = positions[pos_idx]['point']
            if button == 'right':
                window.mouse.click_right(pt)
            else:
                window.mouse.click_left(pt)

        elif self.type == 'hotkey':
            hk_idx: int = self.param
            combo: str = hotkeys[hk_idx]['combo']
            window.keyboard.key_press(combo)

        elif self.type == 'wait':
            pass  # Wait handled by timer

        self.timer._start = 0


class Action:
    """
    Represents a configured action that consists of multiple instructions.
    """

    def __init__(self,
                 name: str,
                 instructions: List[Union[Instruction, Dict[str, Any]]],
                 interval: float,
                 enabled: bool = True):
        self.name = name
        self.interval = interval
        self.enabled = enabled

        # Convert dict instructions to Instruction objects
        self._instructions = []
        for i in instructions:
            if isinstance(i, Instruction):
                self._instructions.append(i)
            else:
                self._instructions.append(Instruction(**i))

        # Initialize instruction pointer
        self._current_index = 0

    @property
    def has_instructions(self):
        return bool(self._instructions)

    def get_next_instruction(self):
        """Get the current instruction without advancing the pointer"""
        if not self.has_instructions:
            return None
        return self._instructions[self._current_index]

    def advance_instruction(self):
        """Move to the next instruction, cycling back to start if needed"""
        if not self.has_instructions:
            return

        self._current_index = (self._current_index + 1) % len(self._instructions)

    def execute(self,
                window: Window,
                positions: List[Dict[str, Any]],
                hotkeys: List[Dict[str, Any]]):
        """
        Execute the current instruction and advance to the next one.
        """
        if not self.enabled or not self.has_instructions:
            return

        instruction = self.get_next_instruction()
        if not instruction.is_ready:
            return

        try:
            instruction.execute(window, positions, hotkeys)
            self.advance_instruction()
        except Exception as err:
            print(f"Error executing action '{self.name}': {err}")


class ActionRunner:
    """
    Executes each Action repeatedly in its own thread.
    """

    def __init__(self,
                 actions,
                 window,
                 positions,
                 hotkeys):
        self.actions = [a for a in actions]
        self.window = window
        self.positions = positions
        self.hotkeys = hotkeys
        self._stop = threading.Event()
        # Use Timer objects for each action
        self._timers = {a: Timer(a.interval, start=False, auto_reset=True) for a in self.actions}

    def start(self):
        # Start all timers
        for timer in self._timers.values():
            timer.start()

        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        """
        Runs all actions periodically using Timer objects to manage intervals.
        """
        while not self._stop.is_set():
            now_actions = []

            # Check which actions should be executed
            for action, timer in self._timers.items():
                if timer.is_timeout:
                    now_actions.append(action)
                    timer.reset()  # Reset the timer for the next execution

            # Execute the actions
            for action in now_actions:
                try:
                    action.execute(self.window, self.positions, self.hotkeys)
                except Exception as err:
                    print(f"Erro ao executar action '{action.name}': {err}")

            # Sleep a small amount to prevent CPU hogging
            if not self._stop.wait(timeout=0.01):  # Small sleep between checks
                continue

    def stop(self):
        self._stop.set()
