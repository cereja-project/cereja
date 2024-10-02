import unittest
from cereja.utils.colors import (
    rgb_to_hsl, hsl_to_rgb, rgb_to_hsv, hsv_to_rgb,
    rgb_to_cmyk, cmyk_to_rgb, Color, normalize_rgb
)


class TestColor(unittest.TestCase):
    def test_to_hex(self):
        color = Color(255, 0, 0)
        self.assertEqual(color.hex, "#ff0000")

    def test_from_hex(self):
        color = Color.from_hex("#ff0000")
        self.assertEqual((color.red, color.green, color.blue), (255, 0, 0))

    def test_to_hsl(self):
        color = Color(255, 0, 0)
        self.assertEqual(color.hsl, (0.0, 100.0, 50.0))

    def test_to_hsv(self):
        color = Color(255, 0, 0)
        self.assertEqual(color.hsv, (0, 100, 100))

    def test_to_cmyk(self):
        color = Color(255, 0, 0)
        self.assertEqual(color.cmyk, (0, 100, 100, 0))

    def test_parse(self):
        color = Color.parse("#ff0000")
        self.assertEqual((color.red, color.green, color.blue), (255, 0, 0))
        color = Color.parse((255, 0, 0))
        self.assertEqual((color.red, color.green, color.blue), (255, 0, 0))
        color = Color.parse(Color(255, 0, 0))
        self.assertEqual((color.red, color.green, color.blue), (255, 0, 0))

    def test_is_rgba(self):
        color = Color(255, 0, 0)
        self.assertFalse(color.is_rgba)
        color = Color(255, 0, 0, 255)
        self.assertTrue(color.is_rgba)
        self.assertEqual(color.rgba, (255, 0, 0, 255))
        self.assertEqual(color.rgb, (255, 0, 0))

    def test_to_rgba(self):
        color = Color(255, 0, 0, 255)
        self.assertEqual(color.rgba, (255, 0, 0, 255))
        self.assertEqual(color.rgb, (255, 0, 0))
        self.assertEqual(color.hex, "#ff0000")
        self.assertEqual(color.hsl, (0.0, 100.0, 50.0))
        self.assertEqual(color.hsv, (0, 100, 100))
        self.assertEqual(color.cmyk, (0, 100, 100, 0))

    def test_luminance(self):
        color = Color(255, 255, 255)  # White
        self.assertAlmostEqual(color.luminance, 1.0)

        color = Color(0, 0, 0)  # Black
        self.assertAlmostEqual(color.luminance, 0.0)

        color = Color(255, 0, 0)  # Red
        self.assertAlmostEqual(color.luminance, 0.2126, places=4)

    def test_contrast_ratio(self):
        white = Color(255, 255, 255)
        black = Color(0, 0, 0)
        red = Color(255, 0, 0)

        # Contrast ratio between white and black should be 21:1
        self.assertAlmostEqual(
            white.contrast_ratio(white.luminance, black.luminance), 21.0, places=1
        )

        # Contrast ratio between white and red
        self.assertAlmostEqual(
            white.contrast_ratio(white.luminance, red.luminance), 3.998, places=3
        )

        # Contrast ratio between black and red
        self.assertAlmostEqual(
            black.contrast_ratio(black.luminance, red.luminance), 5.25, places=2
        )


class TestConverters(unittest.TestCase):

    def test_rgb_to_hsl(self):
        h, s, l = rgb_to_hsl(255, 0, 0)
        self.assertAlmostEqual(h, 0.0)
        self.assertAlmostEqual(s, 100.0)
        self.assertAlmostEqual(l, 50.0)

    def test_hsl_to_rgb(self):
        r, g, b = hsl_to_rgb(0.0, 100.0, 50.0)
        self.assertEqual((r, g, b), (255, 0, 0))

    def test_rgb_to_hsv(self):
        h, s, v = rgb_to_hsv(255, 0, 0)
        self.assertEqual((h, s, v), (0, 100, 100))

    def test_hsv_to_rgb(self):
        r, g, b = hsv_to_rgb(0, 100, 100)
        self.assertEqual((r, g, b), (255, 0, 0))

    def test_rgb_to_cmyk(self):
        c, m, y, k = rgb_to_cmyk(255, 0, 0)
        self.assertEqual((c, m, y, k), (0, 100, 100, 0))

    def test_cmyk_to_rgb(self):
        r, g, b = cmyk_to_rgb(0, 100, 100, 0)
        self.assertEqual((r, g, b), (255, 0, 0))

    def test_normalize_rgb(self):
        # Test normalization of RGB values (255, 0, 0)
        normalized = normalize_rgb(255, 0, 0)
        self.assertEqual(normalized, (1.0, 0.0, 0.0))

        # Test normalization of RGB values (128, 128, 128)
        normalized = normalize_rgb(128, 128, 128)
        self.assertEqual(normalized, (0.5019607843137255, 0.5019607843137255, 0.5019607843137255))

        # Test normalization of RGB values (0, 255, 0)
        normalized = normalize_rgb(0, 255, 0)
        self.assertEqual(normalized, (0.0, 1.0, 0.0))


if __name__ == '__main__':
    unittest.main()
