"""Disposable, stdlib-only planning models. Not a production UI implementation."""
from dataclasses import dataclass
import heapq
import queue
import threading
import unicodedata


def sanitize(text):
    """Single-line text policy: neutralize controls before measurement."""
    return ''.join('\ufffd' if ord(c) < 32 or 127 <= ord(c) <= 159 else c
                   for c in text)


def conservative_width(text):
    """Return None for unsupported sequences, never guess emoji clusters."""
    text = sanitize(text)
    if any(ord(c) >= 0x1f000 or c == '\u200d' or
           0xfe00 <= ord(c) <= 0xfe0f for c in text):
        return None
    if text and unicodedata.combining(text[0]):
        return None
    return sum(0 if unicodedata.combining(c) else
               2 if unicodedata.east_asian_width(c) in 'WF' else 1
               for c in text)


@dataclass(frozen=True)
class Cell:
    text: str = ' '
    width: int = 1
    style: int = 0


class Frame:
    def __init__(self, width, height):
        self.width, self.height = width, height
        self.cells = [Cell()] * (width * height)
        self.dirty = set()

    def clone(self):
        result = Frame(self.width, self.height)
        result.cells = self.cells.copy()
        return result

    def _set(self, index, cell):
        self.cells[index] = cell
        self.dirty.add(index)

    def _erase(self, index):
        cell = self.cells[index]
        lead = index - 1 if cell.width == 0 else index
        span = self.cells[lead].width
        for pos in range(lead, lead + span):
            self._set(pos, Cell())

    def put(self, x, y, text, width=1, style=0):
        if width not in (1, 2):
            raise ValueError('explicit cell width required')
        if not (0 <= y < self.height and 0 <= x and x + width <= self.width):
            return False
        index = y * self.width + x
        for pos in range(index, index + width):
            self._erase(pos)
        self._set(index, Cell(sanitize(text), width, style))
        if width == 2:
            self._set(index + 1, Cell('', 0, style))
        return True


def diff(old, new, dirty=False):
    if (old.width, old.height) != (new.width, new.height):
        raise ValueError('resize requires full invalidation')
    candidates = sorted(new.dirty) if dirty else range(len(new.cells))
    return [(i, new.cells[i]) for i in candidates if old.cells[i] != new.cells[i]]


def encode(changes, width):
    """Model ANSI payload, per leading cell; not final-column-safe transport."""
    return ''.join(f'\x1b[{i // width + 1};{i % width + 1}H'
                   f'\x1b[{30 + cell.style % 8}m{cell.text}'
                   for i, cell in changes if cell.width).encode('utf-8')


class Mailbox:
    """Bounded FIFO, explicit rejection, lock-safe wakeup reset."""
    def __init__(self, limit=256):
        self.items = queue.Queue(limit)
        self.wakeup = threading.Event()
        self.lock = threading.Lock()

    def post(self, item):
        with self.lock:
            try:
                self.items.put_nowait(item)
            except queue.Full:
                return False
            self.wakeup.set()
            return True

    def drain(self, budget):
        result = []
        with self.lock:
            for _ in range(budget):
                try:
                    result.append(self.items.get_nowait())
                except queue.Empty:
                    break
            if self.items.empty():
                self.wakeup.clear()
        return result


class Timers:
    def __init__(self):
        self.heap = []
        self.sequence = 0

    def schedule(self, deadline, value):
        heapq.heappush(self.heap, (deadline, self.sequence, value))
        self.sequence += 1

    def timeout(self, now):
        return max(0, self.heap[0][0] - now) if self.heap else None

    def due(self, now, budget):
        result = []
        while self.heap and self.heap[0][0] <= now and len(result) < budget:
            result.append(heapq.heappop(self.heap)[2])
        return result
