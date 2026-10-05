"""CLI argument handling and failure paths — no network involved."""

import argparse

import pytest
from PIL import Image

from gifcast.cli import build_parser, main, parse_size


def test_parse_size():
    assert parse_size("32x32") == (32, 32)
    assert parse_size("64X16") == (64, 16)


@pytest.mark.parametrize("bad", ["32", "axb", "", "32x"])
def test_parse_size_rejects_garbage(bad):
    with pytest.raises(argparse.ArgumentTypeError):
        parse_size(bad)


def test_defaults():
    args = build_parser().parse_args(["x.gif"])
    assert args.priority == "normal"
    assert args.duration == 10.0
    assert args.max_frames == 120
    assert args.source == "gifcast"
    assert not args.once


def test_missing_file_exits_nonzero(capsys, tmp_path):
    assert main([str(tmp_path / "nope.gif")]) == 2


def test_unreachable_box_fails_cleanly(tmp_path, caplog):
    """A connector must report a dead box, not traceback."""
    path = tmp_path / "a.png"
    Image.new("RGB", (4, 4), (9, 9, 9)).save(path)
    # Port 1 is reserved and will refuse instantly.
    code = main([str(path), "--url", "http://127.0.0.1:1", "--size", "8x8"])
    assert code == 1
    assert "Could not reach a box" in caplog.text
    assert "make dev" in caplog.text
