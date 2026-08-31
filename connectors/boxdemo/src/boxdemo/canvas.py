"""A minimal RGB buffer and colour helpers.

Deliberately not imported from the box package. A connector talks to the box
over HTTP and nothing else, so it carries its own tiny rendering primitives —
the same reason gifcast depends on Pillow rather than on the box.
"""

RGB = tuple[int, int, int]


def hsv_to_rgb(h: float, s: float, v: float) -> RGB:
    """HSV -> RGB. Hue wraps; s and v are clamped to 0..1."""
    h = h % 1.0
    s = 0.0 if s < 0.0 else 1.0 if s > 1.0 else s
    v = 0.0 if v < 0.0 else 1.0 if v > 1.0 else v

    i = int(h * 6.0)
    f = h * 6.0 - i
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    r, g, b = (
        (v, t, p),
        (q, v, p),
        (p, v, t),
        (p, q, v),
        (t, p, v),
        (v, p, q),
    )[i % 6]
    return (int(r * 255 + 0.5), int(g * 255 + 0.5), int(b * 255 + 0.5))


class Canvas:
    """A width x height RGB buffer, flat and row-major from the top-left."""

    __slots__ = ("width", "height", "buf")

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.buf = bytearray(width * height * 3)

    def set_px(self, x: int, y: int, color: RGB) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            i = (y * self.width + x) * 3
            self.buf[i : i + 3] = bytes(color)

    def snapshot(self) -> bytes:
        return bytes(self.buf)
