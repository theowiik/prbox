"""Frame generation: shape, determinism, and that each visual actually moves."""

import pytest

from boxdemo.canvas import Canvas, hsv_to_rgb
from boxdemo.noise import ValueNoise
from boxdemo.scenes import gradient_frames, life_frames, rainbow_frames

W = H = 16
STRIDE = W * H * 3


def split(data: bytes) -> list[bytes]:
    return [data[i : i + STRIDE] for i in range(0, len(data), STRIDE)]


# -- canvas ----------------------------------------------------------------


def test_hsv_primaries():
    assert hsv_to_rgb(0.0, 1.0, 1.0) == (255, 0, 0)
    assert hsv_to_rgb(1 / 3, 1.0, 1.0) == (0, 255, 0)
    assert hsv_to_rgb(2 / 3, 1.0, 1.0) == (0, 0, 255)


def test_hsv_hue_wraps():
    assert hsv_to_rgb(1.25, 1.0, 1.0) == hsv_to_rgb(0.25, 1.0, 1.0)


def test_canvas_ignores_out_of_bounds():
    c = Canvas(2, 2)
    c.set_px(-1, 0, (255, 255, 255))
    c.set_px(0, 9, (255, 255, 255))
    assert not any(c.buf)


# -- noise -----------------------------------------------------------------


def test_noise_is_smooth_and_bounded():
    noise = ValueNoise(seed=42)
    values = [noise(x * 0.1, 0.0, 0.0) for x in range(200)]
    assert all(0.0 <= v <= 1.0 for v in values)
    assert max(abs(b - a) for a, b in zip(values, values[1:], strict=False)) < 0.4


# -- shape -----------------------------------------------------------------


@pytest.mark.parametrize("count", [1, 5, 30])
def test_every_visual_emits_exactly_count_frames(count):
    for data in (
        rainbow_frames(W, H, count, 12.0, seed=1),
        life_frames(W, H, count, seed=1),
        gradient_frames(W, H, count),
    ):
        assert len(data) == count * STRIDE


def test_non_square_panels_work():
    assert len(rainbow_frames(32, 8, 3, 12.0, seed=1)) == 3 * 32 * 8 * 3
    assert len(life_frames(32, 8, 3, seed=1)) == 3 * 32 * 8 * 3


# -- behaviour -------------------------------------------------------------


def test_rainbow_animates():
    frames = split(rainbow_frames(W, H, 6, 12.0, seed=5))
    assert len(set(frames)) == 6, "every frame should differ"


def test_rainbow_is_colourful():
    frame = split(rainbow_frames(W, H, 1, 12.0, seed=5))[0]
    assert len(set(frame)) > 20, "should span many values, not one flat colour"


def test_rainbow_is_deterministic_for_a_seed():
    assert rainbow_frames(W, H, 3, 12.0, seed=7) == rainbow_frames(
        W, H, 3, 12.0, seed=7
    )


def test_rainbow_with_no_blobs_still_renders():
    assert any(rainbow_frames(W, H, 1, 12.0, blobs=0, seed=1))


def test_life_evolves():
    frames = split(life_frames(W, H, 8, seed=11))
    assert len(set(frames)) > 1, "generations must differ"


def test_life_is_deterministic_for_a_seed():
    assert life_frames(W, H, 5, seed=3) == life_frames(W, H, 5, seed=3)


def test_life_never_goes_permanently_dark():
    """Extinction and stagnation reseed, so no frame in a long run is blank."""
    frames = split(life_frames(W, H, 400, seed=2))
    blank = [i for i, f in enumerate(frames) if not any(f)]
    assert not blank, f"frames {blank[:5]} were empty"


def test_gradient_covers_the_hue_wheel():
    frame = split(gradient_frames(W, H, 1))[0]
    row = [tuple(frame[i * 3 : i * 3 + 3]) for i in range(W)]
    assert len(set(row)) == W, "each column should be a different hue"
