from __future__ import annotations

__all__ = ["rgb_to_hex", "hex_to_rgb", "rgb_to_hsl", "hsl_to_rgb", "rgb_to_hsv", "hsv_to_rgb", "rgb_to_cmyk",
           "cmyk_to_rgb", "normalize_rgb"]

def normalize_rgb(r, g, b):
    """
    Normalizes the RGB values from 0-255 to the 0-1 range.

    This function converts the RGB color components, typically in the 0-255 range,
    to values in the 0-1 range. It is useful in various contexts of image processing,
    graphics, and color calculations, where color values need to be worked on in a normalized format.

    Args:
        r (int): The red component value, ranging from 0 to 255.
        g (int): The green component value, ranging from 0 to 255.
        b (int): The blue component value, ranging from 0 to 255.

    Returns:
        tuple[float, float, float]: A tuple containing the normalized red,
        green, and blue values, each in the 0-1 range.
    """
    return r / 255.0, g / 255.0, b / 255.0

def parse_hex(hex_value):
    hex_value = hex_value.lstrip("#")
    length = len(hex_value)
    if length == 3:
        r = int(hex_value[0] * 2, 16)
        g = int(hex_value[1] * 2, 16)
        b = int(hex_value[2] * 2, 16)
    elif length == 4:
        # RGBA
        r = int(hex_value[0] * 2, 16)
        g = int(hex_value[1] * 2, 16)
        b = int(hex_value[2] * 2, 16)
        a = int(hex_value[3] * 2, 16)
        return r, g, b, a
    elif length == 6:
        r = int(hex_value[:2], 16)
        g = int(hex_value[2:4], 16)
        b = int(hex_value[4:], 16)
    elif length == 8:
        # RGBA
        r = int(hex_value[:2], 16)
        g = int(hex_value[2:4], 16)
        b = int(hex_value[4:6], 16)
        a = int(hex_value[6:], 16)
        return r, g, b, a
    else:
        raise ValueError(f"Invalid hex color: {hex_value}")
    return r, g, b


def rgb_to_hex(r, g, b):
    return "#{:02x}{:02x}{:02x}".format(r, g, b)


def rgba_to_hex(r, g, b, a):
    return "#{:02x}{:02x}{:02x}{:02x}".format(r, g, b, a)


def hex_to_rgb(hex_value):
    value = parse_hex(hex_value)
    return value[:3]


def hex_to_rgba(hex_value):
    value = parse_hex(hex_value)
    if len(value) == 3:
        return value + (255,)
    return value


def rgb_to_hsl(r, g, b):
    r, g, b = normalize_rgb(r, g, b)
    max_c = max(r, g, b)
    min_c = min(r, g, b)
    l = (max_c + min_c) / 2.0
    if max_c == min_c:
        s = h = 0.0
    else:
        delta = max_c - min_c
        s = delta / (2.0 - max_c - min_c) if l > 0.5 else delta / (max_c + min_c)
        if max_c == r:
            h = (g - b) / delta + (g < b) * 6.0
        elif max_c == g:
            h = (b - r) / delta + 2.0
        elif max_c == b:
            h = (r - g) / delta + 4.0
        h /= 6.0
    return h * 360.0, s * 100.0, l * 100.0


def hsl_to_rgb(h, s, l):
    s /= 100.0
    l /= 100.0
    c = (1.0 - abs(2 * l - 1.0)) * s
    h /= 60.0
    x = c * (1.0 - abs(h % 2 - 1.0))
    if 0 <= h < 1:
        r, g, b = c, x, 0
    elif 1 <= h < 2:
        r, g, b = x, c, 0
    elif 2 <= h < 3:
        r, g, b = 0, c, x
    elif 3 <= h < 4:
        r, g, b = 0, x, c
    elif 4 <= h < 5:
        r, g, b = x, 0, c
    elif 5 <= h < 6:
        r, g, b = c, 0, x
    m = l - c / 2.0
    return int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)


def hsl_to_rgba(h, s, l):
    r, g, b = hsl_to_rgb(h, s, l)
    return r, g, b, 255


def rgb_to_hsv(r, g, b):
    r, g, b = normalize_rgb(r, g, b)
    max_c = max(r, g, b)
    min_c = min(r, g, b)
    delta = max_c - min_c

    if delta == 0:
        h = 0
    elif max_c == r:
        h = (g - b) / delta % 6
    elif max_c == g:
        h = (b - r) / delta + 2
    elif max_c == b:
        h = (r - g) / delta + 4
    h = int(h * 60)
    if h < 0:
        h += 360

    s = 0 if max_c == 0 else delta / max_c
    v = max_c

    return h, int(s * 100), int(v * 100)


def hsv_to_rgb(h, s, v):
    s /= 100
    v /= 100
    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c

    if 0 <= h < 60:
        r, g, b = c, x, 0
    elif 60 <= h < 120:
        r, g, b = x, c, 0
    elif 120 <= h < 180:
        r, g, b = 0, c, x
    elif 180 <= h < 240:
        r, g, b = 0, x, c
    elif 240 <= h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x

    return int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)


def hsv_to_rgba(h, s, v):
    r, g, b = hsv_to_rgb(h, s, v)
    return r, g, b, 255


def rgb_to_cmyk(r, g, b):
    if (r == 0) and (g == 0) and (b == 0):
        return 0, 0, 0, 100
    c = 1 - r / 255.0
    m = 1 - g / 255.0
    y = 1 - b / 255.0
    k = min(c, m, y)
    c = (c - k) / (1 - k)
    m = (m - k) / (1 - k)
    y = (y - k) / (1 - k)
    return int(c * 100), int(m * 100), int(y * 100), int(k * 100)


def cmyk_to_rgb(c, m, y, k):
    r = 255 * (1 - c / 100) * (1 - k / 100)
    g = 255 * (1 - m / 100) * (1 - k / 100)
    b = 255 * (1 - y / 100) * (1 - k / 100)
    return int(r), int(g), int(b)


def cmyk_to_rgba(c, m, y, k):
    r, g, b = cmyk_to_rgb(c, m, y, k)
    return r, g, b, 255
