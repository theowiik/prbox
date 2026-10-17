"""The debug view's tail: the ring buffer, the logging bridge, and /api/logs."""

import asyncio
import logging

import pytest
from fastapi.testclient import TestClient

from box.api.app import create_app
from box.config import Settings
from box.logs import BufferHandler, LogBuffer, install, uninstall


@pytest.fixture
def buffer() -> LogBuffer:
    return LogBuffer(capacity=5)


def test_append_assigns_increasing_seq(buffer):
    a = buffer.append("first")
    b = buffer.append("second")
    assert (a.seq, b.seq) == (1, 2)
    assert buffer.cursor == 2


def test_buffer_is_bounded_but_seq_keeps_climbing(buffer):
    for i in range(12):
        buffer.append(f"line {i}")
    entries = buffer.since(0)
    assert len(entries) == 5
    assert entries[0].message == "line 7"
    assert buffer.cursor == 12


def test_since_returns_only_newer_entries(buffer):
    buffer.append("old")
    cursor = buffer.cursor
    buffer.append("new")
    assert [e.message for e in buffer.since(cursor)] == ["new"]


def test_channel_filters_before_the_limit(buffer):
    buffer.append("an event", channel="event")
    for i in range(3):
        buffer.append(f"line {i}")
    # The event is older than the last two lines, but it is the last event.
    events = buffer.since(0, limit=2, channel="event")
    assert [e.message for e in events] == ["an event"]


def test_handler_captures_records_and_tracebacks(buffer):
    logger = logging.getLogger("box.test.capture")
    handler = BufferHandler(buffer)
    logger.addHandler(handler)
    try:
        logger.warning("panel is %s", "sulking")
        try:
            raise RuntimeError("display said no")
        except RuntimeError:
            logger.exception("push failed")
    finally:
        logger.removeHandler(handler)

    warned, failed = buffer.since(0)
    assert warned.message == "panel is sulking"
    assert warned.level == "WARNING"
    assert warned.channel == "log"
    # The traceback is the reason a log view beats a status field.
    assert "RuntimeError: display said no" in failed.message


def test_structured_events_become_event_rows(buffer):
    logger = logging.getLogger("box.test.events")
    handler = BufferHandler(buffer)
    logger.addHandler(handler)
    try:
        logger.info(
            "queued github: ci green",
            extra={
                "box_event": {
                    "source": "github",
                    "priority": "normal",
                    "duration": 8.0,
                }
            },
        )
    finally:
        logger.removeHandler(handler)

    entry = buffer.since(0)[-1]
    assert entry.channel == "event"
    assert (entry.source, entry.priority, entry.duration) == ("github", "normal", 8.0)


def test_install_tees_the_root_logger(buffer):
    handler = install(buffer)
    try:
        logging.getLogger("box.somewhere").info("through the root")
    finally:
        uninstall(handler)
    assert buffer.since(0)[-1].message == "through the root"

    logging.getLogger("box.somewhere").info("after uninstall")
    assert "after uninstall" not in [e.message for e in buffer.since(0)]


@pytest.mark.anyio
async def test_subscribers_get_appended_entries(buffer, anyio_backend):
    buffer.bind(asyncio.get_running_loop())
    queue = buffer.subscribe()
    try:
        buffer.append("live")
        entry = await asyncio.wait_for(queue.get(), 1)
    finally:
        buffer.unsubscribe(queue)
    assert entry.message == "live"


# -- the API -------------------------------------------------------------


def test_submitting_an_event_shows_up_in_the_log(client):
    client.post(
        "/api/events",
        json={"source": "discord", "scene": {"kind": "text", "text": "ping"}},
    )
    body = client.get("/api/logs").json()
    events = [e for e in body["entries"] if e["channel"] == "event"]
    latest = events[-1]
    assert latest["source"] == "discord"
    assert latest["priority"] == "normal"
    assert "ping" in latest["message"]
    assert body["cursor"] >= latest["seq"]


def test_startup_lines_are_in_the_tail(client):
    messages = [e["message"] for e in client.get("/api/logs").json()["entries"]]
    assert any("Render loop started" in m for m in messages)


def test_since_cursor_returns_only_what_is_new(client):
    cursor = client.get("/api/logs").json()["cursor"]
    client.post(
        "/api/events",
        json={"source": "build", "scene": {"kind": "text", "text": "failed"}},
    )
    entries = client.get(f"/api/logs?since={cursor}").json()["entries"]
    assert entries and all(e["seq"] > cursor for e in entries)
    assert any("failed" in e["message"] for e in entries)


def test_channel_filter(client):
    client.post(
        "/api/events",
        json={"source": "slack", "scene": {"kind": "text", "text": "standup"}},
    )
    entries = client.get("/api/logs?channel=event").json()["entries"]
    assert entries and {e["channel"] for e in entries} == {"event"}


def test_clear_drops_what_came_before(client):
    client.post(
        "/api/events",
        json={"source": "slack", "scene": {"kind": "text", "text": "standup"}},
    )
    assert client.delete("/api/logs").status_code == 200
    # Not empty: anything the process logs after the clear (the HTTP client's
    # own request lines here, uvicorn's access log on the Pi) lands right back
    # in the tail. What matters is that nothing older survived.
    messages = [e["message"] for e in client.get("/api/logs").json()["entries"]]
    assert not any("standup" in m for m in messages)


def test_clear_requires_the_token_when_one_is_set():
    settings = Settings(mode="emulator", width=32, height=32, fps=60, token="s3cret")
    with TestClient(create_app(settings)) as c:
        assert c.delete("/api/logs").status_code == 401
        assert c.get("/api/logs").status_code == 200
        ok = c.delete("/api/logs", headers={"Authorization": "Bearer s3cret"})
        assert ok.status_code == 200


def test_websocket_sends_backlog_then_live_entries(client):
    with client.websocket_connect("/ws/logs") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello"
        assert any(e["channel"] == "event" for e in hello["entries"])

        client.post(
            "/api/events",
            json={"source": "email", "scene": {"kind": "text", "text": "inbox"}},
        )
        msg = ws.receive_json()
        assert msg["type"] == "entry"
        assert msg["entry"]["source"] == "email"
        assert msg["entry"]["seq"] > hello["cursor"]
