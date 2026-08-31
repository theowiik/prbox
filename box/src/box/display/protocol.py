"""The contract every output device implements."""

from typing import Protocol


class Display(Protocol):
    """A sink for rendered frames.

    Backends receive gamma-corrected RGB bytes (width * height * 3, row-major,
    top-left first) from the render engine. They know nothing about text,
    colour, scenes or events — all of that resolves upstream, which is what
    lets the web preview and the LED matrix show byte-identical output.
    """

    width: int
    height: int

    def push_frame(self, buf: bytes) -> None:
        """Show one frame. Called on every tick of the render loop."""
        ...

    def close(self) -> None:
        """Release hardware resources."""
        ...
