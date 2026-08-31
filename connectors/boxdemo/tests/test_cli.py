"""CLI argument handling and failure paths — no network involved."""

import argparse

import pytest

from boxdemo.cli import MAX_FRAMES, build_parser, main, parse_size


def test_parse_size():
    assert parse_size("32x32") == (32, 32)
    assert parse_size("64X16") == (64, 16)


@pytest.mark.parametrize("bad", ["32", "axb", "", "32x"])
def test_parse_size_rejects_garbage(bad):
    with pytest.raises(argparse.ArgumentTypeError):
        parse_size(bad)


def test_defaults_to_ambient():
    """A generative visual is wallpaper, not a notification."""
    args = build_parser().parse_args(["rainbow"])
    assert args.priority == "ambient"
    assert args.frames == 180


@pytest.mark.parametrize("visual", ["rainbow", "life", "gradient"])
def test_visuals_accepted(visual):
    assert build_parser().parse_args([visual]).visual == visual


def test_unknown_visual_rejected():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["fractal"])


@pytest.mark.parametrize("count", [0, -1, MAX_FRAMES + 1])
def test_frame_count_is_bounded(count, caplog):
    assert main(["rainbow", "--frames", str(count), "--size", "8x8"]) == 2
    assert "--frames must be between" in caplog.text


def test_unreachable_box_fails_cleanly(caplog):
    """A connector must report a dead box, not traceback."""
    code = main(
        ["gradient", "--url", "http://127.0.0.1:1", "--size", "8x8", "--frames", "2"]
    )
    assert code == 1
    assert "Could not reach" in caplog.text
