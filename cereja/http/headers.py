"""Case-insensitive HTTP headers that preserve repeated fields."""

from collections.abc import Iterator, Mapping

_TOKEN_CHARS = frozenset(
    "!#$%&'*+-.^_`|~0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
)


class Headers:
    def __init__(self, values=None):
        self._items: list[tuple[str, str]] = []
        if values is None:
            return
        source = values.items() if isinstance(values, Mapping) else values
        for name, value in source:
            self.add(name, value)

    @staticmethod
    def _validate(name, value):
        name, value = str(name), str(value)
        if not name or any(ch not in _TOKEN_CHARS for ch in name):
            raise ValueError(f"Invalid HTTP header name: {name!r}")
        for char in value:
            code = ord(char)
            if (code < 0x20 and char != "\t") or code == 0x7F or code > 0xFF:
                raise ValueError(f"Invalid HTTP header value for {name!r}")
        return name, value

    def add(self, name, value):
        self._items.append(self._validate(name, value))

    def set(self, name, value):
        lower = str(name).lower()
        self._items = [(n, v) for n, v in self._items if n.lower() != lower]
        self.add(name, value)

    def get_list(self, name):
        lower = str(name).lower()
        return [value for key, value in self._items if key.lower() == lower]

    def get(self, name, default=None):
        values = self.get_list(name)
        return ", ".join(values) if values else default

    def __getitem__(self, name):
        value = self.get(name)
        if value is None:
            raise KeyError(name)
        return value

    def __contains__(self, name):
        return bool(self.get_list(name))

    def __iter__(self) -> Iterator[tuple[str, str]]:
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def items(self):
        return list(self._items)

    def copy(self):
        return Headers(self._items)

    def __repr__(self):
        return f"Headers({self._items!r})"
