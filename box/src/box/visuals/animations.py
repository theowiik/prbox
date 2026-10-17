"""The generators behind the built-in visuals.

Each one renders a whole animation to a flat RGB buffer up front, which the
box then plays through `FramesScene`. Generating is the expensive part — the
rainbow takes seconds on a Pi — so it happens once, on a worker thread, and is
cached (see `visuals/__init__.py`). The render loop only ever copies bytes.
"""

import math
import random
from functools import lru_cache

from ..render.frame import RGB, Frame
from .color import hsv_to_rgb
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
    canvas = Frame(width, height)
    out = bytearray()
    for index in range(count):
        phase = index / count
        for y in range(height):
            for x in range(width):
                canvas.set_px(x, y, hsv_to_rgb(x / width + phase, saturation, 1.0))
        out += bytes(canvas.buf)
    return bytes(out)


#: Beer palette. Amber deepens towards the bottom of the glass, like the real
#: thing seen through more liquid.
_BEER_TOP = (255, 186, 32)
_BEER_BOTTOM = (176, 92, 0)
_FOAM = (255, 244, 218)
_FOAM_SHADE = (226, 212, 180)
_BUBBLE = (255, 222, 130)
_GLASS = (64, 80, 96)
_GLASS_SHINE = (120, 140, 160)


def _mix(a: RGB, b: RGB, t: float) -> RGB:
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def beer_frames(width: int, height: int, fps: float = 20.0) -> bytes:
    """A pint glass being poured: stream, rising beer and foam, then bubbles.

    Plays once — the last frame is a full glass, which is what the panel
    should rest on. Geometry scales from a 32x32 design to any panel.
    """
    s = min(width, height) / 32
    cx = width / 2
    top, bottom = round(height / 2 - 12 * s), round(height / 2 + 12 * s)
    top_hw, bottom_hw = 8.5 * s, 6.0 * s
    base = max(1, round(1.5 * s))  # thick glass bottom
    foam_max = max(2, round(3 * s))

    # Inner extent of the glass per row: (left, right) inclusive, or None.
    walls: dict[int, tuple[int, int]] = {}
    for y in range(top, bottom + 1):
        frac = (y - top) / max(bottom - top, 1)
        hw = top_hw + (bottom_hw - top_hw) * frac
        walls[y] = (round(cx - hw), round(cx + hw) - 1)
    floor = bottom - base  # lowest row liquid can occupy
    # Where the top of the head sits when full: one row proud of the rim, so
    # the foam domes over it the way a well-poured pint does.
    full = top - 1

    # Timeline, in seconds: stream falls in, glass fills, stream stops, rest.
    t_drop, t_fill, t_stop, t_rest = 0.35, 3.2, 0.3, 1.6
    count = round((t_drop + t_fill + t_stop + t_rest) * fps)
    rng = random.Random(7)
    bubbles = [
        [rng.uniform(0, 1), rng.uniform(0, 1), rng.uniform(4, 9) * s]
        for _ in range(max(4, round(9 * s * s)))
    ]

    out = bytearray()
    for index in range(count):
        t = index / fps
        canvas = Frame(width, height)

        # How full, 0..1, eased out: a pour slows as the glass tops up.
        p = min(max((t - t_drop) / t_fill, 0.0), 1.0)
        level = 1 - (1 - p) ** 2
        # Float row of the top; floor + 1 is an empty glass.
        surface = floor + 1 - (floor + 1 - full) * level
        foam = foam_max * min(1.0, level * 1.6) if level > 0 else 0.0

        # Liquid and foam, inside the walls (and the dome above the rim).
        for y in range(top - 1, floor + 1):
            # Coverage of this row: 1 below the surface, partial at it.
            cover = min(1.0, y + 1 - surface)
            if cover <= 0:
                continue
            if y < top:  # the dome: narrower than the rim, foam only
                left, right = walls[top][0] + 1, walls[top][1] - 1
            else:
                left, right = walls[y]
            in_head = y < surface + foam
            for x in range(left + 1, right):
                if in_head:
                    color = _FOAM_SHADE if (x * 7 + y * 3) % 5 == 0 else _FOAM
                else:
                    shade = (y - top) / max(floor - top, 1)
                    color = _mix(_BEER_TOP, _BEER_BOTTOM, shade)
                if cover < 1:
                    color = _mix((0, 0, 0), color, cover)
                canvas.set_px(x, y, color)

        # Bubbles drift up through the beer below the foam.
        if level > 0.15:
            for bubble in bubbles:
                bx, by, speed = bubble
                y = floor - ((by * (floor - surface)) + t * speed) % max(
                    floor - surface - foam, 1
                )
                left, right = walls[int(y)] if int(y) in walls else (0, 0)
                x = left + 1 + int(bx * max(right - left - 1, 1))
                if surface + foam + 1 <= y <= floor and left < x < right:
                    canvas.set_px(x, int(y), _BUBBLE)

        # The pour: a stream from the top edge down to the surface.
        t_end = t_drop + t_fill
        head = min(1.0, t / t_drop) * (surface - 0)  # falling in
        tail = max(0.0, (t - t_end) / t_stop) * surface  # falling away
        if t < t_end + t_stop:
            sx = int(cx) - 1 if s < 1.5 else int(cx)
            for y in range(int(tail), int(head)):
                canvas.set_px(sx, y, _BEER_TOP)
                if s >= 1.5:
                    canvas.set_px(sx - 1, y, _BEER_TOP)

        # The glass last, so it reads in front of the beer.
        for y, (left, right) in walls.items():
            canvas.set_px(left, y, _GLASS)
            canvas.set_px(right, y, _GLASS)
            if y > floor:
                for x in range(left, right + 1):
                    canvas.set_px(x, y, _GLASS)
        # A faint reflection down one side: tints what is behind it rather than
        # replacing it, so it never reads as a bubble.
        for y in range(top + 2, top + 2 + round(8 * s)):
            i = (y * width + walls[y][0] + 1) * 3
            under = tuple(canvas.buf[i : i + 3])
            canvas.set_px(walls[y][0] + 1, y, _mix(under, _GLASS_SHINE, 0.45))

        out += bytes(canvas.buf)
    return bytes(out)
