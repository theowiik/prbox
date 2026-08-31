"""The connector-facing contract: /api/events, auth, and animation upload."""

import base64

import pytest
from fastapi.testclient import TestClient

from box.api.app import create_app
from box.config import Settings
from box.events import MAX_FRAMES_BYTES


def frames_payload(count=4, w=32, h=32, byte=200):
    return base64.b64encode(bytes([byte]) * (count * w * h * 3)).decode()


def test_submit_text_event(client):
    r = client.post(
        "/api/events",
        json={"source": "discord", "scene": {"kind": "text", "text": "hello"}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "discord"
    assert body["priority"] == "normal"
    assert len(body["id"]) == 12

    state = client.get("/api/display").json()
    assert state["text"] == "hello"
    assert state["source"] == "discord"


def test_alert_preempts_via_api(client):
    client.post(
        "/api/events",
        json={
            "source": "a",
            "duration": 60,
            "scene": {"kind": "text", "text": "slow"},
        },
    )
    client.post(
        "/api/events",
        json={
            "source": "b",
            "priority": "alert",
            "scene": {"kind": "text", "text": "urgent"},
        },
    )
    assert client.get("/api/display").json()["text"] == "urgent"


def test_ambient_event_joins_rotation(client):
    client.post(
        "/api/events",
        json={
            "source": "clock",
            "priority": "ambient",
            "scene": {"kind": "text", "text": "12:00"},
        },
    )
    assert "clock" in client.get("/api/display").json()["ambient"]


def test_default_source_is_accepted(client):
    r = client.post("/api/events", json={"scene": {"kind": "text", "text": "x"}})
    assert r.status_code == 200
    assert r.json()["source"] == "api"


@pytest.mark.parametrize(
    "payload",
    [
        {"scene": {"kind": "nonsense"}},
        {"scene": {"kind": "text"}},
        {"scene": {"kind": "text", "text": "x", "color": "notacolor"}},
        {"scene": {"kind": "text", "text": "x"}, "priority": "urgent"},
        {"scene": {"kind": "text", "text": "x"}, "duration": -1},
        {"scene": {"kind": "text", "text": "x"}, "source": "bad source!"},
        {"scene": {"kind": "life", "speed": 999}},
    ],
)
def test_malformed_events_rejected(client, payload):
    assert client.post("/api/events", json=payload).status_code == 422


def test_delete_clears_the_queue(client):
    client.post(
        "/api/events",
        json={"source": "a", "duration": 60, "scene": {"kind": "text", "text": "x"}},
    )
    assert client.delete("/api/events").status_code == 200
    assert client.get("/api/display").json()["queued"] == 0


# -- animation -------------------------------------------------------------


def test_submit_frames(client):
    r = client.post(
        "/api/events",
        json={
            "source": "gif",
            "scene": {
                "kind": "frames",
                "width": 32,
                "height": 32,
                "fps": 10,
                "data": frames_payload(),
            },
        },
    )
    assert r.status_code == 200
    assert client.get("/api/display").json()["scene"] == "frames"


def test_frames_with_wrong_byte_count_rejected(client):
    """A truncated upload must fail at the door, not mid-render."""
    bad = base64.b64encode(b"\x01" * (32 * 32 * 3 + 7)).decode()
    r = client.post(
        "/api/events",
        json={
            "source": "gif",
            "scene": {"kind": "frames", "width": 32, "height": 32, "data": bad},
        },
    )
    assert r.status_code == 422
    assert "whole number" in r.text


def test_frames_reject_bad_base64(client):
    r = client.post(
        "/api/events",
        json={
            "source": "gif",
            "scene": {"kind": "frames", "width": 4, "height": 4, "data": "!!!!"},
        },
    )
    assert r.status_code == 422


def test_frames_reject_empty(client):
    r = client.post(
        "/api/events",
        json={
            "source": "gif",
            "scene": {"kind": "frames", "width": 4, "height": 4, "data": ""},
        },
    )
    assert r.status_code == 422


def test_oversized_animation_rejected(client):
    huge = base64.b64encode(b"\x00" * (MAX_FRAMES_BYTES + 1)).decode()
    r = client.post(
        "/api/events",
        json={
            "source": "gif",
            "scene": {"kind": "frames", "width": 32, "height": 32, "data": huge},
        },
    )
    assert r.status_code == 422


def test_mismatched_panel_size_is_scaled_not_rejected(client):
    """A connector that guesses the panel size wrong still gets something."""
    r = client.post(
        "/api/events",
        json={
            "source": "gif",
            "scene": {
                "kind": "frames",
                "width": 16,
                "height": 16,
                "data": frames_payload(count=2, w=16, h=16),
            },
        },
    )
    assert r.status_code == 200


# -- auth ------------------------------------------------------------------


@pytest.fixture
def secure_client():
    settings = Settings(mode="dev", width=32, height=32, fps=60, token="s3cret")
    with TestClient(create_app(settings)) as c:
        yield c


def test_writes_require_a_token_when_configured(secure_client):
    r = secure_client.post("/api/events", json={"scene": {"kind": "text", "text": "x"}})
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_correct_token_accepted(secure_client):
    r = secure_client.post(
        "/api/events",
        json={"scene": {"kind": "text", "text": "x"}},
        headers={"Authorization": "Bearer s3cret"},
    )
    assert r.status_code == 200


@pytest.mark.parametrize(
    "header",
    ["Bearer wrong", "Basic s3cret", "s3cret", "Bearer ", ""],
)
def test_bad_credentials_rejected(secure_client, header):
    r = secure_client.post(
        "/api/events",
        json={"scene": {"kind": "text", "text": "x"}},
        headers={"Authorization": header},
    )
    assert r.status_code == 401


def test_reads_stay_open(secure_client):
    """The dashboard must render before it knows the token."""
    assert secure_client.get("/api/display").status_code == 200
    assert secure_client.get("/").status_code == 200


def test_auth_is_off_by_default(client):
    assert (
        client.post(
            "/api/events", json={"scene": {"kind": "text", "text": "x"}}
        ).status_code
        == 200
    )
