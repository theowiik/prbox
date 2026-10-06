import pytest

from box.render import font
from box.render.engine import _gamma_lut
from box.render.font import ADVANCE, GLYPH_HEIGHT, text_width
from box.render.frame import Frame, hex_to_rgb, rgb_to_hex
from box.render.scenes import BlankScene, SolidScene, TextScene


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


# -- FramesScene -----------------------------------------------------------


def solid_frames(colors, w, h):
    """One frame per colour, as a flat RGB buffer."""
    return b"".join(bytes(c) * (w * h) for c in colors)


def test_frames_play_in_order():
    from box.render.scenes import FramesScene

    data = solid_frames([(255, 0, 0), (0, 255, 0), (0, 0, 255)], 4, 4)
    scene = FramesScene(data, 4, 4, fps=10)
    frame = Frame(4, 4)

    for index, expected in enumerate([(255, 0, 0), (0, 255, 0), (0, 0, 255)]):
        scene.render(frame, index / 10 + 0.01)
        assert tuple(frame.buf[0:3]) == expected


def test_frames_loop_by_default():
    from box.render.scenes import FramesScene

    data = solid_frames([(255, 0, 0), (0, 255, 0)], 2, 2)
    scene = FramesScene(data, 2, 2, fps=10)
    frame = Frame(2, 2)

    scene.render(frame, 0.01)
    first = bytes(frame.buf)
    scene.render(frame, 0.21)  # Two frames later: back to the start.
    assert bytes(frame.buf) == first


def test_frames_can_hold_on_the_last_frame():
    from box.render.scenes import FramesScene

    data = solid_frames([(255, 0, 0), (0, 255, 0)], 2, 2)
    scene = FramesScene(data, 2, 2, fps=10, loop=False)
    frame = Frame(2, 2)

    scene.render(frame, 50.0)
    assert tuple(frame.buf[0:3]) == (0, 255, 0)
    assert scene.finished(50.0)
    assert not scene.finished(0.0)


def test_frames_scale_to_a_different_panel_size():
    from box.render.scenes import FramesScene

    # A 2x2 upload onto a 4x4 panel: each source pixel covers a 2x2 block.
    data = bytes([255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 0])
    scene = FramesScene(data, 2, 2, fps=1)
    frame = Frame(4, 4)
    scene.render(frame, 0.0)

    assert tuple(frame.buf[0:3]) == (255, 0, 0), "top-left"
    px = lambda x, y: tuple(frame.buf[(y * 4 + x) * 3 : (y * 4 + x) * 3 + 3])  # noqa: E731
    assert px(3, 0) == (0, 255, 0), "top-right"
    assert px(0, 3) == (0, 0, 255), "bottom-left"
    assert px(3, 3) == (255, 255, 0), "bottom-right"


def test_frames_reject_a_ragged_buffer():
    from box.render.scenes import FramesScene

    with pytest.raises(ValueError, match="whole number of frames"):
        FramesScene(b"\x00" * 13, 2, 2, fps=1)


def test_frames_exact_size_uses_the_fast_path():
    from box.render.scenes import FramesScene

    scene = FramesScene(solid_frames([(1, 2, 3)], 4, 4), 4, 4)
    assert scene._index_map(4, 4) is None, "no scaling table for an exact match"
    assert scene._index_map(8, 8) is not None


def test_swedish_letters_have_glyphs():
    """Review titles and city names are Swedish; none of it may render as '?'."""
    for char in "ÅÄÖåäöÉéÜü":
        assert font.glyph(char) != font.glyph("?"), char
    assert font.glyph("ö") == font.glyph("Ö")


def test_subpixel_text_emits_constant_light():
    """Scrolling text must not pulse as it crosses half-pixel positions.

    What reaches the LEDs is the frame after the ~2.2 gamma, so that is what
    has to stay constant; a naive 50/50 split emitted 44% at the half-pixel.
    """
    lut = _gamma_lut(1.0, 2.2)
    frame = Frame(32, 8)
    light = []
    for step in range(11):
        frame.clear()
        frame.draw_text("W", 10 + step / 10, 0, (128, 200, 200))
        light.append(sum(frame.buf.translate(lut)))
    assert max(light) / min(light) < 1.05
