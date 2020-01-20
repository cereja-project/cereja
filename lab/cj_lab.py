from typing import TypeVar

from cereja.common import flatten, get_shape

T = TypeVar('T')


class Vector(list):
    """
    -- Development proposal --
    Vector is a dynamic array, whose size can be increased and can store any type of objects

    """

    def __init__(self, values):
        super().__init__(values)
        self._size = len(self.flatten())
        self._shape = get_shape(self)

    @property
    def size(self):
        # Need to create smart way to check changes
        return self._size

    @property
    def shape(self):
        # need to create smart way to check changes
        return self._shape

    def first(self) -> T:
        return self[0]

    def flatten(self):
        return flatten(self)
