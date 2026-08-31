"""Game of Life: the automaton rules, then the scene that draws them."""

import pytest

from prbox.render.frame import Frame
from prbox.render.life import next_generation, population, random_board
from prbox.render.scenes import LifeScene


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


# -- scene -----------------------------------------------------------------


def test_scene_draws_live_cells():
    frame = Frame(32, 32)
    LifeScene(seed=1).render(frame, 0.0)
    assert any(frame.buf), "a seeded board should light some pixels"


def test_scene_advances_with_time():
    scene = LifeScene(speed=6.0, seed=1)
    frame = Frame(32, 32)

    scene.render(frame, 0.0)
    assert scene._generation == 0
    scene.render(frame, 1.0)
    assert scene._generation == 6, "6 generations/second"


def test_scene_is_deterministic_for_a_seed():
    a, b = Frame(32, 32), Frame(32, 32)
    LifeScene(seed=7).render(a, 2.0)
    LifeScene(seed=7).render(b, 2.0)
    assert bytes(a.buf) == bytes(b.buf)


def test_rewinding_time_replays_identically():
    """`t` going backwards must reproduce the earlier frame exactly."""
    scene = LifeScene(seed=3)
    early, late, again = Frame(32, 32), Frame(32, 32), Frame(32, 32)

    scene.render(early, 0.5)
    scene.render(late, 5.0)
    scene.render(again, 0.5)
    assert bytes(again.buf) == bytes(early.buf)
    assert bytes(late.buf) != bytes(early.buf)


def test_births_fade_in_across_a_generation():
    """Mid-tick, a newborn cell must be dimmer than an established one."""
    scene = LifeScene(speed=1.0, seed=5)
    frame = Frame(32, 32)
    scene.render(frame, 1.0)  # Land exactly on a generation boundary.

    established = {i for i, v in enumerate(scene._cells) if v and scene._prev[i]}
    newborn = {i for i, v in enumerate(scene._cells) if v and not scene._prev[i]}
    assert established and newborn, "need both kinds of cell for this test"

    scene.render(frame, 1.25)  # A quarter of the way into the next generation.
    i = next(iter(newborn))
    j = next(iter(established))
    assert sum(frame.buf[i * 3 : i * 3 + 3]) < sum(frame.buf[j * 3 : j * 3 + 3])


def test_extinction_triggers_a_reseed():
    """An empty board must not leave the panel dark forever."""
    scene = LifeScene(seed=1)
    frame = Frame(32, 32)
    scene.render(frame, 0.0)

    scene._cells = bytearray(len(scene._cells))  # Kill everything.
    scene._advance()
    assert population(scene._cells) > 0
    assert scene._reseeds == 1


def test_stagnation_triggers_a_reseed():
    """A still life is finished evolving, so it must be replaced."""
    scene = LifeScene(seed=1)
    frame = Frame(16, 16)
    scene.render(frame, 0.0)

    # A single block: stable forever, so the second sighting is stagnation.
    scene._cells = bytearray(16 * 16)
    for y, x in ((4, 4), (4, 5), (5, 4), (5, 5)):
        scene._cells[y * 16 + x] = 1
    scene._history.clear()

    scene._advance()
    scene._advance()
    assert scene._reseeds == 1


def test_resizing_the_panel_restarts_the_board():
    scene = LifeScene(seed=1)
    scene.render(Frame(32, 32), 0.0)
    assert (scene._w, scene._h) == (32, 32)

    scene.render(Frame(16, 8), 0.0)
    assert (scene._w, scene._h) == (16, 8)
    assert len(scene._cells) == 16 * 8


def test_huge_time_jump_does_not_hang():
    """A large `t` resyncs instead of simulating every skipped generation."""
    scene = LifeScene(speed=30.0, seed=1)
    frame = Frame(32, 32)
    scene.render(frame, 100_000.0)
    assert scene._generation == int(100_000.0 * 30.0)
    assert any(frame.buf)


def test_scene_survives_a_long_run():
    """Reseeding must keep the panel alive over many generations."""
    scene = LifeScene(speed=10.0, seed=2)
    frame = Frame(32, 32)
    for step in range(1, 60):
        scene.render(frame, step * 0.5)
        assert any(frame.buf), f"panel went dark at t={step * 0.5}"


# -- API -------------------------------------------------------------------


def test_life_endpoint(client):
    assert client.post("/api/display/life", json={}).status_code == 200
    assert client.get("/api/display").json()["scene"] == "life"


def test_life_endpoint_accepts_parameters(client):
    response = client.post(
        "/api/display/life", json={"speed": 12.0, "density": 0.5, "hue": 0.1}
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    "payload",
    [{"speed": 0.1}, {"speed": 100}, {"density": 0.0}, {"density": 1.5}, {"hue": 2.0}],
)
def test_life_endpoint_rejects_out_of_range(client, payload):
    assert client.post("/api/display/life", json=payload).status_code == 422
