"""Conway's Game of Life — the automaton itself, with no rendering in it.

Kept separate from the scene that draws it so the rules can be tested against
known patterns (gliders, blinkers, still lifes) without a Frame in sight.

The grid is a toroid: the left edge neighbours the right, the top the bottom.
Bounded grids kill anything that drifts into a wall, which on a panel this
small means gliders die within seconds; wrapping lets them run forever.
"""

import random

#: Live neighbour counts that produce a live cell next generation.
_BIRTH = 3
_SURVIVE = (2, 3)


def random_board(
    width: int, height: int, density: float, rng: random.Random
) -> bytearray:
    """A board seeded with roughly `density` live cells."""
    density = min(max(density, 0.0), 1.0)
    return bytearray(1 if rng.random() < density else 0 for _ in range(width * height))


def next_generation(cells: bytearray, width: int, height: int) -> bytearray:
    """One tick of Life on a toroidal grid.

    Neighbour offsets are resolved through precomputed wrap tables rather than
    a modulo per neighbour per cell — that is 8 modulos per cell per generation
    on the hot path, which a Raspberry Pi notices.
    """
    left = [(x - 1) % width for x in range(width)]
    right = [(x + 1) % width for x in range(width)]
    up = [((y - 1) % height) * width for y in range(height)]
    down = [((y + 1) % height) * width for y in range(height)]

    nxt = bytearray(width * height)
    for y in range(height):
        row = y * width
        row_up = up[y]
        row_down = down[y]
        for x in range(width):
            xl = left[x]
            xr = right[x]
            neighbours = (
                cells[row_up + xl]
                + cells[row_up + x]
                + cells[row_up + xr]
                + cells[row + xl]
                + cells[row + xr]
                + cells[row_down + xl]
                + cells[row_down + x]
                + cells[row_down + xr]
            )
            if neighbours == _BIRTH or (cells[row + x] and neighbours in _SURVIVE):
                nxt[row + x] = 1
    return nxt


def population(cells: bytearray) -> int:
    return sum(cells)
