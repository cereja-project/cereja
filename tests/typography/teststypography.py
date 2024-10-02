import unittest
from cereja.utils.typography import (
    px_to_pt, pt_to_px, em_to_pt, pt_to_em, em_to_px, pt_to_rem, rem_to_px, rem_to_pt
)


class TestTypographyConverters(unittest.TestCase):
    """
    Unit tests for typography conversion functions. Each test checks for the correct conversion
    between pixel (px), point (pt), em, and rem units, using standard assumptions such as
    96 PPI (pixels per inch) for screen resolution and 16px as the base font size for em/rem.
    """

    def test_px_to_pt(self):
        """
        Test conversion from pixels (px) to points (pt).

        The function should correctly convert 96px to 72pt and 48px to 36pt.
        Additionally, the test checks for ValueError when a negative pixel value is provided.
        """
        self.assertAlmostEqual(px_to_pt(96), 72.0)  # 96px should be 72pt
        self.assertAlmostEqual(px_to_pt(48), 36.0)  # 48px should be 36pt
        with self.assertRaises(ValueError):
            px_to_pt(-1)  # Negative values should raise an error

    def test_pt_to_px(self):
        """
        Test conversion from points (pt) to pixels (px).

        The function should correctly convert 72pt to 96px and 36pt to 48px.
        Additionally, the test checks for ValueError when a negative point value is provided.
        """
        self.assertAlmostEqual(pt_to_px(72), 96.0)
        self.assertAlmostEqual(pt_to_px(36), 48.0)
        with self.assertRaises(ValueError):
            pt_to_px(-1)

    def test_em_to_pt(self):
        """
        Test conversion from em units to points (pt).

        The function should correctly convert 1em to 12pt (based on a 16px base font size),
        and 1.5em to 18pt. Additionally, the test checks for ValueError when a negative em value is provided.
        """
        self.assertAlmostEqual(em_to_pt(1), 12.0)
        self.assertAlmostEqual(em_to_pt(1.5), 18.0)
        with self.assertRaises(ValueError):
            em_to_pt(-1)

    def test_pt_to_em(self):
        """
        Test conversion from points (pt) to em units.

        The function should correctly convert 12pt to 1em (based on a 16px base font size),
        and 18pt to 1.5em. Additionally, the test checks for ValueError when a negative point value is provided.
        """
        self.assertAlmostEqual(pt_to_em(12), 1.0)
        self.assertAlmostEqual(pt_to_em(18), 1.5)
        with self.assertRaises(ValueError):
            pt_to_em(-1)

    def test_em_to_px(self):
        """
        Test conversion from em units to pixels (px).

        The function should correctly convert 1em to 16px (based on a 16px base font size),
        and 1.5em to 24px. Additionally, the test checks for ValueError when a negative em value is provided.
        """
        self.assertAlmostEqual(em_to_px(1), 16.0)
        self.assertAlmostEqual(em_to_px(1.5), 24.0)
        with self.assertRaises(ValueError):
            em_to_px(-1)

    def test_pt_to_rem(self):
        """
        Test conversion from points (pt) to rem units.

        The function should correctly convert 12pt to 1rem (based on a 16px base font size),
        and 18pt to 1.5rem. Additionally, the test checks for ValueError when a negative point value is provided.
        """
        self.assertAlmostEqual(pt_to_rem(12), 1.0)
        self.assertAlmostEqual(pt_to_rem(18), 1.5)
        with self.assertRaises(ValueError):
            pt_to_rem(-1)

    def test_rem_to_px(self):
        """
        Test conversion from rem units to pixels (px).

        The function should correctly convert 1rem to 16px (based on a 16px base font size),
        and 1.5rem to 24px. Additionally, the test checks for ValueError when a negative rem value is provided.
        """
        self.assertAlmostEqual(rem_to_px(1), 16.0)
        self.assertAlmostEqual(rem_to_px(1.5), 24.0)
        with self.assertRaises(ValueError):
            rem_to_px(-1)

    def test_rem_to_pt(self):
        """
        Test conversion from rem units to points (pt).

        The function should correctly convert 1rem to 12pt (based on a 16px base font size),
        and 1.5rem to 18pt. Additionally, the test checks for ValueError when a negative rem value is provided.
        """
        self.assertAlmostEqual(rem_to_pt(1), 12.0)
        self.assertAlmostEqual(rem_to_pt(1.5), 18.0)
        with self.assertRaises(ValueError):
            rem_to_pt(-1)


if __name__ == "__main__":
    unittest.main()
