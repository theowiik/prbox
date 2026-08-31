import pytest

from box.config import Settings


def test_defaults_from_empty_env(monkeypatch):
    for key in list(dict(__import__("os").environ)):
        if key.startswith("BOX_"):
            monkeypatch.delenv(key, raising=False)
    settings = Settings.from_env()
    assert (settings.mode, settings.width, settings.height) == ("dev", 32, 32)


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("BOX_DISPLAY_WIDTH", "64")
    monkeypatch.setenv("BOX_FPS", "24")
    monkeypatch.setenv("BOX_TTY_PREVIEW", "yes")
    settings = Settings.from_env()
    assert settings.width == 64
    assert settings.fps == 24
    assert settings.tty_preview is True


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("BOX_DISPLAY_MODE", "hologram"),
        ("BOX_FPS", "0"),
        ("BOX_FPS", "999"),
        ("BOX_DISPLAY_WIDTH", "0"),
        ("BOX_GAMMA", "0"),
        ("BOX_FPS", "fast"),
    ],
)
def test_invalid_env_rejected(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        Settings.from_env()
