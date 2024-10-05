from __future__ import annotations

__all__ = [
    "px_to_pt", "pt_to_px", "em_to_pt", "pt_to_em", "em_to_px", "pt_to_rem", "rem_to_px", "rem_to_pt", "pt_to_rem"
]

PIXELS_PER_INCH = 96  # Screen resolution standard (96 PPI)
POINTS_PER_INCH = 72  # 1 inch = 72 pt
DEFAULT_FONT_SIZE_PX = 16  # Default font size for em/rem (16px)

def px_to_pt(px: float) -> float:
    """
    Converts pixels (px) to points (pt), assuming a screen resolution of 96 PPI.

    This function converts a pixel value to its equivalent in points, based on the standard
    screen resolution of 96 pixels per inch (PPI).

    Args:
        px (float): The pixel value to convert. Must be a non-negative value.

    Returns:
        float: The equivalent value in points (pt).

    Raises:
        ValueError: If the pixel value is negative.
    """
    if px < 0:
        raise ValueError("Pixel value cannot be negative.")
    return (px * POINTS_PER_INCH) / PIXELS_PER_INCH

def pt_to_px(pt: float) -> float:
    """
    Converts points (pt) to pixels (px), assuming a screen resolution of 96 PPI.

    This function converts a point value to its equivalent in pixels, based on the standard
    screen resolution of 96 pixels per inch (PPI).

    Args:
        pt (float): The point value to convert. Must be a non-negative value.

    Returns:
        float: The equivalent value in pixels (px).

    Raises:
        ValueError: If the point value is negative.
    """
    if pt < 0:
        raise ValueError("Point value cannot be negative.")
    return (pt * PIXELS_PER_INCH) / POINTS_PER_INCH

def em_to_pt(em: float, base_font_size_px: float = DEFAULT_FONT_SIZE_PX) -> float:
    """
    Converts em units to points (pt), based on a given base font size in pixels.

    This function calculates the equivalent value in points for a given em value,
    based on the provided base font size in pixels.

    Args:
        em (float): The em value to convert. Must be a non-negative value.
        base_font_size_px (float): The base font size in pixels. Default is 16px.

    Returns:
        float: The equivalent value in points (pt).

    Raises:
        ValueError: If the em value is negative.
    """
    if em < 0:
        raise ValueError("EM value cannot be negative.")
    return px_to_pt(em * base_font_size_px)

def pt_to_em(pt: float, base_font_size_px: float = DEFAULT_FONT_SIZE_PX) -> float:
    """
    Converts points (pt) to em units, based on a given base font size in pixels.

    This function calculates the equivalent em value for a given point size, using
    the provided base font size in pixels.

    Args:
        pt (float): The point value to convert. Must be a non-negative value.
        base_font_size_px (float): The base font size in pixels. Default is 16px.

    Returns:
        float: The equivalent value in em units.

    Raises:
        ValueError: If the point value is negative.
    """
    if pt < 0:
        raise ValueError("Point value cannot be negative.")
    px_value = pt_to_px(pt)
    return px_value / base_font_size_px

def em_to_px(em: float, base_font_size_px: float = DEFAULT_FONT_SIZE_PX) -> float:
    """
    Converts em units to pixels (px), based on a given base font size in pixels.

    This function calculates the equivalent value in pixels for a given em value,
    using the provided base font size in pixels.

    Args:
        em (float): The em value to convert. Must be a non-negative value.
        base_font_size_px (float): The base font size in pixels. Default is 16px.

    Returns:
        float: The equivalent value in pixels (px).

    Raises:
        ValueError: If the em value is negative.
    """
    if em < 0:
        raise ValueError("EM value cannot be negative.")
    return em * base_font_size_px

def pt_to_rem(pt: float, base_font_size_px: float = DEFAULT_FONT_SIZE_PX) -> float:
    """
    Converts points (pt) to rem units, based on a given base font size in pixels.

    This function calculates the equivalent rem value for a given point size,
    using the provided base font size in pixels.

    Args:
        pt (float): The point value to convert. Must be a non-negative value.
        base_font_size_px (float): The base font size in pixels. Default is 16px.

    Returns:
        float: The equivalent value in rem units.

    Raises:
        ValueError: If the point value is negative.
    """
    if pt < 0:
        raise ValueError("Point value cannot be negative.")
    return pt_to_em(pt, base_font_size_px)

def rem_to_px(rem: float, base_font_size_px: float = DEFAULT_FONT_SIZE_PX) -> float:
    """
    Converts rem units to pixels (px), based on a given base font size in pixels.

    This function calculates the equivalent value in pixels for a given rem value,
    using the provided base font size in pixels.

    Args:
        rem (float): The rem value to convert. Must be a non-negative value.
        base_font_size_px (float): The base font size in pixels. Default is 16px.

    Returns:
        float: The equivalent value in pixels (px).

    Raises:
        ValueError: If the rem value is negative.
    """
    if rem < 0:
        raise ValueError("REM value cannot be negative.")
    return rem * base_font_size_px

def rem_to_pt(rem: float, base_font_size_px: float = DEFAULT_FONT_SIZE_PX) -> float:
    """
    Converts rem units to points (pt), based on a given base font size in pixels.

    This function calculates the equivalent value in points for a given rem value,
    using the provided base font size in pixels.

    Args:
        rem (float): The rem value to convert. Must be a non-negative value.
        base_font_size_px (float): The base font size in pixels. Default is 16px.

    Returns:
        float: The equivalent value in points (pt).

    Raises:
        ValueError: If the rem value is negative.
    """
    if rem < 0:
        raise ValueError("REM value cannot be negative.")
    return px_to_pt(rem * base_font_size_px)