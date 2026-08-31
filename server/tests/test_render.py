import pytest

from prbox.render.font import ADVANCE, GLYPH_HEIGHT, text_width
from prbox.render.frame import Frame, hex_to_rgb, hsv_to_rgb, rgb_to_hex
from prbox.render.noise import ValueNoise
from prbox.render.scenes import BlankScene, RainbowScene, SolidScene, TextScene


def lit_columns(frame: Frame) -> set[int]:
    """Columns containing at least one non-black pixel."""
    return {
        x
        for y in range(frame.height)
        for x in range(frame.width)
        if any(frame.buf[(y * frame.width + x) * 3 + c] for c in range(3))
    }


def test_hex_roundtrip():
    assert hex_to_rgb("#FF8800") == (255, 136, 0)
    assert hex_to_rgb("f80") == (255, 136, 0)
    assert rgb_to_hex((255, 136, 0)) == "#FF8800"


@pytest.mark.parametrize("bad", ["", "#12345", "zzzzzz", "#GGGGGG"])
def test_hex_rejects_garbage(bad):
    with pytest.raises(ValueError):
        hex_to_rgb(bad)


def test_hsv_primaries():
    assert hsv_to_rgb(0.0, 1.0, 1.0) == (255, 0, 0)
    assert hsv_to_rgb(1 / 3, 1.0, 1.0) == (0, 255, 0)
    assert hsv_to_rgb(2 / 3, 1.0, 1.0) == (0, 0, 255)
    assert hsv_to_rgb(0.5, 0.0, 0.0) == (0, 0, 0)


def test_hsv_hue_wraps():
    assert hsv_to_rgb(1.25, 1.0, 1.0) == hsv_to_rgb(0.25, 1.0, 1.0)


def test_frame_clear_and_set():
    f = Frame(4, 2)
    f.set_px(1, 1, (10, 20, 30))
    assert f.buf[(1 * 4 + 1) * 3 : (1 * 4 + 1) * 3 + 3] == bytearray((10, 20, 30))
    f.clear()
    assert not any(f.buf)


def test_frame_ignores_out_of_bounds():
    f = Frame(2, 2)
    f.set_px(-1, 0, (255, 255, 255))
    f.set_px(0, 9, (255, 255, 255))
    assert not any(f.buf)


def test_draw_text_stays_in_bounds():
    f = Frame(8, 8)
    f.draw_text("ABCDEFGHIJ", -3.5, 0, (255, 255, 255))
    assert len(f.buf) == 8 * 8 * 3  # No overflow into neighbouring rows.


def test_short_text_is_centred_and_static():
    scene = TextScene("HI", (0, 255, 0))
    f = Frame(32, 8)
    scene.render(f, 0.0)
    at_zero = bytes(f.buf)
    scene.render(f, 5.0)
    assert bytes(f.buf) == at_zero, "text that fits must not scroll"

    cols = lit_columns(f)
    left, right = min(cols), 31 - max(cols)
    # Glyphs have uneven ink within their 5px cell, so allow a little slack.
    assert abs(left - right) <= 2


def test_long_text_scrolls():
    """The bug: '22°C FOGGY' is wider than a 32px panel and used to be cut off."""
    text = "22°C FOGGY"
    assert text_width(text) > 32

    scene = TextScene(text, (255, 255, 255))
    f = Frame(32, 8)

    scene.render(f, 0.0)
    first = bytes(f.buf)
    # Past the initial hold, the frame must actually move.
    scene.render(f, TextScene.HOLD + 1.0)
    assert bytes(f.buf) != first


