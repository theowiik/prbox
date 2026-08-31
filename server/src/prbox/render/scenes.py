"""Scenes: things that can draw themselves into a Frame over time."""

import math
from functools import lru_cache
from typing import Protocol

from .font import GLYPH_HEIGHT, text_width
from .frame import RGB, Frame, hsv_to_rgb
from .noise import ValueNoise


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


#: Quantisation of the precomputed rainbow palette. 256 hues x 64 values is
#: finer than an LED panel can resolve, and turns per-pixel HSV maths into an
#: index lookup — the single biggest win for frame rate on a Pi.
_HUE_STEPS = 256
_VAL_STEPS = 64


@lru_cache(maxsize=8)
def _palette(saturation_q: int) -> list[bytes]:
    """Flat [value * _HUE_STEPS + hue] table of pre-rendered RGB triples."""
    saturation = saturation_q / 100.0
    return [
        bytes(hsv_to_rgb(h / _HUE_STEPS, saturation, v / (_VAL_STEPS - 1)))
        for v in range(_VAL_STEPS)
        for h in range(_HUE_STEPS)
    ]


class RainbowScene:
    """A rainbow gradient with soft drifting blobs and a noise wash.

    The hue sweeps across the panel and over time; metaball-style blobs push the
    hue and brightness around locally, and value noise breaks up the banding so
    it does not read as a flat gradient on real LEDs.

    The inner loop is written for a Raspberry Pi rather than for elegance: the
    palette is a lookup table, noise is sampled on a coarse grid and
    interpolated, and pixels are written as byte slices.
    """

    name = "rainbow"

    #: Noise is low-frequency, so sampling every Nth pixel and interpolating is
    #: visually indistinguishable from sampling every pixel, at a quarter the cost.
    NOISE_STRIDE = 2

    def __init__(
        self,
        speed: float = 0.08,
        blobs: int = 4,
        noise_amount: float = 0.25,
        saturation: float = 1.0,
        seed: int | None = None,
    ) -> None:
        self.speed = speed
        self.blob_count = max(0, blobs)
        self.noise_amount = min(max(noise_amount, 0.0), 1.0)
        self.saturation = min(max(saturation, 0.0), 1.0)
        self._noise = ValueNoise(seed)
        self._palette = _palette(int(round(self.saturation * 100)))

        # Each blob gets its own drift frequencies and phases so the group never
        # settles into a visible repeating pattern.
        rng = ValueNoise(seed)
        self._blobs = [
            (
                0.11 + 0.07 * rng(i, 0, 0),  # x frequency
                0.09 + 0.06 * rng(i, 1, 0),  # y frequency
                6.283 * rng(i, 2, 0),  # x phase
                6.283 * rng(i, 3, 0),  # y phase
                0.18 + 0.22 * rng(i, 4, 0),  # radius, as a fraction of width
            )
            for i in range(self.blob_count)
        ]

    def _noise_grid(self, w: int, h: int, t: float) -> list[float]:
        """fbm sampled on a (stride-spaced) grid, one row-major list per frame."""
        stride = self.NOISE_STRIDE
        cols = w // stride + 2
        rows = h // stride + 2
        z = t * 0.35
        fbm = self._noise.fbm
        return [
            fbm(gx * stride * 0.22, gy * stride * 0.35, z, octaves=2)
            for gy in range(rows)
            for gx in range(cols)
        ]

    def render(self, frame: Frame, t: float) -> None:
        w, h = frame.width, frame.height
        buf = frame.buf
        palette = self._palette
        inv_w = 1.0 / w
        inv_h = 1.0 / max(h - 1, 1)

        # Resolve blob centres once per frame rather than once per pixel.
        centres = [
            (
                (0.5 + 0.42 * math.sin(t * fx * 6.283 + px)) * w,
                (0.5 + 0.42 * math.cos(t * fy * 6.283 + py)) * h,
                (radius * w) ** 2,
            )
            for fx, fy, px, py, radius in self._blobs
        ]

        use_noise = self.noise_amount > 0.0
        if use_noise:
            stride = self.NOISE_STRIDE
            grid = self._noise_grid(w, h, t)
            grid_cols = w // stride + 2
            inv_stride = 1.0 / stride
        hue_base = t * self.speed
        noise_hue = self.noise_amount * 0.5
        noise_dim = self.noise_amount * 0.6

        i = 0
        for y in range(h):
            row_hue = y * inv_h * 0.12 + hue_base
            if use_noise:
                gy = y * inv_stride
                gy0 = int(gy)
                wy = gy - gy0
                row0 = gy0 * grid_cols
                row1 = row0 + grid_cols

            for x in range(w):
                field = 0.0
                for cx, cy, r2 in centres:
                    dx = x - cx
                    dy = (y - cy) * 2.0  # Panels are wide; keep blobs round-ish.
                    field += r2 / (dx * dx + dy * dy + r2 * 0.35)

                if use_noise:
                    gx = x * inv_stride
                    gx0 = int(gx)
                    wx = gx - gx0
                    top = grid[row0 + gx0]
                    top += (grid[row0 + gx0 + 1] - top) * wx
                    bottom = grid[row1 + gx0]
                    bottom += (grid[row1 + gx0 + 1] - bottom) * wx
                    n = top + (bottom - top) * wy
                else:
                    n = 0.5

                hue = row_hue + x * inv_w * 0.85 + field * 0.10 + (n - 0.5) * noise_hue
                # Blobs read as bright cores; the noise keeps the field alive.
                value = 0.35 + 0.5 * (field if field < 1.4 else 1.4) / 1.4
                value *= 1.0 - noise_dim * (1.0 - n)

                h_i = int(hue * _HUE_STEPS) % _HUE_STEPS
                v_i = int(value * (_VAL_STEPS - 1))
                if v_i < 0:
                    v_i = 0
                elif v_i >= _VAL_STEPS:
                    v_i = _VAL_STEPS - 1

                buf[i : i + 3] = palette[v_i * _HUE_STEPS + h_i]
                i += 3


class SolidScene:
    """A single flat colour across the whole panel."""

    name = "solid"

    def __init__(self, color: RGB) -> None:
        self.color = color

    def render(self, frame: Frame, t: float) -> None:
        frame.clear(self.color)


__all__ = [
    "BlankScene",
    "RainbowScene",
    "Scene",
    "SolidScene",
    "TextScene",
]
