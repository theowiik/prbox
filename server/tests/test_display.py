import pytest
from fastapi.testclient import TestClient

from prbox.app import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_get_display_state(client):
    response = client.get("/api/display")
    assert response.status_code == 200
    data = response.json()
    assert data["text"] == ""
    assert data["color"] == "#00FF00"
    assert data["brightness"] == 1.0
    assert data["width"] == 32
    assert data["height"] == 8


def test_show_text(client):
    client.post("/api/display/text", json={"text": "hello", "color": "#FF0000"})
    data = client.get("/api/display").json()
    assert data["text"] == "hello"
    assert data["color"] == "#FF0000"


def test_show_text_default_color(client):
    client.post("/api/display/text", json={"text": "hi"})
    data = client.get("/api/display").json()
    assert data["text"] == "hi"
    assert data["color"] == "#00FF00"


def test_clear_display(client):
    client.post("/api/display/text", json={"text": "hello"})
    client.post("/api/display/clear")
    data = client.get("/api/display").json()
    assert data["text"] == ""


def test_set_brightness(client):
    client.post("/api/display/brightness", json={"brightness": 0.5})
    data = client.get("/api/display").json()
    assert data["brightness"] == 0.5


def test_invalid_brightness_too_high(client):
    response = client.post("/api/display/brightness", json={"brightness": 1.5})
    assert response.status_code == 422


def test_invalid_brightness_too_low(client):
    response = client.post("/api/display/brightness", json={"brightness": -0.1})
    assert response.status_code == 422


def test_preview_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "prbox" in response.text
