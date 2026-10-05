"""Finding the box: a default, an env var, or an optional .env."""

import os

import pytest

from gifcast.client import box_url, load_dotenv


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


def test_defaults_to_localhost():
    assert box_url() == "http://localhost:8000"


def test_explicit_url_wins(monkeypatch):
    monkeypatch.setenv("BOX_URL", "http://from-env:8000")
    assert box_url("http://explicit:9000/") == "http://explicit:9000"


def test_env_url_is_used(monkeypatch):
    monkeypatch.setenv("BOX_URL", "http://elsewhere:8000/")
    assert box_url() == "http://elsewhere:8000"


def test_port_alone_is_enough(monkeypatch):
    monkeypatch.setenv("BOX_PORT", "9000")
    assert box_url() == "http://localhost:9000"


def test_dotenv_supplies_the_port(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("# my box moved\nBOX_PORT = 9100\n\n")
    monkeypatch.chdir(tmp_path)
    assert box_url() == "http://localhost:9100"


def test_dotenv_is_found_in_a_parent(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text('BOX_URL="http://parent:8123"\n')
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    assert box_url() == "http://parent:8123"


def test_real_environment_beats_the_file(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("BOX_PORT=9100\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BOX_PORT", "9200")
    load_dotenv()
    assert box_url() == "http://localhost:9200"


def test_dotenv_search_stops_at_the_repo_root(tmp_path, monkeypatch):
    """A .env belonging to some parent directory is not ours to read."""
    (tmp_path / ".env").write_text("BOX_PORT=9999\n")
    project = tmp_path / "project"
    (project / ".git").mkdir(parents=True)
    monkeypatch.chdir(project)
    assert box_url() == "http://localhost:8000"
