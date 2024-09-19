from cereja.utils.colors import Color
from cereja.utils.typography import Typography

__all__ = ['contrast_checker']

large_text_thresholds = (4.5, 3)  # AAA: 4.5, AA: 3
small_text_thresholds = (7, 4.5)  # AAA: 7, AA: 4.5

def contrast_checker(first_color, other_color, font_size: str, is_bold=False) -> dict:
    """
    Checks the contrast ratio between two colors and determines the WCAG compliance level
    considering font size and whether the text is bold.

    This function calculates the contrast ratio between two colors and evaluates whether it meets
    WCAG compliance at AA and AAA levels. The compliance level depends on the text size:
    - Large text: >= 18pt or >= 14pt if bold.
    - Small text: Any font size smaller than what is defined for large text.

    Args:
        first_color (Any): The first color, which can be a hex string, tuple (RGB or RGBA), or a Color object.
        other_color (Any): The second color, which can be a hex string, tuple (RGB or RGBA), or a Color object.
        font_size (str): The font size (e.g., '16px', '12pt', '1.5em', '2rem'). Must include a valid unit.
        is_bold (bool): Indicates whether the text is bold. Default is False.

    Returns:
        dict: A dictionary showing if the contrast passes or fails for Small Text and Large Text at AA and AAA levels.
        The return is structured as follows:
        {
            'Element Type': {
                'Small Text': {
                    'AA': 'Pass' or 'Fail',
                    'AAA': 'Pass' or 'Fail',
                },
                'Large Text': {
                    'AA': 'Pass' or 'Fail',
                    'AAA': 'Pass' or 'Fail',
                }
            },
            'contrast_ratio': 'X.XX:1'  # The calculated contrast ratio
        }
    """
    first_color = Color.parse(first_color)
    other_color = Color.parse(other_color)

    # Extract the numeric value and unit from the font size
    font_size_value, font_unit = Typography.parse_font_size(font_size)

    typography = Typography(font_size_value, font_unit)
    font_size_pt = typography.pt

    # Determine if the font is "large" or "normal" based on size and whether it's bold
    if is_bold:
        # Bold fonts use a threshold of 14pt for large text
        is_large_text = font_size_pt >= 14
    else:
        # Normal fonts use a threshold of 18pt for large text
        is_large_text = font_size_pt >= 18

    contrast_ratio = first_color.contrast_ratio(first_color.luminance, other_color.luminance)

    small_text_level = {
        'AA': 'Pass' if contrast_ratio >= small_text_thresholds[1] else 'Fail',
        'AAA': 'Pass' if contrast_ratio >= small_text_thresholds[0] else 'Fail'
    }

    large_text_level = {
        'AA': 'Pass' if contrast_ratio >= large_text_thresholds[1] else 'Fail',
        'AAA': 'Pass' if contrast_ratio >= large_text_thresholds[0] else 'Fail'
    }

    result = {
        'Element Type': {
            'Small Text': {
                'AA': small_text_level['AA'],
                'AAA': small_text_level['AAA'],
            },
            'Large Text': {
                'AA': large_text_level['AA'],
                'AAA': large_text_level['AAA'],
            }
        },
        'contrast_ratio': f"{round(contrast_ratio, 2)}:1",
    }

    return result
