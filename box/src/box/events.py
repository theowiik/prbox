"""The event contract: what a connector sends, and how it becomes a scene.

This module is the API's stable surface. Connectors — a Discord listener on a
desktop, a weather poller on the Pi itself — all speak this shape and nothing
else, so adding one never means touching the box.

Presentation lives here rather than in the connector. A connector says *what
happened* (`source`, `text`, `priority`); the box decides what that looks like.
Restyling every notification is then one edit here instead of a redeploy of
every connector.
"""

import base64
import time
import uuid
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, PrivateAttr, field_validator, model_validator

from .render.frame import hex_to_rgb
from .render.scenes import (
    BlankScene,
    FramesScene,
    Scene,
    SolidScene,
    TextScene,
)


class Priority(StrEnum):
    """How insistently an event wants the panel.

    The two instant tiers are the interesting ones. A Discord ping should jump
    the queue, but two pings arriving together should not shove each other off
    the panel before either can be read — so an `alert` yields to an instant
    event already on screen and shows next instead. An `alarm` never yields:
    a smoke detector does not wait its turn behind a chat notification.
    """

    #: Background content. Joins the idle rotation, never interrupts.
    AMBIENT = "ambient"
    #: Shown in turn for its duration, then the panel returns to ambient.
    NORMAL = "normal"
    #: Jumps the queue — but waits if another instant event is on the panel.
    ALERT = "alert"
    #: Always takes the panel, interrupting even an alert. Use it sparingly.
    ALARM = "alarm"

    @property
    def rank(self) -> int:
        """Ordering. `Priority` is a StrEnum, so `<` would compare spelling."""
        return _RANK[self]


_RANK: dict[Priority, int] = {
    Priority.AMBIENT: 0,
    Priority.NORMAL: 1,
    Priority.ALERT: 2,
    Priority.ALARM: 3,
}


#: Per-source colours. A connector that sends no colour gets its brand here.
SOURCE_COLORS: dict[str, str] = {
    "discord": "#5865F2",
    "slack": "#36C5F0",
    "github": "#F0F6FC",
    "email": "#E8B923",
    "calendar": "#4FC3F7",
    "build": "#FF5252",
    "weather": "#78909C",
    # En Stor Stark Review — lager amber.
    "essr": "#F2A900",
}

#: Fallback colour by priority when the source is unknown.
PRIORITY_COLORS: dict[Priority, str] = {
    Priority.AMBIENT: "#7A8A99",
    Priority.NORMAL: "#00E676",
    Priority.ALERT: "#FF4F00",
    Priority.ALARM: "#FF1744",
}

#: How long an event holds the panel when it does not say.
DEFAULT_DURATION: dict[Priority, float] = {
    Priority.AMBIENT: 12.0,
    Priority.NORMAL: 8.0,
    Priority.ALERT: 10.0,
    # Longer: an alarm is worth interrupting for, so it is worth reading twice.
    Priority.ALARM: 20.0,
}

#: Ceiling on a single animation upload, before base64 expansion.
MAX_FRAMES_BYTES = 8 * 1024 * 1024


class TextSpec(BaseModel):
    """Scrolling or centred text — the common case."""

    kind: Literal["text"] = "text"
    text: str = Field(max_length=512)
    #: Omit to let the box pick from the source or priority.
    color: str | None = None

    @field_validator("color")
    @classmethod
    def _valid_color(cls, v: str | None) -> str | None:
        if v is not None:
            hex_to_rgb(v)
        return v


class SolidSpec(BaseModel):
    kind: Literal["solid"] = "solid"
    color: str

    @field_validator("color")
    @classmethod
    def _valid_color(cls, v: str) -> str:
        hex_to_rgb(v)
        return v


class BlankSpec(BaseModel):
    kind: Literal["blank"] = "blank"