def test_long_text_eventually_shows_its_tail():
    """The tail of an overflowing string must actually reach the panel."""
    text = "22°C FOGGY"
    scene = TextScene(text, (255, 255, 255))
    f = Frame(32, 8)

    # Scroll until the final glyph sits one pixel in from the left edge.
    target_x = 1.0
    offset = (len(text) - 1) * ADVANCE - target_x
    scene.render(f, TextScene.HOLD + offset / TextScene.SPEED)

    reference = Frame(32, 8)
    reference.draw_text(text[-1], target_x, (8 - GLYPH_HEIGHT) // 2, (255, 255, 255))
    assert lit_columns(reference) <= lit_columns(f)


def test_text_vertically_centred():
    f = Frame(32, 16)
    TextScene("HI", (255, 255, 255)).render(f, 0.0)
    rows = {
        y
        for y in range(f.height)
        for x in range(f.width)
        if any(f.buf[(y * f.width + x) * 3 + c] for c in range(3))
    }
    assert min(rows) >= (16 - GLYPH_HEIGHT) // 2


def test_blank_scene_is_black():
    f = Frame(8, 8)
    f.clear((9, 9, 9))
    BlankScene().render(f, 1.0)
    assert not any(f.buf)


def test_solid_scene_fills():
    f = Frame(4, 4)
    SolidScene((1, 2, 3)).render(f, 0.0)
    assert bytes(f.buf) == bytes((1, 2, 3)) * 16


def test_rainbow_is_colourful_and_animates():
    f = Frame(32, 8)
    scene = RainbowScene(seed=7)

    scene.render(f, 0.0)
    first = bytes(f.buf)
    scene.render(f, 3.0)
    second = bytes(f.buf)

    assert first != second, "rainbow must animate over time"
    assert len(set(first)) > 8, "rainbow should span many values, not one flat colour"


def test_rainbow_is_deterministic_for_a_seed():
    a, b = Frame(16, 8), Frame(16, 8)
    RainbowScene(seed=3).render(a, 1.5)
    RainbowScene(seed=3).render(b, 1.5)
    assert bytes(a.buf) == bytes(b.buf)


def test_rainbow_with_no_blobs_still_renders():
    f = Frame(16, 8)
    RainbowScene(blobs=0, seed=1).render(f, 0.5)
    assert any(f.buf)


def test_noise_in_range_and_smooth():
    noise = ValueNoise(seed=42)
    values = [noise(x * 0.1, 0.0, 0.0) for x in range(200)]
    assert all(0.0 <= v <= 1.0 for v in values)
    # Neighbouring samples must be close, or it is white noise, not value noise.
    assert max(abs(b - a) for a, b in zip(values, values[1:], strict=False)) < 0.4


def test_noise_is_deterministic():
    assert ValueNoise(seed=1)(1.5, 2.5, 3.5) == ValueNoise(seed=1)(1.5, 2.5, 3.5)


def test_fbm_in_range():
    noise = ValueNoise(seed=9)
    assert all(
        0.0 <= noise.fbm(i * 0.3, i * 0.7, i * 0.2, octaves=3) <= 1.0 for i in range(50)
    )


@pytest.mark.parametrize(("w", "h"), [(32, 32), (64, 32), (32, 8)])
def test_rainbow_blobs_are_round_at_any_aspect_ratio(w, h):
    """Blobs must not stretch on non-square panels — LEDs are square pixels.

    Rendering at saturation 0 makes every pixel grey, so the red channel is a
    direct readout of the blob field with the hue gradient factored out.
    """
    frame = Frame(w, h)
    RainbowScene(blobs=1, noise_amount=0.0, saturation=0.0, seed=4).render(frame, 0.0)

    values = [frame.buf[(y * w + x) * 3] for y in range(h) for x in range(w)]
    peak = max(values)
    core = [
        (x, y) for y in range(h) for x in range(w) if values[y * w + x] > peak * 0.9
    ]
    assert core, "blob should have a bright core"

    xs = [p[0] for p in core]
    ys = [p[1] for p in core]
    width = max(xs) - min(xs) + 1
    height = max(ys) - min(ys) + 1
    assert abs(width - height) <= 1, f"blob is {width}x{height}, not round"


def test_rainbow_blobs_fit_within_a_short_panel():
    """Blob radius keys off the short edge, so it cannot exceed panel height."""
    scene = RainbowScene(blobs=4, seed=2)
    # Largest radius fraction the constructor can produce is 0.18 + 0.22.
    assert max(b[4] for b in scene._blobs) <= 0.40
