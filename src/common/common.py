from enum import Enum

class Direction(Enum):
    RIGHT = 1
    LEFT = 2
    UP = 3
    DOWN = 4


def hsv_to_rgb(h, s, v):
    """Convert HSV to an (r, g, b) tuple of ints in 0..255.

    h: hue in [0, 1) — values outside the range wrap.
    s: saturation in [0, 1].
    v: value in [0, 1].
    """
    if s <= 0.0:
        c = int(round(v * 255))
        return (c, c, c)
    h6 = (h % 1.0) * 6.0
    i = int(h6)
    f = h6 - i
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    if i == 0:
        r, g, b = v, t, p
    elif i == 1:
        r, g, b = q, v, p
    elif i == 2:
        r, g, b = p, v, t
    elif i == 3:
        r, g, b = p, q, v
    elif i == 4:
        r, g, b = t, p, v
    else:
        r, g, b = v, p, q
    return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))