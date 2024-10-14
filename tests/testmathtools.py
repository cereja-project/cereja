import unittest
import math

from cereja.mathtools import degrees_to_radian, distance_between_points


class MathToolsTests(unittest.TestCase):
    def test_degrees_to_radian(self):
        self.assertEqual(degrees_to_radian(30), math.pi / 6)
        self.assertEqual(degrees_to_radian(60), math.pi / 3)

    def test_distance_between_points(self):
        self.assertEqual(distance_between_points((1, 1), (1, 1)), 0)
        self.assertEqual(distance_between_points((2, 6), (5, 10)), 5)
        self.assertEqual(distance_between_points((1, 1), (6, 13)), 13)

if __name__ == "__main__":
    unittest.main()