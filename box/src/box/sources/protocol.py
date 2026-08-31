"""Event sources that live on the box itself.

An on-Pi source is just a connector that happens to run locally: it produces
Events and hands them to the scheduler through the same path an external
service uses. The split is about availability, not mechanism — your desktop
sleeps, so anything that must still be on screen at 3am belongs here.
"""

from typing import Protocol

from ..events import Event


class Source(Protocol):
    """Something the box polls for ambient content. Structural, no base class."""

    #: Identifies this source's card in the ambient rotation.
    name: str

    def poll(self) -> Event | None:
        """Current content, or None to leave the rotation untouched."""
        ...
