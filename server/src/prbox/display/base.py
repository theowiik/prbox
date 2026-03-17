from typing import Protocol

from pydantic import BaseModel, Field


class DisplayState(BaseModel):
    text: str = ""
    color: str = "#00FF00"
    brightness: float = Field(default=1.0, ge=0.0, le=1.0)


class Display(Protocol):
    def show_text(self, text: str, color: str = "#00FF00") -> None: ...
    def clear(self) -> None: ...
    def set_brightness(self, brightness: float) -> None: ...
    def get_state(self) -> DisplayState: ...
