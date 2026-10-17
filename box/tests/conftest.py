import pytest
from fastapi.testclient import TestClient

from box.api.app import create_app
from box.config import Settings


@pytest.fixture
def settings(tmp_path) -> Settings:
    # A small panel keeps per-frame work trivial so tests stay fast.
    return Settings(
        mode="emulator",
        width=32,
        height=32,
        fps=60,
        # Feeds poll the internet and remember what they saw; neither belongs
        # in a test run.
        feeds=False,
        state_dir=tmp_path / "state",
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
