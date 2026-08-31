from typing import Protocol

from pydantic import BaseModel, Field


class DisplayState(BaseModel):
    """What the display is currently showing. Serialised straight to the API."""

    scene: str = "blank"
    text: str = ""
    color: str = "#00FF00"
    brightness: float = Field(default=1.0, ge=0.0, le=1.0)
    width: int = 32
    height: int = 8
    fps: int = 30


class Display(Protocol):
    """A sink for rendered frames.

    Backends receive gamma-corrected RGB bytes (width * height * 3, row-major,
    top-left first) from the render engine. They do not know about text, colour
    or scenes — all of that lives in `prbox.render`.
    """

    width: int
    height: int

    def push_frame(self, buf: bytes) -> None:
        """Show one frame. Called on every tick of the render loop."""
        ...

    def close(self) -> None:
        """Release hardware resources."""
        ...