class FramesSpec(BaseModel):
    """A pre-rendered animation: raw RGB frames, base64'd end to end.

    Decoding stays on the sender. A connector converts its GIF or video to
    panel-sized RGB and uploads pixels, so the Pi never grows an image stack and
    the same payload works for anything that can produce frames.
    """

    kind: Literal["frames"] = "frames"
    width: int = Field(ge=1, le=256)
    height: int = Field(ge=1, le=256)
    fps: float = Field(default=12.0, ge=0.1, le=60.0)
    loop: bool = True
    #: base64 of frame_count * width * height * 3 bytes, row-major from top-left.
    data: str

    #: The decoded pixels. Decoded once, during validation: an upload can be
    #: 8 MB, and decoding it again for every consumer is real time on a Pi.
    _raw: bytes = PrivateAttr(default=b"")

    @property
    def raw(self) -> bytes:
        return self._raw

    @model_validator(mode="after")
    def _decode(self) -> FramesSpec:
        # Size first, from the encoded length, so an oversized upload is
        # refused before anything is allocated for it.
        if len(self.data) * 3 // 4 > MAX_FRAMES_BYTES + 2:
            raise ValueError(f"data exceeds {MAX_FRAMES_BYTES} bytes")
        try:
            raw = base64.b64decode(self.data, validate=True)
        except ValueError as exc:
            raise ValueError("data must be valid base64") from exc
        if not raw:
            raise ValueError("data is empty")
        if len(raw) > MAX_FRAMES_BYTES:
            raise ValueError(f"data exceeds {MAX_FRAMES_BYTES} bytes")
        # Checked here rather than at render time, so a truncated upload is a
        # 422 at the door instead of a crash mid-loop.
        stride = self.width * self.height * 3
        if len(raw) % stride:
            raise ValueError(
                f"data is {len(raw)} bytes, not a whole number of "
                f"{self.width}x{self.height} RGB frames ({stride} bytes each)"
            )
        self._raw = raw
        return self

    def frame_count(self) -> int:
        return len(self._raw) // (self.width * self.height * 3)


SceneSpec = Annotated[
    TextSpec | SolidSpec | BlankSpec | FramesSpec,
    Field(discriminator="kind"),
]


class Event(BaseModel):
    """One request for the panel's attention."""

    #: Who sent this. Used for styling, for coalescing bursts, and for muting.
    source: str = Field(default="api", max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")
    scene: SceneSpec
    priority: Priority = Priority.NORMAL
    #: Seconds to hold the panel. Omit for the priority's default.
    duration: float | None = Field(default=None, gt=0.0, le=3600.0)

    def resolved_duration(self) -> float:
        return self.duration or DEFAULT_DURATION[self.priority]

    def resolved_color(self) -> str:
        """The colour this event should use when it did not name one."""
        return SOURCE_COLORS.get(self.source, PRIORITY_COLORS[self.priority])

    def effective_color(self) -> str:
        """The colour actually on screen: the spec's own, or the fallback."""
        spec = self.scene
        if isinstance(spec, TextSpec) and spec.color:
            return spec.color
        if isinstance(spec, SolidSpec):
            return spec.color
        return self.resolved_color()


def build_scene(event: Event) -> Scene:
    """Turn an event's spec into something the render engine can draw."""
    spec = event.scene
    match spec:
        case TextSpec():
            return TextScene(
                spec.text, hex_to_rgb(spec.color or event.resolved_color())
            )
        case SolidSpec():
            return SolidScene(hex_to_rgb(spec.color))
        case BlankSpec():
            return BlankScene()
        case FramesSpec():
            return FramesScene(
                spec.raw, spec.width, spec.height, fps=spec.fps, loop=spec.loop
            )
    raise ValueError(f"unhandled scene kind: {spec!r}")


class Scheduled:
    """An event the scheduler has accepted, with its bookkeeping."""

    __slots__ = ("id", "event", "scene", "duration", "started_at")

    def __init__(self, event: Event) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.event = event
        self.scene = build_scene(event)
        self.duration = event.resolved_duration()
        self.started_at: float | None = None

    @property
    def source(self) -> str:
        return self.event.source

    @property
    def priority(self) -> Priority:
        return self.event.priority

    def start(self, now: float | None = None) -> None:
        self.started_at = time.monotonic() if now is None else now

    def expired(self, now: float) -> bool:
        return self.started_at is not None and now - self.started_at >= self.duration

    def remaining(self, now: float) -> float:
        if self.started_at is None:
            return self.duration
        return max(0.0, self.duration - (now - self.started_at))
