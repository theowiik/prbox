"""Scenes: things that can draw themselves into a Frame over time.

The core ships only what the box fundamentally does — show text, play pixels,
fill, and go dark. Anything generative (rainbow gradients, Game of Life) is
*content*, not core, and lives in a connector that renders frames and pushes
them like any other event. See connectors/boxdemo.
"""

from typing import Protocol

from .font import GLYPH_HEIGHT, text_width
from .frame import RGB, Frame


class Scene(Protocol):
    """Anything the engine can render. Implement structurally, no base class."""

    name: str

    def render(self, frame: Frame, t: float) -> None:
        """Draw one frame. `t` is seconds since the scene became active."""
        ...


class BlankScene:
    """Nothing at all — what the display shows after a clear."""

    name = "blank"

    def render(self, frame: Frame, t: float) -> None:
        frame.clear()


class TextScene:
    """Text, centred when it fits and smoothly scrolled when it doesn't.

    Scrolling is the fix for the long-weather-string bug: '22C FOGGY' is 53px
    wide and simply cannot fit a 32px panel, so it has to move to be readable.
    """

    name = "text"

    #: Pixels per second for the marquee. Slow enough to read on a small panel.
    SPEED = 9.0
    #: Blank pixels between the end of the text and the start of its repeat.
    GAP = 8
    #: Seconds to hold at the start before scrolling, so the text can be read.
    HOLD = 1.2

    def __init__(self, text: str, color: RGB) -> None:
        self.text = text
        self.color = color

    def render(self, frame: Frame, t: float) -> None:
        frame.clear()
        if not self.text:
            return

        y = (frame.height - GLYPH_HEIGHT) // 2
        width = text_width(self.text)

        if width <= frame.width:
            frame.draw_text(self.text, (frame.width - width) // 2, y, self.color)
            return

        period = width + self.GAP
        offset = max(0.0, t - self.HOLD) * self.SPEED % period
        # Draw the text twice so the tail and the wrapped head are both visible.
        frame.draw_text(self.text, -offset, y, self.color)
        frame.draw_text(self.text, period - offset, y, self.color)


class FramesScene:
    """Plays a pre-rendered animation from a flat RGB buffer.

    The sender does the decoding, so this only has to index into bytes and
    copy — cheap enough for a Pi even at 64x64. If the upload's dimensions do
    not match the panel it is nearest-neighbour scaled through precomputed
    index tables, so a connector that guesses wrong still gets something
    sensible instead of an error.
    """

    name = "frames"

    def __init__(
        self,
        data: bytes,
        width: int,
        height: int,
        fps: float = 12.0,
        loop: bool = True,
    ) -> None:
        stride = width * height * 3
        if stride <= 0 or len(data) % stride:
            raise ValueError("data is not a whole number of frames")
        self._data = data
        self._src_w = width
        self._src_h = height
        self._stride = stride
        self.count = len(data) // stride
        self.fps = max(fps, 0.1)
        self.loop = loop
        # Rebuilt lazily, since the panel size is only known at render time.
        self._map: list[int] | None = None
        self._map_for: tuple[int, int] | None = None

    def _index_map(self, w: int, h: int) -> list[int] | None:
        """Byte offsets into one source frame for each destination pixel."""
        if (w, h) == (self._src_w, self._src_h):
            return None  # Exact match: copy the frame wholesale.
        if self._map_for != (w, h):
            sx = [min(self._src_w - 1, x * self._src_w // w) for x in range(w)]
            sy = [min(self._src_h - 1, y * self._src_h // h) for y in range(h)]
            self._map = [(row * self._src_w + col) * 3 for row in sy for col in sx]
            self._map_for = (w, h)
        return self._map

    def render(self, frame: Frame, t: float) -> None:
        index = int(t * self.fps)
        if index >= self.count:
            if not self.loop:
                index = self.count - 1
            else:
                index %= self.count
        offset = index * self._stride

        mapping = self._index_map(frame.width, frame.height)
        if mapping is None:
            frame.buf[:] = self._data[offset : offset + self._stride]
            return

        data = self._data
        buf = frame.buf
        out = 0
        for src in mapping:
            i = offset + src
            buf[out : out + 3] = data[i : i + 3]
            out += 3

    def finished(self, t: float) -> bool:
        """True once a non-looping animation has played through."""
        return not self.loop and t * self.fps >= self.count


class SolidScene:
    """A single flat colour across the whole panel."""

    name = "solid"

    def __init__(self, color: RGB) -> None:
        self.color = color

    def render(self, frame: Frame, t: float) -> None:
        frame.clear(self.color)


__all__ = [
    "BlankScene",
    "FramesScene",
    "Scene",
    "SolidScene",
    "TextScene",
]
