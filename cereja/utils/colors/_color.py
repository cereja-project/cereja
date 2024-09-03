from __future__ import annotations

from typing import Any

from . import converters as _converters

__all__ = ['Color']


class Color:
    def __init__(self, red, green, blue, alpha=None):
        self.red = red
        self.green = green
        self.blue = blue
        self.alpha = alpha if alpha is not None else 255
        self._is_rgba = alpha is not None

    @property
    def is_rgba(self):
        return self._is_rgba

    @property
    def rgba(self):
        return self.red, self.green, self.blue, self.alpha

    @property
    def rgb(self):
        return self.red, self.green, self.blue

    @property
    def hex(self):
        return _converters.rgb_to_hex(self.red, self.green, self.blue)

    @property
    def hsl(self):
        return _converters.rgb_to_hsl(self.red, self.green, self.blue)

    @property
    def hsv(self):
        return _converters.rgb_to_hsv(self.red, self.green, self.blue)

    @property
    def cmyk(self):
        return _converters.rgb_to_cmyk(self.red, self.green, self.blue)

    @classmethod
    def from_hex(cls, hex_value):
        val_parsed = _converters.parse_hex(hex_value)
        if len(val_parsed) == 3:
            r, g, b = val_parsed
            return cls(r, g, b)
        return cls(*val_parsed)

    @classmethod
    def parse(cls, color: Any):
        if isinstance(color, Color):
            return color
        if isinstance(color, str):
            return cls.from_hex(color)
        if isinstance(color, tuple):
            if len(color) == 3:
                return cls(*color)
            if len(color) == 4:
                return cls(*color[:3], alpha=color[3])
        raise ValueError("Invalid color")

    def interpolate(self, other, factor):
        other = self.parse(other)
        r = self.red + factor * (other.red - self.red)
        g = self.green + factor * (other.green - self.green)
        b = self.blue + factor * (other.blue - self.blue)
        if self.is_rgba and other.is_rgba:
            a = self.alpha + factor * (other.alpha - self.alpha)
        else:
            a = None
        return Color(r, g, b, a)

    def generate_gradient(self, other, steps):
        """
        Generate a gradient between two colors.
        @param other: color to interpolate with
        @param steps: number of steps in the gradient
        @return: list of colors
        """
        return [self.interpolate(other, i / steps) for i in range(steps)]

    def __eq__(self, other):
        return self.rgb == self.parse(other)

    def __ne__(self, other):
        return not self.__eq__(self.parse(other))

    def __hash__(self):
        return hash(self.rgba)

    def __getitem__(self, item):
        if item == 0:
            return self.red
        if item == 1:
            return self.green
        if item == 2:
            return self.blue
        if item == 3:
            return self.alpha
        raise IndexError("Invalid index")

    def __setitem__(self, key, value):
        if key == 0:
            self.red = value
        elif key == 1:
            self.green = value
        elif key == 2:
            self.blue = value
        elif key == 3:
            self.alpha = value
            self._is_rgba = True
        else:
            raise IndexError("Invalid index")

    def __iter__(self):
        return iter(self.rgba) if self.is_rgba else iter(self.rgb)

    def __len__(self):
        return 4 if self.is_rgba else 3

    def __repr__(self):
        if self.is_rgba:
            return f"Color(R={self.red}, G={self.green}, B={self.blue}, A={self.alpha})"
        else:
            return f"Color(R={self.red}, G={self.green}, B={self.blue})"
