"""GIF -> panel frames. All the sizing and timing decisions live here."""

import base64

import pytest
from PIL import Image

from gifcast.convert import convert


@pytest.fixture
def gif(tmp_path):
    def make(w=64, h=48, frames=6, duration=80, bg=(0, 0, 0)):
        images = []
        for i in range(frames):
            im = Image.new("RGB", (w, h), bg)
            im.putpixel((i % w, 0), (255, 0, 0))
            images.append(im)
        path = tmp_path / "t.gif"
        images[0].save(
            path, save_all=True, append_images=images[1:], duration=duration, loop=0
        )
        return path

    return make


def test_output_is_exactly_panel_sized(gif):
    anim = convert(gif(), 32, 32)
    assert anim.width == 32 and anim.height == 32
    assert len(anim.frames) == anim.count * 32 * 32 * 3


def test_frame_count_matches_the_gif(gif):
    assert convert(gif(frames=7), 16, 16).count == 7


def test_fps_derived_from_gif_delay(gif):
    # 80ms per frame is 12.5 fps.
    assert convert(gif(duration=80), 16, 16).fps == pytest.approx(12.5, rel=0.05)


def test_fps_can_be_overridden(gif):
    assert (
        convert(gif(duration=80), 16, 16, fps=5.0) == pytest.approx(5.0, rel=0.01)
        or convert(gif(duration=80), 16, 16, fps=5.0).fps == 5.0
    )


def test_fps_is_clamped_to_something_playable(gif):
    # A 10ms delay would be 100fps; the panel cannot and need not do that.
    assert convert(gif(duration=1), 16, 16).fps <= 60.0


def test_max_frames_truncates(gif):
    assert convert(gif(frames=50), 16, 16, max_frames=10).count == 10


def rows_of(anim):
    stride = anim.width * 3
    return [anim.frames[y * stride : (y + 1) * stride] for y in range(anim.height)]


def test_letterbox_preserves_aspect(gif):
    """A wide GIF on a square panel gets black bars, not a squashed image.

    The source is lit everywhere, so any black row can only be padding.
    """
    anim = convert(gif(w=64, h=16, frames=1, bg=(40, 60, 80)), 32, 32)
    blank = [i for i, r in enumerate(rows_of(anim)) if not any(r)]

    # 64x16 scaled by 0.5 is 32x8, centred: 12 padding rows above and below.
    assert blank == list(range(12)) + list(range(20, 32))


def test_crop_fills_the_panel(gif):
    """--crop trades edges for coverage, leaving no padding at all."""
    anim = convert(gif(w=64, h=16, frames=1, bg=(40, 60, 80)), 32, 32, crop=True)
    assert not [i for i, r in enumerate(rows_of(anim)) if not any(r)]


def test_transparency_composites_onto_black(tmp_path):
    """Transparent GIF pixels must not pick up a random palette colour."""
    im = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    im.putpixel((0, 0), (255, 0, 0, 255))
    path = tmp_path / "a.gif"
    im.save(path)

    anim = convert(path, 8, 8)
    assert tuple(anim.frames[0:3]) == (255, 0, 0)
    assert tuple(anim.frames[3:6]) == (0, 0, 0), "transparent -> black"


def test_encoded_is_valid_base64(gif):
    anim = convert(gif(frames=3), 8, 8)
    assert base64.b64decode(anim.encoded(), validate=True) == anim.frames


def test_still_image_is_a_one_frame_animation(tmp_path):
    path = tmp_path / "s.png"
    Image.new("RGB", (10, 10), (1, 2, 3)).save(path)
    assert convert(path, 8, 8).count == 1


def test_missing_file_raises(tmp_path):
    with pytest.raises(OSError):
        convert(tmp_path / "nope.gif", 8, 8)
