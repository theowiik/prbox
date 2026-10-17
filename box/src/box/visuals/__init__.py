"""Built-in visuals: named animations the box renders for itself.

An event asks for one by name (`{"kind": "visual", "name": "beer"}`), so a
feed, the dashboard or a one-line curl can put a rainbow or a pouring pint on
the panel without generating or uploading any pixels.

Rendering a visual is slow (seconds, for the rainbow on a Pi) and its output
depends only on the name and the panel size, so it is done once per size and
cached. Callers on the event loop warm the cache through `asyncio.to_thread`
first (see `events.prepare`); the render loop itself only ever plays bytes.
"""

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from .animations import beer_frames, gradient_frames, life_frames, rainbow_frames


@dataclass(frozen=True)
class Visual:
    #: (width, height) -> count * width * height * 3 bytes of RGB frames.
    render: Callable[[int, int], bytes]
    fps: float
    #: False plays once and rests on the last frame.
    loop: bool = True


#: Seeded so a visual looks the same every time it is asked for; the
#: generators take `seed=None` for variety when called directly.
VISUALS: dict[str, Visual] = {
    "rainbow": Visual(lambda w, h: rainbow_frames(w, h, 180, 12.0, seed=1), 12.0),
    "life": Visual(lambda w, h: life_frames(w, h, 240, seed=1), 8.0),
    "gradient": Visual(lambda w, h: gradient_frames(w, h, 120), 12.0),
    "beer": Visual(lambda w, h: beer_frames(w, h, 20.0), 20.0, loop=False),
}


@lru_cache(maxsize=16)
def frames(name: str, width: int, height: int) -> bytes:
    """The rendered frames for `name` at this size. Slow the first time."""
    return VISUALS[name].render(width, height)


__all__ = ["VISUALS", "Visual", "frames"]
