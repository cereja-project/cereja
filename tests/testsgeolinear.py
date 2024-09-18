import unittest
import math

from cereja.geolinear import Point


class TestPoint(unittest.TestCase):

    def setUp(self):
        """Setup some common test points."""
        self.p1 = Point(1, 2, 3)
        self.p2 = Point(1, 2, 3)
        self.p3 = Point(4, 5)
        self.p4 = Point(0, 0, 0)
        self.p5 = Point(self.p1)

        self.point = Point(10, 20)

    def test_point_equality(self):
        """Test the equality comparison method."""
        self.assertEqual(self.p1, self.p2)
        self.assertNotEqual(self.p1, self.p3)

    def test_point_copy(self):
        """Test copying a Point object."""
        self.assertEqual(self.p1, self.p5)

    def test_point_inequality(self):
        """Test the inequality comparison method."""
        self.assertNotEqual(self.p1, self.p3)
        self.assertNotEqual(self.p1, self.p4)

    def test_point_less_than(self):
        """Test the less than comparison method."""
        self.assertTrue(self.p4 < self.p1)
        self.assertFalse(self.p1 < self.p2)

    def test_point_less_than_or_equal(self):
        """Test the less than or equal to comparison method."""
        self.assertTrue(self.p4 <= self.p1)
        self.assertTrue(self.p1 <= self.p2)

    def test_point_greater_than(self):
        """Test the greater than comparison method."""
        self.assertTrue(self.p3 > self.p1)
        self.assertFalse(self.p1 > self.p3)

    def test_point_greater_than_or_equal(self):
        """Test the greater than or equal to comparison method."""
        self.assertTrue(self.p3 >= self.p1)
        self.assertTrue(self.p1 >= self.p2)

    def test_magnitude(self):
        """Test the magnitude method."""
        self.assertEqual(self.p4.magnitude, 0)
        self.assertEqual(self.p1.magnitude, math.sqrt(14))

    def test_dot_product(self):
        """Test the dot product method."""
        self.assertEqual(self.p1.dot(self.p2), 14)

    def test_cross_product(self):
        """Test the cross product method for 3D points."""
        result = self.p1.cross(Point(2, 3, 4))
        self.assertEqual(result, Point(-1, 2, -1))

    def test_addition(self):
        """Test addition of points."""
        result = self.p1 + self.p3
        self.assertEqual(result, Point(5, 7, 3))

    def test_subtraction(self):
        """Test subtraction of points."""
        result = self.p1 - self.p2
        self.assertEqual(result, Point(0, 0, 0))

    def test_scalar_multiplication(self):
        """Test scalar multiplication."""
        result = self.p1 * 2
        self.assertEqual(result, Point(2, 4, 6))

    def test_scalar_division(self):
        """Test scalar division."""
        result = self.p1 / 2
        self.assertEqual(result, Point(0.5, 1, 1.5))

    def test_center_position(self):
        # Testar a posição central da bounding box
        bbox = self.point.bounding_box(4, 6, position="center")
        self.assertEqual(bbox, (Point(8, 17), Point(12, 17), Point(12, 23), Point(8, 23)))

    def test_left_top_position(self):
        # Testar a posição left-top da bounding box
        bbox = self.point.bounding_box(4, 6, position="left-top")
        self.assertEqual(bbox, (Point(10, 20), Point(14, 20), Point(14, 26), Point(10, 26)))

    def test_invalid_position(self):
        # Testar posição inválida da bounding box
        with self.assertRaises(ValueError):
            self.point.bounding_box(4, 6, position="invalid_position")

    def test_manhattan_distance(self):
        # Testa a distância de Manhattan entre pontos iguais
        result = self.p1.manhattan_distance_to(self.p2)
        self.assertEqual(result, 0)

        # Testa a distância de Manhattan entre pontos diferentes
        result = self.p1.manhattan_distance_to(self.p3)
        self.assertEqual(result, abs(1 - 4) + abs(2 - 5) + abs(3 - 6))

        # Testa a distância de Manhattan para uma tupla de coordenadas
        result = Point((1, 4)).manhattan_distance_to((2, 5))
        self.assertEqual(result, abs(1 - 2) + abs(4 - 5))

if __name__ == '__main__':
    unittest.main()
