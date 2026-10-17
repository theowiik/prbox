"""Game of Life: the automaton rules the `life` visual renders from."""

import pytest

from box.visuals.life import next_generation, population, random_board


def board(rows: list[str]) -> tuple[bytearray, int, int]:
    """Build a board from '#'/'.' art. Returns (cells, width, height)."""
    height = len(rows)
    width = len(rows[0])
    assert all(len(r) == width for r in rows), "ragged board"
    cells = bytearray(1 if c == "#" else 0 for row in rows for c in row)
    return cells, width, height


def art(cells: bytearray, width: int, height: int) -> list[str]:
    return [
        "".join("#" if cells[y * width + x] else "." for x in range(width))
        for y in range(height)
    ]


# -- rules -----------------------------------------------------------------


def test_blinker_oscillates_with_period_two():
    cells, w, h = board([".....", "..#..", "..#..", "..#..", "....."])
    first = next_generation(cells, w, h)
    assert art(first, w, h)[2] == ".###."
    assert next_generation(first, w, h) == cells


def test_block_is_a_still_life():
    cells, w, h = board(["....", ".##.", ".##.", "...."])
    assert next_generation(cells, w, h) == cells


def test_glider_translates_diagonally_every_four_generations():
    cells, w, h = board(
        [
            ".#........",
            "..#.......",
            "###.......",
            "..........",
            "..........",
            "..........",
            "..........",
            "..........",
        ]
    )
    moved = cells
    for _ in range(4):
        moved = next_generation(moved, w, h)

    expected = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            if cells[y * w + x]:
                expected[((y + 1) % h) * w + (x + 1) % w] = 1
    assert moved == expected


def test_grid_wraps_at_the_edges():
    """A blinker straddling the top/bottom edge must still oscillate."""
    cells, w, h = board(["..#..", ".....", ".....", ".....", "..#.."])
    # Three cells in a vertical line through the wrap: rows 4, 0, 1.
    cells[1 * w + 2] = 1
    assert art(next_generation(cells, w, h), w, h)[0] == ".###."


def test_lonely_cell_dies():
    cells, w, h = board(["...", ".#.", "..."])
    assert population(next_generation(cells, w, h)) == 0


def test_overcrowded_cell_dies():
    cells, w, h = board(["###", "###", "###"])
    # The centre has eight neighbours and must not survive.
    assert next_generation(cells, w, h)[1 * w + 1] == 0


def test_random_board_respects_density_and_seed():
    import random

    a = random_board(32, 32, 0.35, random.Random(1))
    b = random_board(32, 32, 0.35, random.Random(1))
    assert a == b, "same seed must give the same board"
    assert 0.25 < population(a) / len(a) < 0.45


@pytest.mark.parametrize("density", [0.0, 1.0])
def test_random_board_handles_extreme_density(density):
    import random

    cells = random_board(8, 8, density, random.Random(0))
    assert population(cells) == (64 if density == 1.0 else 0)


def test_random_board_is_deterministic():
    import random

    a = random_board(16, 16, 0.4, random.Random(5))
    b = random_board(16, 16, 0.4, random.Random(5))
    assert a == b
