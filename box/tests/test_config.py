import os

import pytest

from box.config import Settings


def test_defaults_from_empty_env(monkeypatch):
    for key in list(dict(__import__("os").environ)):
        if key.startswith("BOX_"):
            monkeypatch.delenv(key, raising=False)
    settings = Settings.from_env()
    assert (settings.mode, settings.width, settings.height) == ("emulator", 32, 32)


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
        ("BOX_TTY_PREVIEW", "ture"),
    ],
)
def test_invalid_env_rejected(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        Settings.from_env()


# -- the optional .env ---------------------------------------------------


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    """No BOX_* set and no .env above, so a default is really a default.

    load_dotenv writes into os.environ (that is the point of it), which
    monkeypatch cannot undo, so the whole BOX_* namespace is saved and put back.
    """
    saved = {k: v for k, v in os.environ.items() if k.startswith("BOX_")}
    for key in saved:
        del os.environ[key]
    monkeypatch.chdir(tmp_path)
    yield
    for key in [k for k in os.environ if k.startswith("BOX_")]:
        del os.environ[key]
    os.environ.update(saved)


def test_dotenv_fills_in_settings(tmp_path, monkeypatch):
    monkeypatch.delenv("BOX_PORT", raising=False)
    (tmp_path / ".env").write_text("# my box moved\nBOX_PORT = 9100\n\n")
    assert Settings.from_env().port == 9100


def test_dotenv_is_found_in_a_parent(tmp_path, monkeypatch):
    monkeypatch.delenv("BOX_CITY", raising=False)
    (tmp_path / ".env").write_text('BOX_CITY="Malmo"\n')
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    assert Settings.from_env().city == "Malmo"


def test_the_environment_beats_the_file(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("BOX_PORT=9100\n")
    monkeypatch.setenv("BOX_PORT", "9200")
    assert Settings.from_env().port == 9200


def test_junk_lines_are_ignored(tmp_path, monkeypatch):
    monkeypatch.delenv("BOX_PORT", raising=False)
    (tmp_path / ".env").write_text("nonsense\n\n  # comment\nBOX_PORT=9300\n")
    assert Settings.from_env().port == 9300


def test_no_dotenv_is_fine():
    assert Settings.from_env().port == 8000


def test_dotenv_search_stops_at_the_repo_root(tmp_path, monkeypatch):
    """A .env belonging to some parent directory is not ours to read."""
    (tmp_path / ".env").write_text("BOX_PORT=9999\n")
    project = tmp_path / "project"
    (project / ".git").mkdir(parents=True)
    monkeypatch.chdir(project)
    assert Settings.from_env().port == 8000


# -- matrix wiring -------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("BOX_MATRIX_CHAIN", "3"),  # 32 does not split across 3 panels
        ("BOX_MATRIX_PARALLEL", "0"),
        ("BOX_MATRIX_HW_BRIGHTNESS", "0"),
        ("BOX_MATRIX_PWM_BITS", "12"),
    ],
)
def test_bad_matrix_wiring_rejected_in_matrix_mode(monkeypatch, key, value):
    monkeypatch.setenv("BOX_DISPLAY_MODE", "matrix")
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        Settings.from_env()


def test_matrix_wiring_ignored_in_dev_mode(monkeypatch):
    """A Pi's .env copied to a laptop must not stop the dev server starting."""
    monkeypatch.setenv("BOX_MATRIX_CHAIN", "3")
    assert Settings.from_env().mode == "emulator"


def test_chained_panels_accepted(monkeypatch):
    monkeypatch.setenv("BOX_DISPLAY_MODE", "matrix")
    monkeypatch.setenv("BOX_DISPLAY_WIDTH", "64")
    monkeypatch.setenv("BOX_MATRIX_CHAIN", "2")
    assert Settings.from_env().matrix.chain_length == 2


@pytest.mark.parametrize(("raw", "expected"), [("off", False), ("YES", True)])
def test_bool_spellings(monkeypatch, raw, expected):
    monkeypatch.setenv("BOX_TTY_PREVIEW", raw)
    assert Settings.from_env().tty_preview is expected


def test_dev_is_still_accepted_as_the_emulator(monkeypatch):
    """`dev` was the old name; an existing .env must keep working."""
    monkeypatch.setenv("BOX_DISPLAY_MODE", "dev")
    assert Settings.from_env().mode == "emulator"
