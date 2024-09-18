from __future__ import annotations
from cereja.utils.colors import Color

__all__ = ['contrast_checker']

def contrast_checker(first_color, other_color) -> dict:
    """
    Checks the contrast ratio between two colors and determines the WCAG compliance level.

    This function calculates the contrast ratio between two colors and assigns a WCAG accessibility level
    based on the contrast ratio. The levels are:
      - "AAA" (ratio >= 7) for the highest contrast.
      - "AA" (ratio >= 4.5) for good contrast.
      - "A" for lower contrast that does not meet the "AA" standard.

    Args:
        first_color (Any): The first color, can be a hex string, tuple (RGB or RGBA), or a Color object.
        other_color (Any): The second color, can be a hex string, tuple (RGB or RGBA), or a Color object.

    Returns:
        dict: A dictionary containing:
            - 'level': The WCAG compliance level ("AAA", "AA", or "A").
            - 'contrast_ratio': A string representing the contrast ratio formatted to 2 decimal places.
    """
    # Parse the input colors into Color objects
    first_color = Color.parse(first_color)
    other_color = Color.parse(other_color)

    # Calculate the contrast ratio between the two colors
    contrast_ratio = first_color.contrast_ratio(first_color.luminance, other_color.luminance)

    # Determine the WCAG compliance level based on the contrast ratio
    if contrast_ratio >= 7:
        level = "AAA"
    elif contrast_ratio >= 4.5:
        level = "AA"
    else:
        level = "A"

    # Return the contrast ratio and compliance level
    return {
        'level': level,
        'contrast_ratio': f"{round(contrast_ratio, 2)}:1",
    }
