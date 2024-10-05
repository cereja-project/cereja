from __future__ import annotations
from . import converters as _converters

__all__ = ['Typography']

class Typography:

    def __init__(self, value: float, unit: str = 'px'):
        self.value = value
        self.unit = unit

    @property
    def px(self) -> float:
        """
        Converts the current value to pixels (px).
        """
        if self.unit == 'pt':
            return _converters.pt_to_px(self.value)
        elif self.unit in ['em', 'rem']:
            return self.value * _converters.DEFAULT_FONT_SIZE_PX
        return self.value

    @property
    def pt(self) -> float:
        """
        Converts the current value to points (pt).
        """
        if self.unit == 'px':
            return _converters.px_to_pt(self.value)
        elif self.unit == 'em':
            return _converters.em_to_pt(self.value, _converters.DEFAULT_FONT_SIZE_PX)
        elif self.unit == 'rem':
            return _converters.rem_to_pt(self.value, _converters.DEFAULT_FONT_SIZE_PX)
        return self.value

    @property
    def em(self) -> float:
        """
        Converts the current value to em, using the base font size.
        """
        if self.unit == 'px':
            return self.value / _converters.DEFAULT_FONT_SIZE_PX
        elif self.unit == 'pt':
            px_value = _converters.pt_to_px(self.value)
            return px_value / _converters.DEFAULT_FONT_SIZE_PX
        return self.value

    @property
    def rem(self) -> float:
        """
        Converts the current value to rem, based on the default font size.
        """
        return self.em  # rem is based on the root font size, similar to em

    @classmethod
    def from_px(cls, px_value: float):
        """
        Initializes the Typography from a pixel (px) value.
        """
        return cls(px_value, 'px')

    @classmethod
    def from_pt(cls, pt_value: float):
        """
        Initializes the Typography from a point (pt) value.
        """
        return cls(pt_value, 'pt')

    @classmethod
    def from_em(cls, em_value: float):
        """
        Initializes the Typography from an em value.
        """
        return cls(em_value, 'em')

    @classmethod
    def from_rem(cls, rem_value: float):
        """
        Initializes the Typography from a rem value.
        """
        return cls(rem_value, 'rem')

    @classmethod
    def parse_font_size(cls, font_size: str) -> tuple[float, str]:
        """
        Parse the font size string and extract the numeric value and the unit.

        Args:
            font_size (str): The font size as a string, e.g., '16px', '12pt', '1.5em', '2rem'.

        Returns:
            tuple: A tuple containing the numeric value and the unit as separate elements.
        """
        import re
        match = re.match(r"([\d.]+)(px|pt|em|rem)", font_size)
        if not match:
            raise ValueError(f"Invalid font size format: {font_size}")

        value = float(match.group(1))  # Extract the numeric value
        unit = match.group(2)  # Extract the unit (px, pt, em, rem)
        return value, unit

    def __eq__(self, other):
        """
        Checks equality between two Typography instances by comparing their values in pixels.
        """
        if isinstance(other, Typography):
            return self.px == other.px
        return False

    def __ne__(self, other):
        """
        Checks inequality between two Typography instances.
        """
        return not self.__eq__(other)

    def __repr__(self):
        """
        Provides a string representation of the Typography instance.
        """
        return f"Typography(value={self.value}, unit='{self.unit}')"
