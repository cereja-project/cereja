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
from typing import Union, Sequence, Optional, Tuple
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

    def __init__(self, x: Union['Point', Sequence, float], y: Optional[float] = None,
                 z: Optional[float] = None):
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
                if len(x) in [2, 3]:
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
        return (self - other).magnitude

    def angle_theta(self, other: 'Point', degrees=False) -> float:
        """
        Computes the angle (in radians or degrees) between this point and another point when treated as vectors.

        Args:
            other (Point): The other point (or vector) with which the angle is calculated.
            degrees (bool): if true returns the angle in degrees, default is False.

        Returns:
            float: The angle in radians or degress.
        """
        other = Point(other)
        dot_product = self.dot(other)
        magnitudes_product = self.magnitude * other.magnitude
        acos = math.acos(max(-1., min(1., dot_product / magnitudes_product)))
        return math.degrees(acos) if degrees else acos

    def rotation_angle(self, point, axis=0):
        """
        Creates vector v1 = self - point and calculates the angle of v1 with respect to an axis (x, y or z)
        @param point: Another point
        @param axis: x, y or z
        @return: Degrees
        """
        v1 = self - point

        if axis == 0:
            v2 = Point(1, 0, 0)  # Horizontal
        elif axis == 1:
            v2 = Point(0, 1, 0)  # Vertical
        else:
            v2 = Point(0, 0, 1)  # depth

        angle = v1.angle_theta(v2, True)
        return angle

    def bounding_box(self, w: int, h: int, position: str = "center") -> Tuple['Point', 'Point', 'Point', 'Point']:
        """
        Calculate the coordinates of a bounding box based on the given width, height, and position relative to a point.

        Args:
            w (int): Width of the bounding box.
            h (int): Height of the bounding box.
            position (str, optional): Position of the bounding box relative to the point.
                Valid positions: "center", "left-top", "left-bottom", "right_top", "right_bottom".
                Defaults to "center".

        Raises:
            ValueError: Raised when an invalid position is provided.

        Returns:
            Tuple[Point, Point, Point, Point]: A tuple containing four Point instances representing the
                coordinates of the bounding box in the order (start_x, start_y), (end_x, start_y),
                (end_x, end_y), and (start_x, end_y).
        """
        position = position.lower().strip()
        if position == "center":
            start_x, start_y = self.x - (w // 2), self.y - (h // 2)
        elif position == "left-top":
            start_x, start_y = self.x, self.y
        elif position == "left-bottom":
            start_x, start_y = self.x, self.y - (h // 2)
        elif position == "right_top":
            start_x, start_y = self.x - w, self.y
        elif position == "right_bottom":
            start_x, start_y = self.x - w, self.y - h
        else:
            raise ValueError('Invalid position. Enter a valid position for the point. Valid positions: ('
                             '"center", "left-top", "left-bottom", "right_top", "right_bottom")')

        end_x = start_x + w
        end_y = start_y + h

        return Point(start_x, start_y), Point(end_x, start_y), Point(end_x, end_y), Point(start_x, end_y)

    def rotate(self, angle: float, center=(0, 0, 0), axis: str = 'z') -> 'Point':
        """
        Rotates the point around the specified axis by the given angle.

        Args:
            angle (float): The rotation angle in degrees.
            center (Point): The rotation origin.
            axis (str, optional): The axis around which the point is rotated.
                                  Can be 'x', 'y', or 'z'. Default is 'z'.

        Returns:
            Point: A new point representing the rotated position.
        """
        angle = math.radians(angle)  # Convert angle to radians

        translated_point = self - center
        if axis == 'z':
            x_new = translated_point.x * math.cos(angle) - translated_point.y * math.sin(angle)
            y_new = translated_point.x * math.sin(angle) + translated_point.y * math.cos(angle)
            return Point(x_new, y_new, translated_point.z) + center

        elif axis == 'y':
            # Rotation around the Y axis
            x_new = translated_point.x * math.cos(angle) + translated_point.z * math.sin(angle)
            z_new = -translated_point.x * math.sin(angle) + translated_point.z * math.cos(angle)
            return Point(x_new, translated_point.y, z_new) + center

        elif axis == 'x':
            # Rotation around the X axis
            y_new = translated_point.y * math.cos(angle) - translated_point.z * math.sin(angle)
            z_new = translated_point.y * math.sin(angle) + translated_point.z * math.cos(angle)
            return Point(translated_point.x, y_new, z_new) + center

        else:
            raise ValueError(f"Invalid axis: {axis}. Axis should be 'x', 'y', or 'z'.")

    def manhattan_distance_to(self, other: 'Point') -> float:
        """
        Computes the Manhattan distance between this point and another point.

        Args:
            other (Point): The other point to which the Manhattan distance is calculated.

        Returns:
            float: The Manhattan distance between the two points.
        """
        return sum(abs(a - b) for a, b in zip(self, other))

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
