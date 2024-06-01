import math

from .point import Point
from .. import shape_is_ok


class Circle:
    def __init__(self, center: Point, radius: float):
        self.center = center
        self.radius = radius

    @property
    def area(self) -> float:
        """Calculate the area of the circle."""
        return math.pi * self.radius ** 2

    @property
    def circumference(self) -> float:
        """Calculate the circumference of the circle."""
        return 2 * math.pi * self.radius

    def contains(self, point: Point) -> bool:
        """Check if a given point is inside the circle."""
        return self.center.distance_to(point) <= self.radius

    @property
    def diameter(self):
        return self.circumference / math.pi


class Triangle:
    def __init__(self, p1: Point, p2: Point, p3: Point):
        self.p1 = p1
        self.p2 = p2
        self.p3 = p3

    @staticmethod
    def side_length(p1: Point, p2: Point) -> float:
        """Calculate length of a side between two points."""
        return p1.distance_to(p2)

    @property
    def perimeter(self) -> float:
        """Calculate the perimeter of the triangle."""
        return self.side_length(self.p1, self.p2) + \
            self.side_length(self.p2, self.p3) + \
            self.side_length(self.p1, self.p3)

    @property
    def area(self) -> float:
        """Calculate the area of the triangle using Heron's formula."""
        s = self.perimeter / 2
        a = self.side_length(self.p1, self.p2)
        b = self.side_length(self.p2, self.p3)
        c = self.side_length(self.p1, self.p3)
        return math.sqrt(s * (s - a) * (s - b) * (s - c))


class Rectangle:
    def __init__(self, point1: Point, point2: Point):
        self.point1 = point1
        self.point2 = point2

    @property
    def width(self) -> float:
        """Width of the rectangle."""
        return abs(self.point1.x - self.point2.x)

    @property
    def height(self) -> float:
        """Height of the rectangle."""
        return abs(self.point1.y - self.point2.y)

    @property
    def area(self) -> float:
        """Calculate the area of the rectangle."""
        return self.width * self.height

    @property
    def perimeter(self) -> float:
        """Calculate the perimeter of the rectangle."""
        return 2 * (self.width + self.height)


class Dimension:
    def __init__(self, w, h):
        self._width = w
        self._height = h
        self._ratio = w / h
        self._center = w // 2, h // 2

    @property
    def ratio(self):
        return self._ratio

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    def rect(self, vec, size, keep_ratio=False):
        x, y = vec
        w = size
        h = size
        if keep_ratio:
            h = h // self.ratio
        x2 = x + w
        y2 = y + h

        return [(x, y), (x, y2), (x2, y), (x2, y2)]

    @property
    def center(self):
        return self._center

    @property
    def center_x(self):
        return self.center[0]

    @property
    def center_y(self):
        return self.center[1]

    @staticmethod
    def fix_rect_pts(pts):
        assert shape_is_ok(pts), ValueError(f"Expected a list with 4 points (x, y), received {pts}")
        pts = sorted(pts)
        x1 = pts[0][0]
        x2 = pts[-1][0]

        y1 = pts[0][1]
        y2 = pts[-1][1]
        return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]

    @classmethod
    def from_rect_points(cls, pts):
        points = cls.fix_rect_pts(pts)
        w = points[1][0] - points[0][0]
        h = points[-1][1] - points[0][1]
        return cls(w, h)

    def circle_edges(self, ra):
        pass

    def __repr__(self):
        return f"Dim(w={self._width}, y={self._height})"


if __name__ == "__main__":
    BASE_PICTURE_SHEET_DIM = [720, 1280]  # WxH
    W_SHEET = 653
    H_SHEET = 923

    # QRCODE
    W_QRCODE = 102
    H_QRCODE = 102
    QRCODE_CENTER_X_DIST_TO_WINDOW_CENTER = 241
    QRCODE_CENTER_Y_DIST_TO_WINDOW_CENTER = 396

    # CELULAR
    WINDOW_SIZE = [750, 1334]
    WINDOW_CENTER = WINDOW_SIZE[0] // 2, WINDOW_SIZE[1] // 2

    # pegar proporção
    PX = BASE_PICTURE_SHEET_DIM[0] / WINDOW_SIZE[0]
    PY = BASE_PICTURE_SHEET_DIM[1] / WINDOW_SIZE[1]

    # Calcula tamanho da folha em relação a tela
    W_SHEET_WINDOW, H_SHEET_WINDOW = W_SHEET * PX, H_SHEET * PY

    # Calcula o ponto inicial da folha na tela
    WINDOW_SHEET_X1, WINDOW_SHEET_Y1 = (
    WINDOW_CENTER[0] - (W_SHEET_WINDOW // 2), WINDOW_CENTER[1] - H_SHEET_WINDOW // 2)

    # Calcula o ponto final da folha na tela
    WINDOW_SHEET_X2, WINDOW_SHEET_Y2 = WINDOW_SHEET_X1 + W_SHEET_WINDOW, WINDOW_SHEET_Y1 + H_SHEET_WINDOW

    # SET LOC QR_CODE
    WINDOW_QRCODE_CENTER = WINDOW_CENTER[0] + (QRCODE_CENTER_X_DIST_TO_WINDOW_CENTER * PX), WINDOW_CENTER[1] - (
                QRCODE_CENTER_Y_DIST_TO_WINDOW_CENTER * PY)
    W_QRCODE_WINDOW = W_QRCODE * PX
    H_QRCODE_WINDOW = H_QRCODE * PY
    WINDOW_QRCODE_X1, WINDOW_QRCODE_Y1 = WINDOW_QRCODE_CENTER[0] - (W_QRCODE_WINDOW // 2), WINDOW_QRCODE_CENTER[1] - (
                H_QRCODE_WINDOW // 2)
    WINDOW_QRCODE_X2, WINDOW_QRCODE_Y2 = WINDOW_QRCODE_X1 + W_QRCODE_WINDOW, WINDOW_QRCODE_Y1 + H_QRCODE_WINDOW
