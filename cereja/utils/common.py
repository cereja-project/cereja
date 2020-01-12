from typing import Any, List, Union, Optional, Sequence, Tuple
import math
import logging
import sys

__all__ = ['theta_angle', 'is_iterable', 'group_items_in_batches', 'remove_duplicate_items', 'is_sequence', 'flatten',
           'Freq']
T = Union[int, float, str]

logger = logging.getLogger(__name__)
logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
consoleHandler = logging.StreamHandler(sys.stdout)
logger.addHandler(consoleHandler)
logger.setLevel(logging.DEBUG)


def theta_angle(u: Tuple[float, float], v: Tuple[float, float]) -> float:
    """
    Calculates and returns theta angle between two vectors

    e.g usage:
    >>> u = (2,2)
    >>> v = (0, -2)
    >>> theta_angle(u, v)
    135.0
    """
    x1, y1 = u
    x2, y2 = v
    return math.degrees(math.acos((x1 * x2 + y1 * y2) / (math.sqrt(x1 ** 2 + y1 ** 2) * math.sqrt(x2 ** 2 + y2 ** 2))))


def is_iterable(obj: Any) -> bool:
    """
    Return whether an object is iterable or not.

    :param obj: Any object for check
    """
    try:
        iter(obj)
    except TypeError:
        return False
    return True


def group_items_in_batches(items: List[Any], items_per_batch: int = 0, fill: Any = None) -> List[List[Any]]:
    """
    Responsible for grouping items in batch taking into account the quantity of items per batch

    e.g.
    >>> group_items_in_batches(items=[1,2,3,4], items_per_batch=3)
    [[1, 2, 3], [4]]
    >>> group_items_in_batches(items=[1,2,3,4], items_per_batch=3, fill=0)
    [[1, 2, 3], [4, 0, 0]]

    :param items: list of any values
    :param items_per_batch: number of items per batch
    :param fill: fill examples when items is not divisible by items_per_batch, default is None
    :return:
    """
    items_length = len(items)
    if not isinstance(items_per_batch, int):
        raise TypeError(f"Value for items_per_batch is not valid. Please send integer.")
    if items_per_batch < 0 or items_per_batch > len(items):
        raise ValueError(f"Value for items_per_batch is not valid. I need a number integer between 0 and {len(items)}")
    if items_per_batch == 0:
        return items

    if fill is not None:
        missing = items_per_batch - items_length % items_per_batch
        items += missing * [fill]

    batches = []

    for i in range(0, items_length, items_per_batch):
        batch = [group for group in items[i:i + items_per_batch]]
        batches.append(batch)
    return batches


def remove_duplicate_items(items: Optional[list]) -> Any:
    """
    remove duplicate items in an item list or duplicate items list of list

    e.g usage:
    >>> remove_duplicate_items([1,2,1,2,1])
    [1, 2]
    >>> remove_duplicate_items(['hi', 'hi', 'ih'])
    ['hi', 'ih']

    >>> remove_duplicate_items([['hi'], ['hi'], ['ih']])
    [['hi'], ['ih']]
    >>> remove_duplicate_items([[1,2,1,2,1], [1,2,1,2,1], [1,2,1,2,3]])
    [[1, 2, 1, 2, 1], [1, 2, 1, 2, 3]]
    """
    # TODO: improve function
    if not is_iterable(items) or isinstance(items, str):
        raise TypeError("Send iterable except string.")

    try:
        return list(dict.fromkeys(items))
    except TypeError:
        return sorted([list(item) for item in set(tuple(x) for x in items)], key=items.index)


def is_sequence(obj: Any) -> bool:
    """
    Return whether an object a Sequence or not, exclude strings.

    :param obj: Any object for check
    """
    if isinstance(obj, str):
        return False
    return is_iterable(obj)


def flatten(sequence: Sequence[Any], max_recursion: int = -1) -> Union[List[Any], Any]:
    """
    Receives values, whether arrays of values, regardless of their shape and flatness
    :param sequence: Is sequence of values.
    :param max_recursion: allows you to control a recursion amount, for example if you send a
    sequence=[1,2, [[3]]] and max_recursion=1 your return will be [1, 2, [3]]. :return: flattened array

    e.g usage:

    >>> sequence = [[1, 2, 3], [], [[2, [3], 4], 6]]
    >>> flatten(sequence)
    [1, 2, 3, 2, 3, 4, 6]
    >>> flatten(sequence, max_recursion=2)
    [1, 2, 3, 2, [3], 4, 6]
    """
    if not isinstance(max_recursion, int):
        raise TypeError(f"Value for max_recursion is not valid. Please send integer.")

    if not is_sequence(sequence):
        return sequence

    flattened = []
    for obj in sequence:
        if is_sequence(obj) and max_recursion:
            recursive_flattened = flatten(obj, max_recursion - 1)
            for i in recursive_flattened:
                flattened.append(i)
        else:
            flattened.append(obj)
    return flattened


class ConvertDictError(Exception): pass


class Freq:
    """
    [!] It's still under development [!]

    >>> freq = Freq([1,2,3,3,4,5,6,7,6,7,12,31,123,5,3])
    {3: 3, 5: 2, 6: 2, 7: 2, 1: 1, 2: 1, 4: 1, 12: 1, 31: 1, 123: 1}

    >>> freq.add_item(3)
    {3: 4, 5: 3, 6: 2, 7: 2, 1: 1, 2: 1, 4: 1, 12: 1, 31: 1, 123: 1}

    >>> freq.most_freq(4)
    {3: 3, 5: 2, 6: 2, 7: 2}

    >>> freq.least_freq(1)
    {123: 1}

    >>> freq_str = Freq('My car is red I like red color'.split())
    {'red': 2, 'My': 1, 'car': 1, 'is': 1, 'I': 1, 'like': 1, 'color': 1}
    """

    def __init__(self, data: list):
        if not is_iterable(data):
            raise ValueError("The data you entered is not valid! Please give me iterable data.")

        self.data = data
        self.freq = self._freq(len(self.data))

    def __len__(self):
        return len(self.data)

    def __repr__(self):
        return self.freq.__repr__()

    def _freq(self, max_items: int = None):
        try:
            max_items = max_items or len(self.data)
            values = {item: self.data.count(item) for item in self.data}
            max_items = len(self.data) if max_items > len(self.data) else max_items
            freq = {item: values[item] for i, item in enumerate(sorted(values, key=values.get, reverse=True)) if
                    i < max_items}
        except Exception as err:
            raise ConvertDictError("Cannot convert data to dictionary")
        return freq

    def _verify_query(self, **kwargs):
        max_items = kwargs.get('max_items')
        if max_items:
            if not isinstance(max_items, int):
                raise TypeError(f"Value {max_items} isn't valid. Please give me integer.")

            assert max_items < len(
                self), "Not possible, because the maximum value taked is greater than the number of items."

    def _get_dict_from_keys(self, keys: list):
        return {item: self.freq[item] for item in keys}

    def item(self, item):
        return self.freq[item]

    def most_freq(self, max_items: int):
        self._verify_query(max_items=max_items)
        most = list(self.freq)[:max_items]
        return self._get_dict_from_keys(most)

    def least_freq(self, max_items: int):
        self._verify_query(max_items=max_items)
        less = list(self.freq)[-max_items:]
        return self._get_dict_from_keys(less)

    def add_item(self, item):
        self.data.append(item)
        self.freq = self._freq()

    def remove_item(self, item):
        self.data.remove(item)
        self.freq = self._freq()

    def items(self):
        return self.freq.items()


if __name__ == "__main__":
    pass
