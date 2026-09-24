"""Win32 constants grouped by their native operation.

IntEnum represents alternatives; IntFlag represents combinable bit masks.
Values remain integers at the ctypes boundary. These private enums do not
load native libraries or add names to the public Cereja API.
"""

from enum import IntEnum, IntFlag


class AlertSound(IntEnum):
    OK = 0x0000
    ICONHAND = 0x0010
    ICONQUESTION = 0x0020
    ICONEXCLAMATION = 0x0030
    ICONASTERISK = 0x0040


class WindowMessage(IntEnum):
    KEYDOWN = 0x0100
    KEYUP = 0x0101
    COMMAND = 0x0111
    MOUSEMOVE = 0x0200
    LBUTTONDOWN = 0x0201
    LBUTTONUP = 0x0202
    LBUTTONDBLCLK = 0x0203
    RBUTTONDOWN = 0x0204
    RBUTTONUP = 0x0205
    RBUTTONDBLCLK = 0x0206
    MBUTTONDOWN = 0x0207
    MBUTTONUP = 0x0208
    MBUTTONDBLCLK = 0x0209
    MOUSEWHEEL = 0x020A
    XBUTTONDOWN = 0x020B
    XBUTTONUP = 0x020C
    XBUTTONDBLCLK = 0x020D
    MOUSEHWHEEL = 0x020E


class ShowWindowCommand(IntEnum):
    HIDE = 0
    SHOWNORMAL = 1
    SHOWMINIMIZED = 2
    SHOWMAXIMIZED = 3
    SHOWNOACTIVATE = 4
    SHOW = 5
    MINIMIZE = 6
    SHOWMINNOACTIVE = 7
    SHOWNA = 8
    RESTORE = 9
    SHOWDEFAULT = 10


class MouseEvent(IntFlag):
    MOVE = 0x0001
    LEFTDOWN = 0x0002
    LEFTUP = 0x0004
    RIGHTDOWN = 0x0008
    RIGHTUP = 0x0010


class MouseKeyState(IntFlag):
    LBUTTON = 0x0001
    RBUTTON = 0x0002


class SystemMetric(IntEnum):
    CXSCREEN = 0
    CYSCREEN = 1


class MapVirtualKeyType(IntEnum):
    VK_TO_VSC = 0


class KeyboardMask(IntEnum):
    VIRTUAL_KEY = 0x00FF
    PRESSED = 0x8000


class KeyMessageFlag(IntFlag):
    KEY_UP = 0x80000000


class VirtualKey(IntEnum):
    BACKSPACE = 0x08
    TAB = 0x09
    CLEAR = 0x0C
    ENTER = 0x0D
    SHIFT = 0x10
    CTRL = 0x11
    ALT = 0x12
    PAUSE = 0x13
    CAPS_LOCK = 0x14
    ESC = 0x1B
    SPACEBAR = 0x20
    PAGE_UP = 0x21
    PAGE_DOWN = 0x22
    END = 0x23
    HOME = 0x24
    LEFT_ARROW = 0x25
    UP_ARROW = 0x26
    RIGHT_ARROW = 0x27
    DOWN_ARROW = 0x28
    INSERT = 0x2D
    DELETE = 0x2E
    DIGIT_0 = 0x30
    DIGIT_1 = 0x31
    DIGIT_2 = 0x32
    DIGIT_3 = 0x33
    DIGIT_4 = 0x34
    DIGIT_5 = 0x35
    DIGIT_6 = 0x36
    DIGIT_7 = 0x37
    DIGIT_8 = 0x38
    DIGIT_9 = 0x39
    A = 0x41
    B = 0x42
    C = 0x43
    D = 0x44
    E = 0x45
    F = 0x46
    G = 0x47
    H = 0x48
    I = 0x49
    J = 0x4A
    K = 0x4B
    L = 0x4C
    M = 0x4D
    N = 0x4E
    O = 0x4F
    P = 0x50
    Q = 0x51
    R = 0x52
    S = 0x53
    T = 0x54
    U = 0x55
    V = 0x56
    W = 0x57
    X = 0x58
    Y = 0x59
    Z = 0x5A
    F1 = 0x70
    F2 = 0x71
    F3 = 0x72
    F4 = 0x73
    F5 = 0x74
    F6 = 0x75
    F7 = 0x76
    F8 = 0x77
    F9 = 0x78
    F10 = 0x79
    F11 = 0x7A
    F12 = 0x7B
    OEM_SEMICOLON = 0xBA
    OEM_PLUS = 0xBB
    OEM_COMMA = 0xBC
    OEM_MINUS = 0xBD
    OEM_PERIOD = 0xBE
    OEM_SLASH = 0xBF
    OEM_BACKTICK = 0xC0
    OEM_LBRACKET = 0xDB
    OEM_BACKSLASH = 0xDC
    OEM_RBRACKET = 0xDD
    OEM_QUOTE = 0xDE


class DpiAwarenessContext(IntEnum):
    PER_MONITOR_AWARE_V2 = -4


class RasterOperation(IntFlag):
    SRCCOPY = 0x00CC0020
    CAPTUREBLT = 0x40000000


class CursorState(IntFlag):
    SHOWING = 0x0001
    SUPPRESSED = 0x0002


class MonitorFlag(IntFlag):
    PRIMARY = 0x0001


class PrintWindowFlag(IntFlag):
    CLIENTONLY = 0x0001
    RENDERFULLCONTENT = 0x0002


class DibColorMode(IntEnum):
    RGB_COLORS = 0


class DrawIconFlag(IntFlag):
    MASK = 0x0001
    IMAGE = 0x0002
    NORMAL = MASK | IMAGE
