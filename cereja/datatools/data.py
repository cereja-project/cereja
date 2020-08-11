"""

Copyright (c) 2019 The Cereja Project

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from collections import Counter
from typing import Optional, Sequence, Dict, Any

from cereja.arraytools import is_iterable
from cereja.filetools import JsonFile

__all__ = ["Freq"]


class Freq(Counter):
    def __init__(self, data: Optional[Sequence] = ()):
        assert is_iterable(data), "Isn't iterable."
        self._elements_size = None
        super().__init__(data)

    @property
    def probability(self):
        """
        Return dict with percent
        """
        return dict(zip(self.keys(), map(self.item_prob, self.most_common())))

    def __getattribute__(self, item):
        if item in ('probability', 'item_prob'):
            # ensures correct probability calculation
            self._elements_size = sum(self.values())
        return super(Freq, self).__getattribute__(item)

    def sample(self, max_freq: Optional[int] = None, max_items: int = -1, order='most_common'):
        """
        :param max_freq: limit sample by frequency
        :param max_items: limit sample size
        :param order: choice order in ('most_common', 'least_common')
        :return: sample dictionary
        """
        assert order in ('most_common', 'least_common'), ValueError(
                f"Order {order} not in ('most_common', 'least_common')")
        assert isinstance(max_items, int), TypeError(f"max_items {type(max_items)} != {int}")
        max_items = len(self) if max_items == -1 else max_items
        if order == 'least_common':
            query = super(Freq, self).most_common()[:-max_items - 1:-1]
        else:
            query = super(Freq, self).most_common(max_items)
        if max_freq is not None:
            assert isinstance(max_freq, int), TypeError(f"freq {type(max_freq)} != {int}")
            query = list(filter(lambda item: item[1] <= max_freq, query))
        return dict(query)

    def most_common(self, n: Optional[int] = None) -> Dict[Any, int]:
        return dict(super(Freq, self).most_common(n))

    def least_freq(self, max_items: int = -1):
        return self.sample(max_items=max_items, order='least_common')

    def item_prob(self, item: Any) -> float:
        if item in self:
            return self.get(item) / self._elements_size or sum(self.values())
        return 0.0

    def to_json(self, path_, probability=False, **kwargs):
        content = self.probability if probability else self
        JsonFile(path_=path_, data=content).save(**kwargs)
