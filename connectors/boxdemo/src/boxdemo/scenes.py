"""Generative visuals, rendered to frames locally.

These used to live inside the box. They are content, not core: the box knows
how to play a buffer of RGB frames, and everything here just produces one. That
keeps the box's render path to text and pixels, and means a new visual never
needs a change on the Pi.

Frames are generated ahead of time and uploaded in one go, so nothing has to
keep running afterwards — the box loops the buffer forever on its own.
"""

import math
import random
from functools import lru_cache

from .canvas import Canvas, hsv_to_rgb
from .life import next_generation, population, random_board
from .noise import ValueNoise

#: Palette quantisation. Finer than an LED panel can resolve, and it turns
#: per-pixel HSV maths into an index lookup.
_HUE_STEPS = 256
_VAL_STEPS = 64


@lru_cache(maxsize=8)
def _palette(saturation_q: int) -> list[bytes]:
    saturation = saturation_q / 100.0
    return [
        bytes(hsv_to_rgb(h / _HUE_STEPS, saturation, v / (_VAL_STEPS - 1)))
        for v in range(_VAL_STEPS)
        for h in range(_HUE_STEPS)
    ]


def rainbow_frames(
    width: int,
    height: int,
    count: int,
    fps: float,
    *,
    speed: float = 0.08,
    blobs: int = 4,
    noise_amount: float = 0.25,
    saturation: float = 1.0,
    seed: int | None = None,
) -> bytes:
    """A hue gradient with drifting blobs and a noise wash.

    Blob radius keys off the short edge and distances stay Euclidean, so blobs
    are round on any panel aspect ratio.
    """
    noise = ValueNoise(seed)
    rng = ValueNoise(seed)
    shapes = [
        (
            0.11 + 0.07 * rng(i, 0, 0),
            0.09 + 0.06 * rng(i, 1, 0),
            6.283 * rng(i, 2, 0),
            6.283 * rng(i, 3, 0),
            0.18 + 0.22 * rng(i, 4, 0),
        )
        for i in range(max(0, blobs))
    ]
    palette = _palette(int(round(min(max(saturation, 0.0), 1.0) * 100)))
    short_edge = min(width, height)
    inv_w = 1.0 / width
    inv_h = 1.0 / max(height - 1, 1)
    noise_amount = min(max(noise_amount, 0.0), 1.0)
    stride = 2  # Noise is low-frequency; sample coarsely and interpolate.

    out = bytearray()
    for index in range(count):
        t = index / fps
        centres = [
            (
                (0.5 + 0.42 * math.sin(t * fx * 6.283 + px)) * width,
                (0.5 + 0.42 * math.cos(t * fy * 6.283 + py)) * height,
                (radius * short_edge) ** 2,
            )
            for fx, fy, px, py, radius in shapes
        ]
        cols = width // stride + 2
        grid = [
            noise.fbm(gx * stride * 0.22, gy * stride * 0.35, t * 0.35, octaves=2)
            for gy in range(height // stride + 2)
            for gx in range(cols)
        ]

        frame = bytearray(width * height * 3)
        i = 0
        for y in range(height):
            row_hue = y * inv_h * 0.12 + t * speed
            gy = y / stride
            gy0 = int(gy)
            wy = gy - gy0
            row0 = gy0 * cols
            row1 = row0 + cols
            for x in range(width):
                field = 0.0
                for cx, cy, r2 in centres:
                    dx = x - cx
                    dy = y - cy
                    field += r2 / (dx * dx + dy * dy + r2 * 0.35)

                gx = x / stride
                gx0 = int(gx)
                wx = gx - gx0
                top = grid[row0 + gx0]
                top += (grid[row0 + gx0 + 1] - top) * wx
                bottom = grid[row1 + gx0]
                bottom += (grid[row1 + gx0 + 1] - bottom) * wx
                n = top + (bottom - top) * wy

                hue = (
                    row_hue
                    + x * inv_w * 0.85
                    + field * 0.10
                    + (n - 0.5) * noise_amount * 0.5
                )
                value = 0.35 + 0.5 * (field if field < 1.4 else 1.4) / 1.4
                value *= 1.0 - noise_amount * 0.6 * (1.0 - n)

                h_i = int(hue * _HUE_STEPS) % _HUE_STEPS
                v_i = min(max(int(value * (_VAL_STEPS - 1)), 0), _VAL_STEPS - 1)
                frame[i : i + 3] = palette[v_i * _HUE_STEPS + h_i]
                i += 3
        out += frame
    return bytes(out)


#: Generations a cell is tracked for before its colour stops shifting.
_MAX_AGE = 24


def life_frames(
    width: int,
    height: int,
    count: int,
    *,
    density: float = 0.35,
    hue: float = 0.45,
    hue_span: float = 0.35,
    seed: int | None = None,
) -> bytes:
    """Conway's Game of Life, one rendered frame per generation.

    Small boards reach a still life or die out within a minute, so a board that
    repeats a recent state or goes extinct is reseeded — otherwise the loop
    would freeze partway through.
    """
    rng = random.Random(seed)
    cells = random_board(width, height, density, rng)
    ages = bytearray(cells)
    history: list[int] = []
    colors = [
        bytes(hsv_to_rgb(hue + hue_span * (age / _MAX_AGE), 0.85, 1.0))
        for age in range(_MAX_AGE + 1)
    ]
    black = bytes(3)

    out = bytearray()
    for _ in range(count):
        frame = bytearray(width * height * 3)
        i = 0
        for idx, alive in enumerate(cells):
            frame[i : i + 3] = colors[ages[idx]] if alive else black
            i += 3
        out += frame

        cells = next_generation(cells, width, height)
        new_ages = bytearray(len(cells))
        for idx, alive in enumerate(cells):
            if alive:
                new_ages[idx] = min(ages[idx] + 1, _MAX_AGE)
        ages = new_ages

        state = hash(bytes(cells))
        if not population(cells) or state in history:
            cells = random_board(width, height, density, rng)
            ages = bytearray(cells)
            history.clear()
        else:
            history.append(state)
            if len(history) > 24:
                history.pop(0)
    return bytes(out)


def gradient_frames(
    width: int, height: int, count: int, *, saturation: float = 1.0
) -> bytes:
    """A plain hue sweep — the simplest thing that proves the pipeline works."""
    canvas = Canvas(width, height)
    out = bytearray()
    for index in range(count):
        phase = index / count
        for y in range(height):
            for x in range(width):
                canvas.set_px(x, y, hsv_to_rgb(x / width + phase, saturation, 1.0))
        out += canvas.snapshot()
    return bytes(out)
