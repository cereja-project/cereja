import threading
import time
from typing import Any, Dict, List, Tuple, Union
from cereja import Window, Timer

T_POINT = Tuple[int, int]


class Instruction:
    """
    Represents a single instruction: move, click or hotkey.
    """

    def __init__(self,
                 param: Union[int, Tuple[int, int], str],
                 delay_after: float = 0.1,
                 **kwargs):
        assert 'type' in kwargs, "Instruction must have a 'type' field"
        self.type = kwargs['type']  # 'move', 'click', 'hotkey', 'wait'
        self.param = param
        self.delay_after = delay_after
        self.timer = Timer(0.1, start=False)  # Default timer for action execution
        self.timer = Timer(delay_after if kwargs['type'] != 'wait' else
                           param + delay_after
                           , start=False, auto_reset=False)  # Timer for delay after execution

    @property
    def is_ready(self) -> bool:
        """
        Check if the instruction is ready to be executed.
        """
        if not self.timer.started:
            return True
        if self.type != 'wait' and self.timer.is_timeout:
            return True
        # For 'wait' type, check if the timer has elapsed
        return self.timer.is_timeout

    def execute(self,
                window: Window,
                positions: List[Dict[str, Any]],
                hotkeys: List[Dict[str, Any]]):
        """
        Execute this instruction once in the window context.
        """
        if self.type == 'move':
            ori_idx, dest_idx = self.param  # Tuple[int,int]
            p1: T_POINT = positions[ori_idx]['point']
            p2: T_POINT = positions[dest_idx]['point']
            window.mouse.drag_to(p1, p2)

        elif self.type == 'click':
            pos_idx, button = self.param  # (int, 'left'|'right')
            pt: T_POINT = positions[pos_idx]['point']
            if button == 'right':
                window.mouse.click_right(pt)
            else:
                window.mouse.click_left(pt)

        elif self.type == 'hotkey':
            hk_idx: int = self.param
            combo: str = hotkeys[hk_idx]['combo']
            window.keyboard.press_and_release(combo, secs=0.1)

        elif self.type == 'wait':
            # Just wait the specified seconds
            pass

        else:
            raise ValueError(f"Unknown instruction type: {self.type}")

        self.timer.start()
        time.sleep(0.1)  # Small delay to ensure the action is registered


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
        self._instructions = [i if isinstance(i, Instruction) else Instruction(**i) for i in instructions]
        self.interval = interval
        self.enabled = enabled
        self._last_instruction = None
        self.instructions = self._get_instructions()

    def _get_instructions(self):
        while True:
            if len(self._instructions) == 0:
                yield
            for indx, position in enumerate(self._instructions):
                yield position

    def get_next_instruction(self):
        if len(self._instructions) == 0:
            return None
        if self._last_instruction is None:
            self._last_instruction = next(self.instructions)
            return self._last_instruction
        return self._last_instruction

    def execute(self,
                window: Window,
                positions: List[Dict[str, Any]],
                hotkeys: List[Dict[str, Any]]):
        """
        Execute all instructions in sequence.
        """
        if not self.enabled:
            return
        instruction = self.get_next_instruction()
        if instruction is None or not instruction.is_ready:
            return
        try:
            instruction.execute(window, positions, hotkeys)
            # After executing, reset the last instruction
            self._last_instruction = None
        except Exception as err:
            print(f"Erro ao executar ação '{self.name}': {err}")
            return


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
        # agenda inicial: next_run para cada action
        self._schedule = {a: time.time() for a in self.actions}

    def start(self):
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        """
        Roda todas as ações periodicamente, mas aguarda de forma eficiente
        até a próxima execução ou até que stop seja sinalizado.
        """
        while not self._stop.is_set():
            now = time.time()

            # Executa todas as ações vencidas
            for action, next_run in list(self._schedule.items()):
                if now >= next_run:
                    try:
                        action.execute(self.window, self.positions, self.hotkeys)
                    except Exception as err:
                        print(f"Erro ao executar action '{action.name}': {err}")
                    # Reagenda próxima execução
                    self._schedule[action] = now + action.interval

            # Se não houver ações agendadas, dorme até receber o stop
            if not self._schedule:
                self._stop.wait()  # aguarda indefinidamente até stop.set()
                break

            # Calcula o tempo até a próxima ação
            next_times = self._schedule.values()
            next_execution = min(next_times)
            timeout = max(0, next_execution - time.time())

            # Aguarda até o timeout ou até stop ser sinalizado
            self._stop.wait(timeout=timeout)

    def stop(self):
        self._stop.set()
