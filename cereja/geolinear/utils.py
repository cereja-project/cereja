import math

__all__ = ["Rotation"]

from typing import Union


class Rotation:
    __axis_map = {0: "x", 1: "y", 2: "z"}

    def __init__(self, degrees: Union[int, float]):
        self._degress = degrees
        self._angle_rad = math.radians(degrees)
        self._cos_angle = math.cos(self._angle_rad)
        self._sin_angle = math.sin(self._angle_rad)
        self._rot_x = [[1, 0, 0], [0, self._cos_angle, -self._sin_angle], [0, self._sin_angle, self._cos_angle]]
        self._rot_y = [[self._cos_angle, 0, self._sin_angle], [0, 1, 0], [-self._sin_angle, 0, self._cos_angle]]
        self._rot_z = [[self._cos_angle, -self._sin_angle, 0], [self._sin_angle, self._cos_angle, 0], [0, 0, 1]]
        self._rot_2d = [[self._cos_angle, -self._sin_angle], [self._sin_angle, self._cos_angle]]

    def __repr__(self):
        return f"{self.__class__.__name__}({self._degress}°)"

    @property
    def rot_3d_x(self):
        return self._rot_x

    @property
    def rot_3d_y(self):
        return self._rot_y

    @property
    def rot_3d_z(self):
        return self._rot_z

    @property
    def rot_2d(self):
        return self._rot_2d

    def rotate_point(self, point, axis=None):
        if len(point) == 2:
            rx = self._rot_2d[0][0] * point[0] + self._rot_2d[0][1] * point[1]
            ry = self._rot_2d[1][0] * point[0] + self._rot_2d[1][1] * point[1]
            return [rx, ry]
        assert len(point) == 3, ValueError(f"{point} isn't 3D point.")
        if axis is None:
            axis = 0
        else:
            assert (axis.lower() if isinstance(axis, str) else axis) in ("x", "y", "z", 0, 1, 2), ValueError(
                    "Invalid axis: choose 'x', 'y', 'z' or 0, 1, 2")
        axis = axis if isinstance(axis, str) else self.__axis_map[int(axis)]
        if axis == "x":
            rot = self.rot_3d_x
        elif axis == "y":
            rot = self.rot_3d_y
        else:
            rot = self.rot_3d_z

        rx = (rot[0][0] * point[0]) + (rot[0][1] * point[1]) + (rot[0][2] * point[2])
        ry = (rot[1][0] * point[0]) + (rot[1][1] * point[1]) + (rot[1][2] * point[2])
        rz = (rot[2][0] * point[0]) + (rot[2][1] * point[1]) + (rot[2][2] * point[2])

        return [rx, ry, rz]

    def rotate(self, val, axis=None):
        from cereja import get_shape, reshape, flatten, shape_is_ok

        if not shape_is_ok(val):
            raise ValueError("value isn't valid to rotate.")

        shape = get_shape(val)
        if len(shape) == 1:
            return self.rotate_point(val, axis=axis)

        return reshape(list(map(lambda point: self.rotate_point(point, axis=axis), flatten(val, depth=len(shape) - 2))),
                       shape)
