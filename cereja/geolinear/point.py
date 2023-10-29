"""
Copyright (c) 2019 The Cereja Project

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
from typing import Union, Sequence
import math

__all__ = ["Point"]


class Point:
    """
    Represents a point in a 2D or 3D space.

    Attributes:
        x (Union[int, float]): X-coordinate of the point.
        y (Union[int, float]): Y-coordinate of the point.
        z (Union[int, float]): Z-coordinate of the point. Defaults to 0 for 2D points.
        _is_3d (bool): A private attribute indicating if the point is 3D.
    """

    def __init__(self, x: Union['Point', Sequence, int, float], y: Union[int, float] = None,
                 z: Union[int, float] = None):
        """
        Initializes a Point object with x, y, and optionally z coordinates.

        Args:
            x (Union[int, float]): X-coordinate of the point.
            y (Union[int, float]): Y-coordinate of the point.
            z (Union[int, float], optional): Z-coordinate of the point. Defaults to 0.
        """
        if isinstance(x, Point):
            return  # If x is a Point instance, skip initialization

        try:
            if y is None:
                if len(x) in [2, 3] and sum(x) >= 0:
                    x, y, z = (*x, z) if len(x) == 2 else x
            elif not (isinstance(x, (int, float))
                      and isinstance(y, (int, float))
                      and (isinstance(z, (int, float)) or z is None)):
                raise ValueError
        except Exception:
            msg = x if y is None else f"({x}, {y}, {x})"
            raise ValueError(
                    f"A point must have 2 or 3 coordinates. Amount received {msg}")

        z, self._is_3d = (0.0, False) if z is None else (z, True)

        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def __new__(cls, x: Union['Point', int, float], y: Union[int, float] = None, z: Union[int, float] = None):
        if isinstance(x, Point):
            return x  # Return the existing instance

        instance = super(Point, cls).__new__(cls)
        return instance  # Return a new instance

    @property
    def is_3d(self):
        return self._is_3d

    @property
    def magnitude(self) -> float:
        """Computes the magnitude (or norm) of the point when treated as a vector from the origin."""
        return math.sqrt(sum(coord ** 2 for coord in self))

    def dot(self, other: 'Point') -> float:
        """Computes the dot product between this point and another point."""
        return sum(a * b for a, b in zip(self, other))

    def cross(self, other: 'Point') -> 'Point':
        """Computes the cross product between this point and another point. Only applicable for 3D points."""
        return Point(
                self.y * other.z - self.z * other.y,
                self.z * other.x - self.x * other.z,
                self.x * other.y - self.y * other.x
        )

    @property
    def normalize(self) -> 'Point':
        """Returns a normalized version of the point (or vector)."""
        mag = self.magnitude
        return Point(self.x / mag, self.y / mag, self.z / mag)

    @property
    def coordinates(self) -> tuple:
        """Returns a tuple of the point's coordinates."""
        return self.x, self.y, self.z

    def distance_to(self, other: 'Point') -> float:
        """
        Computes the Euclidean distance between this point and another point.

        Args:
            other (Point): The other point to which the distance is calculated.

        Returns:
            float: The distance between the two points.
        """
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(self, other)))

    def angle_theta(self, other: 'Point', degrees=False) -> float:
        """
        Computes the angle (in radians or degrees) between this point and another point when treated as vectors.

        Args:
            other (Point): The other point (or vector) with which the angle is calculated.
            degrees (bool): if true returns the angle in degrees, default is False.

        Returns:
            float: The angle in radians.
        """
        dot_product = self.dot(other)
        magnitudes_product = self.magnitude * other.magnitude
        acos = math.acos(max(-1., min(1., dot_product / magnitudes_product)))
        return math.degrees(acos) if degrees else acos

    def __getitem__(self, item: Union[int, str]) -> Union[int, float]:
        """Allows indexing into the point to retrieve its coordinates."""
        if isinstance(item, str):
            return getattr(self, item.lower())
        return self.coordinates[item]

    def __iter__(self):
        """Returns an iterator over the point's coordinates."""
        return iter(self.coordinates)

    def __add__(self, other: 'Point') -> 'Point':
        """
        Implements the addition of two points.

        Args:
            other (Point): The other point to add.

        Returns:
            Point: A new point representing the sum of the two points' coordinates.
        """
        return Point(*(a + b for a, b in zip(self, other)))

    def __sub__(self, other: 'Point') -> 'Point':
        """
        Implements the subtraction of two points.

        Args:
            other (Point): The other point to subtract.

        Returns:
            Point: A new point representing the difference of the two points' coordinates.
        """
        return Point(*(a - b for a, b in zip(self, other)))

    def __repr__(self) -> str:
        """Returns the official string representation of the point."""
        return f"Point({self.x}, {self.y}, {self.z})"

    def __str__(self) -> str:
        """Returns the string representation of the point's coordinates."""
        return f"{self.coordinates}"

    def __mul__(self, scalar: Union[int, float]) -> 'Point':
        """Implements scalar multiplication of the point."""
        return Point(self.x * scalar, self.y * scalar, self.z * scalar)

    def __truediv__(self, scalar: Union[int, float]) -> 'Point':
        """Implements scalar division of the point."""
        return Point(self.x / scalar, self.y / scalar, self.z / scalar)

    def __eq__(self, other: Union['Point', Sequence]) -> bool:
        """
        Compares (==) two Point objects based on their coordinates.

        it's the same as a == b

        Args:
            other (Point): Another Point object.

        Returns:
            bool: True if their coordinates are identical, False otherwise.
        """
        other = Point(other)
        return self.coordinates == other.coordinates

    def __ne__(self, other: Union['Point', Sequence]) -> bool:
        """
        Checks inequality (!=) between two Point objects based on their coordinates.

        Args:
            other (Point): Another Point object.

        Returns:
            bool: True if their coordinates are different, False otherwise.
        """
        return not self == other

    def __lt__(self, other: Union['Point', Sequence]) -> bool:
        """
        Checks if the current Point object is "less than" (<) another Point object.

        The comparison is primarily based on the magnitude. If magnitudes are equal,
        lexicographical comparison is used (i.e., x first, then y, then z).

        Args:
            other (Point): Another Point object.

        Returns:
            bool: True if the current point is "less than" the other point, False otherwise.
            ValueError if the other object is not a Point.
        """
        other = Point(other)
        return (self.magnitude, *self.coordinates) < (other.magnitude, *other.coordinates)

    def __le__(self, other: Union['Point', Sequence]) -> bool:
        """
        Checks if the current Point object is "less than or equal to" (<=) another Point object.

        The comparison is primarily based on the magnitude. If magnitudes are equal,
        lexicographical comparison is used (i.e., x first, then y, then z).

        Args:
            other (Point): Another Point object.

        Returns:
            bool: True if the current point is "less than or equal to" the other point, False otherwise.
            ValueError if the other object is not a Point.
        """
        other = Point(other)
        return (self.magnitude, *self.coordinates) <= (other.magnitude, *other.coordinates)

    def __gt__(self, other: Union['Point', Sequence]) -> bool:
        """
        Checks if the current Point object is "greater than" (>) another Point object.

        The comparison is primarily based on the magnitude. If magnitudes are equal,
        lexicographical comparison is used (i.e., x first, then y, then z).

        Args:
            other (Point): Another Point object.

        Returns:
            bool: True if the current point is "greater than" the other point, False otherwise.
            ValueError if the other object is not a Point.
        """
        other = Point(other)
        return (self.magnitude, *self.coordinates) > (other.magnitude, *other.coordinates)

    def __ge__(self, other: Union['Point', Sequence]) -> bool:
        """
        Checks if the current Point object is "greater than or equal to" another Point object.

        The comparison is primarily based on the magnitude. If magnitudes are equal,
        lexicographical comparison is used (i.e., x first, then y, then z).

        Args:
            other (Point): Another Point object.

        Returns:
            bool: True if the current point is "greater than or equal to" (>=) the other point, False otherwise.
            ValueError if the other object is not a Point.
        """
        other = Point(other)
        return (self.magnitude, *self.coordinates) >= (other.magnitude, *other.coordinates)
