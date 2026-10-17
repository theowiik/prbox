"""Colour helpers for generating visuals."""

from ..render.frame import RGB


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
