"""RGB frame buffer used by every scene and display backend."""

import base64

from . import font

RGB = tuple[int, int, int]

#: Antialiasing coverage is converted with a fixed 2.2 rather than BOX_GAMMA:
#: it models perception of the LEDs, not the panel's tuning, and a Frame should
#: not need to know the engine's configuration to draw text.
_INV_GAMMA = 1 / 2.2


def hex_to_rgb(hex_code: str) -> RGB:
    """Parse '#RRGGBB' (or 'RGB'/'RRGGBB') into an 0-255 tuple."""
    h = hex_code.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(f"Invalid hex color: {hex_code!r}")
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except ValueError as exc:
        raise ValueError(f"Invalid hex color: {hex_code!r}") from exc


def rgb_to_hex(rgb: RGB) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


class Frame:
    """A width x height RGB pixel buffer, stored as a flat bytearray."""

    __slots__ = ("width", "height", "buf")

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.buf = bytearray(width * height * 3)

    def clear(self, color: RGB = (0, 0, 0)) -> None:
        if color == (0, 0, 0):
            # Fast path: zeroing beats building a repeated pattern.
            self.buf[:] = bytes(len(self.buf))
        else:
            self.buf[:] = bytes(color) * (self.width * self.height)

    def set_px(self, x: int, y: int, color: RGB) -> None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        i = (y * self.width + x) * 3
        self.buf[i : i + 3] = bytes(color)

    def blend_px(self, x: int, y: int, color: RGB, alpha: float) -> None:
        """Alpha-blend `color` over the existing pixel. alpha is clamped to 0..1."""
        if alpha <= 0.0 or not (0 <= x < self.width and 0 <= y < self.height):
            return
        if alpha >= 1.0:
            self.set_px(x, y, color)
            return
        i = (y * self.width + x) * 3
        buf = self.buf
        inv = 1.0 - alpha
        buf[i] = int(buf[i] * inv + color[0] * alpha)
        buf[i + 1] = int(buf[i + 1] * inv + color[1] * alpha)
        buf[i + 2] = int(buf[i + 2] * inv + color[2] * alpha)

    def draw_text(self, text: str, x: float, y: int, color: RGB) -> None:
        """Draw `text` with its top-left at (x, y).

        `x` may be fractional: each glyph column is split across the two
        neighbouring pixel columns, which is what makes scrolling look smooth
        instead of stepping one whole pixel at a time.
        """
        frac = x - int(x) if x >= 0 else x - (int(x) - 1)
        base = int(x) if x >= 0 else int(x) - 1
        # Split the coverage in *linear light*. Frame values are perceptual
        # and go through a ~2.2 gamma on the way to the LEDs, so a plain 50/50
        # split emits only 2 * 0.5**2.2 = 44% of a whole pixel's light, and
        # scrolling text pulses dim-bright at every half-pixel step. Raising
        # each share to 1/2.2 keeps the light emitted constant as it moves.
        left_a = (1.0 - frac) ** _INV_GAMMA
        frac = frac**_INV_GAMMA

        for index, char in enumerate(text):
            gx = base + index * font.ADVANCE
            # Skip glyphs entirely off either edge (the +1 covers the AA spill).
            if gx >= self.width or gx + font.GLYPH_WIDTH + 1 <= 0:
                continue
            rows = font.glyph(char)
            for row in range(font.GLYPH_HEIGHT):
                py = y + row
                if not 0 <= py < self.height:
                    continue
                mask = rows[row]
                if not mask:
                    continue
                for col in range(font.GLYPH_WIDTH):
                    if not mask & (0b10000 >> col):
                        continue
                    px = gx + col
                    self.blend_px(px, py, color, left_a)
                    if frac:
                        self.blend_px(px + 1, py, color, frac)

    def to_bytes(self) -> bytes:
        return bytes(self.buf)

    def to_base64(self) -> str:
        return base64.b64encode(self.buf).decode("ascii")
