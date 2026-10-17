"""Event sources that live on the box itself.

An on-Pi source is just a connector that happens to run locally: it produces
Events and hands them to the scheduler through the same path an external
service uses. The split is about availability, not mechanism — your desktop
sleeps, so anything that must still be on screen at 3am belongs here.
"""

from typing import Protocol

from ..events import Event


class Source(Protocol):
    """Something the box polls for content. Structural, no base class."""

    #: Identifies the source: its ambient card, its colour, its log lines.
    name: str
    #: Seconds between polls.
    interval: float

    def poll(self) -> Event | None:
        """Something to show, or None for nothing new.

        Runs on a worker thread, so it may block — fetch a URL, read a file.
        It must not touch the scheduler; return the event instead.
        """
        ...
