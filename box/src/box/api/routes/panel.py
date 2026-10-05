"""Panel state, brightness, the live frame stream, and the dashboard.

The scene-specific endpoints here are thin shims over `/api/events`; they exist
because the dashboard is easier to write against them, not because they are a
second way in. Connectors should use `/api/events`.
"""

import asyncio
import base64
import logging
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ...events import Event, Priority, SolidSpec, TextSpec
from ...scheduler import Scheduler
from ...state import PanelState
from ..auth import Protected

logger = logging.getLogger(__name__)
router = APIRouter()

_INDEX = Path(__file__).resolve().parent.parent / "web" / "index.html"


def _get_scheduler(request: Request) -> Scheduler:
    return request.app.state.scheduler


class SetBrightnessRequest(BaseModel):
    brightness: float = Field(ge=0.0, le=1.0)


class ShowTextRequest(TextSpec):
    """The dashboard's text form: a scene plus the tier to send it at."""

    priority: Priority = Priority.NORMAL


class Ok(BaseModel):
    status: str = "ok"


@router.get("/api/display", tags=["display"], summary="Current panel state")
def get_state(scheduler: Scheduler = Depends(_get_scheduler)) -> PanelState:
    return scheduler.get_state()


def _submit(
    scheduler: Scheduler,
    spec,
    priority: Priority = Priority.NORMAL,
    source: str = "dashboard",
) -> Ok:
    """Dashboard actions arrive as events too, so there is one code path."""
    scheduler.submit(
        Event(source=source, scene=spec, priority=priority),
        # An interactive choice should land on the panel immediately.
        focus=priority is Priority.AMBIENT,
    )
    return Ok()


@router.post("/api/display/text", tags=["display"], dependencies=[Protected])
def show_text(
    body: ShowTextRequest, scheduler: Scheduler = Depends(_get_scheduler)
) -> Ok:
    # Rebuilt as a plain TextSpec: priority belongs to the event, not the scene.
    spec = TextSpec(text=body.text, color=body.color)
    return _submit(scheduler, spec, priority=body.priority)


@router.post("/api/display/solid", tags=["display"], dependencies=[Protected])
def show_solid(body: SolidSpec, scheduler: Scheduler = Depends(_get_scheduler)) -> Ok:
    return _submit(scheduler, body)


@router.post("/api/display/clear", tags=["display"], dependencies=[Protected])
def clear(scheduler: Scheduler = Depends(_get_scheduler)) -> Ok:
    # Empty the rotation and the queue and leave it empty — installing a blank
    # *card* would park a dark slot in the rotation that other cards cycle past.
    scheduler.clear_ambient()
    scheduler.clear()
    return Ok()


@router.post("/api/display/brightness", tags=["display"], dependencies=[Protected])
def set_brightness(
    body: SetBrightnessRequest, scheduler: Scheduler = Depends(_get_scheduler)
) -> Ok:
    scheduler.set_brightness(body.brightness)
    return Ok()


@router.get("/api/display/frame", tags=["display"], summary="Latest frame, base64 RGB")
def get_frame(request: Request) -> dict:
    """Single-frame fallback for clients that cannot hold a WebSocket open."""
    engine = request.app.state.engine
    width, height = engine.size
    return {
        "width": width,
        "height": height,
        "frame": base64.b64encode(engine.latest_frame()).decode("ascii"),
    }


@router.websocket("/ws/display")
async def stream_frames(websocket: WebSocket) -> None:
    """Push every rendered frame to the browser as raw RGB bytes."""
    await websocket.accept()
    engine = websocket.app.state.engine
    width, height = engine.size
    queue = engine.subscribe()
    try:
        await websocket.send_json(
            {"type": "hello", "width": width, "height": height, "fps": engine.fps}
        )
        while True:
            frame = await queue.get()
            await websocket.send_bytes(frame)
    except WebSocketDisconnect, asyncio.CancelledError:
        pass
    except RuntimeError:
        # Socket closed underneath us mid-send; nothing to do but unsubscribe.
        pass
    finally:
        engine.unsubscribe(queue)


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def preview() -> HTMLResponse:
    try:
        return HTMLResponse(_INDEX.read_text(encoding="utf-8"))
    except OSError:
        logger.exception("Could not read preview page at %s", _INDEX)
        raise HTTPException(
            status_code=500, detail="Preview page unavailable"
        ) from None
