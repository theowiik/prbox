"""What the panel is showing right now.

Separate from `display/` on purpose: that package is about *devices* that
consume frames, while this is the scheduler's answer to "what is on screen".
The two were conflated when `DisplayState` lived beside the `Display` protocol.
"""

from pydantic import BaseModel, Field


class PanelState(BaseModel):
    """Serialised straight to `GET /api/display`."""

    #: Name of the scene being rendered: text, frames, solid or blank.
    scene: str = "blank"
    #: Which connector owns the panel right now, if any.
    source: str | None = None
    #: The tier that won it: ambient, normal, alert or alarm.
    priority: str | None = None
    text: str = ""
    color: str = "#00FF00"
    brightness: float = Field(default=1.0, ge=0.0, le=1.0)
    width: int = 32
    height: int = 32
    fps: int = 30
    #: Events waiting behind the one on screen.
    queued: int = 0
    #: Sources with a card in the idle rotation.
    ambient: list[str] = Field(default_factory=list)
