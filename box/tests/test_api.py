def test_get_display_state(client):
    """The rotation starts with whatever on-box sources report, nothing else.

    The core ships no generative scenes, so an idle box with no sources is
    simply blank; content arrives from sources and connectors.
    """
    response = client.get("/api/display")
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "weather"
    assert data["brightness"] == 1.0
    assert (data["width"], data["height"], data["fps"]) == (32, 32, 60)
    assert data["queued"] == 0
    # Weather is polled on the box, so its card is in the rotation with no
    # browser involved.
    assert "weather" in data["ambient"]


def test_show_text(client):
    client.post("/api/display/text", json={"text": "hello", "color": "#FF0000"})
    data = client.get("/api/display").json()
    assert data["text"] == "hello"
    assert data["color"] == "#FF0000"
    assert data["scene"] == "text"


def test_show_text_default_color(client):
    """A colourless event is styled by the box, not left undefined."""
    from box.events import PRIORITY_COLORS, Priority

    client.post("/api/display/text", json={"text": "hi"})
    data = client.get("/api/display").json()
    assert data["text"] == "hi"
    assert data["color"] == PRIORITY_COLORS[Priority.NORMAL]


def test_invalid_color_rejected(client):
    response = client.post("/api/display/text", json={"text": "hi", "color": "nope"})
    assert response.status_code == 422


def test_clear_display(client):
    client.post("/api/display/text", json={"text": "hello"})
    client.post("/api/display/clear")
    data = client.get("/api/display").json()
    assert data["text"] == ""
    assert data["scene"] == "blank"


def test_solid_scene(client):
    client.post("/api/display/solid", json={"color": "#123456"})
    assert client.get("/api/display").json()["scene"] == "solid"


def test_set_brightness(client):
    client.post("/api/display/brightness", json={"brightness": 0.5})
    assert client.get("/api/display").json()["brightness"] == 0.5


def test_invalid_brightness_too_high(client):
    assert (
        client.post("/api/display/brightness", json={"brightness": 1.5}).status_code
        == 422
    )


def test_invalid_brightness_too_low(client):
    assert (
        client.post("/api/display/brightness", json={"brightness": -0.1}).status_code
        == 422
    )


def test_frame_endpoint_shape(client):
    data = client.get("/api/display/frame").json()
    assert data["width"] == 32 and data["height"] == 32

    import base64

    assert len(base64.b64decode(data["frame"])) == 32 * 32 * 3


def test_preview_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "box" in response.text


def test_websocket_streams_frames(client):
    with client.websocket_connect("/ws/display") as ws:
        hello = ws.receive_json()
        assert hello == {"type": "hello", "width": 32, "height": 32, "fps": 60}
        frame = ws.receive_bytes()
        assert len(frame) == 32 * 32 * 3


def test_clear_leaves_the_rotation_empty(client):
    """Clear must not park a blank card that other cards then cycle past."""
    client.post("/api/display/clear")
    state = client.get("/api/display").json()
    assert state["scene"] == "blank"
    assert state["ambient"] == [], "a blank card would flash the panel off"
