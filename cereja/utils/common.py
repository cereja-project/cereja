from typing import Any, List, Iterable, Union, Optional
import logging
import sys

T = Union[int, float, str]

logger = logging.getLogger(__name__)
logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
consoleHandler = logging.StreamHandler(sys.stdout)
logger.addHandler(consoleHandler)
logger.setLevel(logging.DEBUG)


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


class ConvertDictError(Exception): pass

class Freq(dict):
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

    def __init__(self, items: Iterable[Any]):

        if not is_iterable(items):
            raise ValueError("The data you entered is not valid! Please give me iterable data.")

        data = self._to_dict(items)
        freq = self.sort_and_limit(data, len(data))
        super().__init__(freq)

    def __repr__(self):
        return super().__repr__()

    def _get_dict_from_keys(self, keys: list):
        return {item: self[item] for item in keys}

    def _verify_query(self, **kwargs):
        max_items = kwargs.get('max_items')
        if max_items:
            if not isinstance(max_items, int):
                raise TypeError(f"Value {max_items} isn't valid. Please give me integer.")

            assert max_items < len(
                self), "Not possible, because the maximum value taked is greater than the number of items."

    def _to_dict(self, items):
        try:
            values = {item: items.count(item) for item in items}
        except Exception as err:
            raise ConvertDictError("Cannot convert data to dictionary")
        return values

    @property
    def length(self):
        return len(self)
    
    @staticmethod
    def sort_and_limit(values: dict, max_items: int, reverse=True) -> dict:
        max_items = len(values) if max_items > len(values) else max_items
        return {item: values[item] for i, item in enumerate(sorted(values, key=values.get, reverse=reverse)) if
                i < max_items}

    def add_item(self, item):
        value = self.get(item)
        self[item] = value + 1 if value else 1

    def remove_item(self, item):
        value = self[item] - 1
        if value:
            self[item] = value
        else:
            del self[item]
            
    def most_freq(self, max_items: int):
        self._verify_query(max_items=max_items)
        most = list(self)[:max_items]
        return self._get_dict_from_keys(most)

    def least_freq(self, max_items: int):
        self._verify_query(max_items=max_items)
        less = list(self)[-max_items:]
        return self._get_dict_from_keys(less)

if __name__ == "__main__":
    pass
