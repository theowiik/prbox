"""Scenes: things that can draw themselves into a Frame over time."""

import math
import random
from collections import deque
from functools import lru_cache
from typing import Protocol

from .font import GLYPH_HEIGHT, text_width
from .frame import RGB, Frame, hsv_to_rgb
from .life import next_generation, population, random_board
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
        # Size blobs off the short edge so they stay on-panel at any aspect
        # ratio; distances stay Euclidean, so blobs are round like the LEDs.
        short_edge = w if w < h else h
        centres = [
            (
                (0.5 + 0.42 * math.sin(t * fx * 6.283 + px)) * w,
                (0.5 + 0.42 * math.cos(t * fy * 6.283 + py)) * h,
                (radius * short_edge) ** 2,
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
                    dy = y - cy
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


#: Generations a cell is tracked for before its colour stops shifting.
_MAX_AGE = 24
#: Quantisation of the birth/death fade. 16 steps is smoother than LEDs resolve.
_LIFE_LEVELS = 16


class LifeScene:
    """Conway's Game of Life, rendered with age colouring and soft transitions.

    Life is stateful, unlike every other scene here, but it still presents the
    same pure `render(frame, t)` interface: the generation number is derived
    from `t`, and rewinding `t` replays deterministically from the seed. That
    keeps it testable at arbitrary `t` and keeps the engine ignorant of the
    difference.

    Generations tick a few times a second, far slower than the 30fps render
    loop, so cells fade in as they are born and fade out as they die. Without
    that the panel would visibly stutter between discrete states.
    """

    name = "life"

    #: Board hashes remembered when looking for a stalled simulation.
    HISTORY = 24
    #: Cap on generations simulated in one render, so a huge jump in `t` cannot
    #: stall the loop. Mirrors the engine's own resync-instead-of-catch-up rule.
    MAX_CATCHUP = 128

    def __init__(
        self,
        speed: float = 6.0,
        density: float = 0.35,
        hue: float = 0.45,
        hue_span: float = 0.35,
        seed: int | None = None,
    ) -> None:
        self.speed = max(speed, 0.1)
        self.density = min(max(density, 0.01), 0.95)
        self.seed = seed

        # Colour by age: newly born cells start at `hue`, long-lived colonies
        # drift across `hue_span`, so structure is readable at a glance.
        self._lut = [
            bytes(
                hsv_to_rgb(
                    hue + hue_span * (age / _MAX_AGE),
                    0.85,
                    level / (_LIFE_LEVELS - 1),
                )
            )
            for age in range(_MAX_AGE + 1)
            for level in range(_LIFE_LEVELS)
        ]

        self._w = 0
        self._h = 0
        self._generation = 0
        self._reseeds = 0

    # -- simulation --------------------------------------------------------

    def _reset(self, width: int, height: int) -> None:
        """Restart from the scene's seed, so replaying `t` is deterministic."""
        self._w = width
        self._h = height
        self._rng = random.Random(self.seed)
        self._cells = random_board(width, height, self.density, self._rng)
        self._age = bytearray(self._cells)
        # The starting board counts as already established, so generation 0 is
        # visible immediately. Fading it up from black would leave the panel
        # dark at t=0, and the engine already crossfades scene entry anyway.
        self._prev = bytearray(self._cells)
        self._prev_age = bytearray(self._age)
        self._history: deque[int] = deque(maxlen=self.HISTORY)
        self._generation = 0

    def _reseed(self) -> None:
        """Drop a fresh random board in when the simulation stops being interesting.

        Small boards reach a still life, a short oscillator or extinction within
        a minute or so. Left alone the panel would just freeze, so a stalled
        board is replaced. The RNG stream continues rather than restarting, so a
        replay from `_reset` reproduces the same reseeds.
        """
        self._cells = random_board(self._w, self._h, self.density, self._rng)
        self._age = bytearray(self._cells)
        self._history.clear()
        self._reseeds += 1

    def _advance(self) -> None:
        """Step one generation, tracking cell ages and watching for stagnation."""
        self._prev = self._cells
        self._prev_age = self._age

        cells = next_generation(self._cells, self._w, self._h)
        age = bytearray(len(cells))
        old_age = self._age
        for i, alive in enumerate(cells):
            if alive:
                a = old_age[i]
                age[i] = a + 1 if a < _MAX_AGE else _MAX_AGE
        self._cells = cells
        self._age = age

        if not population(cells):
            self._reseed()
            return
        # A board state we have seen recently means a still life or a short
        # oscillator — the pattern is finished evolving.
        state = hash(bytes(cells))
        if state in self._history:
            self._reseed()
        else:
            self._history.append(state)

    # -- rendering ---------------------------------------------------------

    def render(self, frame: Frame, t: float) -> None:
        if frame.width != self._w or frame.height != self._h:
            self._reset(frame.width, frame.height)

        exact = t * self.speed if t > 0.0 else 0.0
        target = int(exact)

        if target < self._generation:
            # `t` went backwards (a test, or a scene restart) — replay.
            self._reset(self._w, self._h)
        steps = target - self._generation
        if steps > self.MAX_CATCHUP:
            self._reset(self._w, self._h)
            steps = self.MAX_CATCHUP
        for _ in range(steps):
            self._advance()
        self._generation = target

        self._paint(frame, exact - target)

    def _paint(self, frame: Frame, frac: float) -> None:
        """Draw the board, crossfading births and deaths across the generation."""
        buf = frame.buf
        cells = self._cells
        prev = self._prev
        age = self._age
        prev_age = self._prev_age
        lut = self._lut
        top = _LIFE_LEVELS - 1
        born = int(frac * top)
        dying = top - born

        i = 0
        for idx, alive in enumerate(cells):
            was = prev[idx]
            if alive:
                # Established cells stay lit; newborns fade up over the tick.
                level = top if was else born
                cell_age = age[idx]
            elif was:
                level = dying
                cell_age = prev_age[idx]
            else:
                buf[i] = buf[i + 1] = buf[i + 2] = 0
                i += 3
                continue
            buf[i : i + 3] = lut[cell_age * _LIFE_LEVELS + level]
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
    "LifeScene",
    "RainbowScene",
    "Scene",
    "SolidScene",
    "TextScene",
]
