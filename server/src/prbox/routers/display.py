import asyncio
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
from pydantic import BaseModel, Field, field_validator

from ..controller import DisplayController
from ..display.base import DisplayState
from ..render.frame import hex_to_rgb

logger = logging.getLogger(__name__)
router = APIRouter()

_INDEX = Path(__file__).resolve().parent.parent / "web" / "index.html"


def _get_controller(request: Request) -> DisplayController:
    return request.app.state.controller


class ShowTextRequest(BaseModel):
    text: str = Field(max_length=512)
    color: str = "#00FF00"

    @field_validator("color")
    @classmethod
    def _valid_color(cls, v: str) -> str:
        hex_to_rgb(v)  # Raises ValueError, which pydantic reports as a 422.
        return v


class SolidRequest(BaseModel):
    color: str

    @field_validator("color")
    @classmethod
    def _valid_color(cls, v: str) -> str:
        hex_to_rgb(v)
        return v


class RainbowRequest(BaseModel):
    speed: float = Field(default=0.08, ge=0.0, le=2.0)
    blobs: int = Field(default=4, ge=0, le=16)
    noise: float = Field(default=0.25, ge=0.0, le=1.0)
    saturation: float = Field(default=1.0, ge=0.0, le=1.0)


class SetBrightnessRequest(BaseModel):
    brightness: float = Field(ge=0.0, le=1.0)


class Ok(BaseModel):
    status: str = "ok"


@router.get("/api/display", tags=["display"], summary="Current display state")
def get_state(controller: DisplayController = Depends(_get_controller)) -> DisplayState:
    return controller.get_state()


@router.post("/api/display/text", tags=["display"], summary="Show scrolling text")
def show_text(
    body: ShowTextRequest, controller: DisplayController = Depends(_get_controller)
) -> Ok:
    controller.show_text(body.text, body.color)
    return Ok()


@router.post("/api/display/rainbow", tags=["display"], summary="Show rainbow blobs")
def show_rainbow(
    body: RainbowRequest, controller: DisplayController = Depends(_get_controller)
) -> Ok:
    controller.show_rainbow(
        speed=body.speed,
        blobs=body.blobs,
        noise=body.noise,
        saturation=body.saturation,
    )
    return Ok()


@router.post("/api/display/solid", tags=["display"], summary="Fill with one colour")
def show_solid(
    body: SolidRequest, controller: DisplayController = Depends(_get_controller)
) -> Ok:
    controller.show_solid(body.color)
    return Ok()


@router.post("/api/display/clear", tags=["display"], summary="Blank the display")
def clear(controller: DisplayController = Depends(_get_controller)) -> Ok:
    controller.clear()
    return Ok()


@router.post("/api/display/brightness", tags=["display"], summary="Set brightness")
def set_brightness(
    body: SetBrightnessRequest, controller: DisplayController = Depends(_get_controller)
) -> Ok:
    controller.set_brightness(body.brightness)
    return Ok()


@router.get(
    "/api/display/frame",
    tags=["display"],
    summary="Latest rendered frame as base64 RGB",
)
def get_frame(controller: DisplayController = Depends(_get_controller)) -> dict:
    """Single-frame fallback for clients that cannot use the WebSocket."""
    import base64

    engine = controller.engine
    width, height = engine.size
    return {
        "width": width,
        "height": height,
        "frame": base64.b64encode(engine.latest_frame()).decode("ascii"),
    }


@router.websocket("/ws/display")
async def stream_frames(websocket: WebSocket) -> None:
    """Push every rendered frame to the browser as raw RGB bytes.

    Streaming beats polling here: the preview shows exactly the frames the LED
    matrix gets, at the same cadence, with no interpolation guesswork.
    """
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
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except RuntimeError:
        # Socket closed underneath us mid-send; nothing to clean up but the queue.
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
