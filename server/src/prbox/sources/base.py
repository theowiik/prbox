"""Event sources: anything that can produce content for the display."""

from typing import Protocol

from pydantic import BaseModel


class SourcePayload(BaseModel):
    """The part of a source's data the display actually needs."""

    display_text: str
    display_color: str


class Source(Protocol):
    """Structural interface for a source. No base class needed."""

    name: str

    def get(self) -> SourcePayload:
        """Current value for this source."""
        ...
