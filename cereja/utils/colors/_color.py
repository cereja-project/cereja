from __future__ import annotations

from typing import Any

from . import converters as _converters

__all__ = ['Color']

class Color:
    # Constants for calculating relative luminance
    GAMMA_THRESHOLD = 0.03928
    GAMMA_CORRECTION_FACTOR = 12.92
    LINEAR_CORRECTION_FACTOR = 1.055
    LINEAR_CORRECTION_OFFSET = 0.055
    GAMMA_EXPONENT = 2.4

    # Constants for RGB sensitivity coefficients
    LUMINANCE_RED_COEFFICIENT = 0.2126
    LUMINANCE_GREEN_COEFFICIENT = 0.7152
    LUMINANCE_BLUE_COEFFICIENT = 0.0722
    
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

    def normalize(self):
        return Color(*_converters.normalize_rgb(self.red, self.green, self.blue))

    @property
    def luminance(self) -> float:
        """
        Calculates the relative luminance of the current color.

        This method computes the relative luminance of a color based on its RGB values,
        normalized and adjusted using gamma correction. The luminance is calculated by applying
        coefficients that reflect human sensitivity to different color components (red, green, and blue).

        Returns:
            float: The calculated relative luminance of the color. The luminance value is used
            in various standards (e.g., WCAG) to evaluate color contrast for accessibility.
        """
        def apply_gamma_correction(value: float) -> float:
            """
            Applies gamma correction to the normalized RGB value.

            Args:
                value (float): The normalized RGB component value (0-1).

            Returns:
                float: The gamma-corrected value.
            """
            if value <= Color.GAMMA_THRESHOLD:
                return value / Color.GAMMA_CORRECTION_FACTOR
            else:
                return ((value + Color.LINEAR_CORRECTION_OFFSET) / Color.LINEAR_CORRECTION_FACTOR) ** Color.GAMMA_EXPONENT

        # Normalize RGB values (0-255 to 0-1)
        r_normalized, g_normalized, b_normalized = self.normalize()

        # Apply gamma correction to the normalized RGB values
        r_adjusted = apply_gamma_correction(r_normalized)
        g_adjusted = apply_gamma_correction(g_normalized)
        b_adjusted = apply_gamma_correction(b_normalized)

        # Calculate luminance using weighted coefficients for red, green, and blue
        luminance = (
                Color.LUMINANCE_RED_COEFFICIENT * r_adjusted +
                Color.LUMINANCE_GREEN_COEFFICIENT * g_adjusted +
                Color.LUMINANCE_BLUE_COEFFICIENT * b_adjusted
        )

        return luminance

    @staticmethod
    def contrast_ratio(first_luminance: float, second_luminance: float) -> float:
        """
        Calculates the contrast ratio between two luminance values.

        This function computes the contrast ratio between two colors based on their luminance values.
        The contrast ratio is defined by the formula (L1 + 0.05) / (L2 + 0.05), where L1 is the
        luminance of the lighter color and L2 is the luminance of the darker color.

        Args:
            first_luminance (float): The luminance of the first color.
            second_luminance (float): The luminance of the second color.

        Returns:
            float: The contrast ratio between the two colors. The result is a value between 1 (no contrast)
            and 21 (maximum contrast), where higher values indicate better readability.
        """
        l1 = max(first_luminance, second_luminance)
        l2 = min(first_luminance, second_luminance)

        return (l1 + 0.05) / (l2 + 0.05)

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
        Generate a gradient between two validator.
        @param other: color to interpolate with
        @param steps: number of steps in the gradient
        @return: list of validator
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
