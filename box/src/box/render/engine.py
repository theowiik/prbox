"""The render loop: drives scenes at a fixed frame rate and fans frames out."""

import asyncio
import logging
import time

from .frame import Frame
from .scenes import BlankScene, Scene

logger = logging.getLogger(__name__)

#: Crossfade duration when switching scenes, in seconds.
TRANSITION = 0.35


def _gamma_lut(brightness: float, gamma: float) -> bytes:
    """Map linear 0-255 values to what an LED needs to *look* linear."""
    brightness = min(max(brightness, 0.0), 1.0)
    return bytes(
        int(((v / 255.0) ** gamma) * brightness * 255.0 + 0.5) for v in range(256)
    )


#: `_SCALE[a][v]` is `v * a / 255`, rounded — one translate table per weight.
_SCALE: tuple[bytes, ...] = tuple(
    bytes((v * a + 127) // 255 for v in range(256)) for a in range(256)
)


def _crossfade(cur: bytearray, old: bytearray, alpha: int) -> None:
    """Blend `old` into `cur` in place, `cur` weighted `alpha`/255.

    The per-byte loop this replaces was the costliest thing a Pi did all
    frame. Both scaled buffers come out of `bytes.translate` (C speed), then
    are added as two big integers. That never carries from one byte into the
    next: if both inputs are below 255 the blend is at most 254 and the two
    roundings add at most 1; if either is 255 its half is exact.
    """
    a = cur.translate(_SCALE[alpha])
    b = old.translate(_SCALE[255 - alpha])
    total = int.from_bytes(a) + int.from_bytes(b)
    cur[:] = total.to_bytes(len(cur))


class RenderEngine:
    """Renders the active scene into frames and pushes them to a display.

    Runs as a single asyncio task on a fixed-interval clock so the LED matrix
    gets an even frame cadence — uneven pacing is what reads as "choppy" on
    hardware, more than the raw frame rate does.
    """

    def __init__(
        self,
        display,
        width: int,
        height: int,
        fps: int = 30,
        gamma: float = 2.2,
    ) -> None:
        self._display = display
        self._fps = max(1, fps)
        self._gamma = gamma
        self._brightness = 1.0
        self._lut = _gamma_lut(self._brightness, gamma)

        self._scene: Scene = BlankScene()
        self._scene_started = 0.0
        self._prev: Scene | None = None
        self._prev_started = 0.0
        self._transition_started = 0.0

        self._frame = Frame(width, height)
        self._prev_frame = Frame(width, height)
        self._output = bytearray(width * height * 3)

        self._task: asyncio.Task | None = None
        self._subscribers: set[asyncio.Queue] = set()
        self._frame_index = 0

    # -- lifecycle ---------------------------------------------------------

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="box-render")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    # -- control -----------------------------------------------------------

    @property
    def scene(self) -> Scene:
        return self._scene

    @property
    def brightness(self) -> float:
        return self._brightness

    @property
    def fps(self) -> int:
        return self._fps

    @property
    def size(self) -> tuple[int, int]:
        return (self._frame.width, self._frame.height)

    def set_scene(self, scene: Scene, *, fade: bool = True) -> None:
        """Switch scenes, crossfading from the current one unless told not to."""
        now = time.monotonic()
        if fade and TRANSITION > 0:
            self._prev = self._scene
            self._prev_started = self._scene_started
            self._transition_started = now
        else:
            self._prev = None
        self._scene = scene
        self._scene_started = now

    def set_brightness(self, brightness: float) -> None:
        if not 0.0 <= brightness <= 1.0:
            raise ValueError("Brightness must be between 0.0 and 1.0")
        self._brightness = brightness
        self._lut = _gamma_lut(brightness, self._gamma)

    # -- frame distribution ------------------------------------------------

    def subscribe(self) -> asyncio.Queue:
        """A queue that receives the latest frame bytes, dropping stale ones."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=1)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def latest_frame(self) -> bytes:
        return bytes(self._output)

    # -- internals ---------------------------------------------------------

    def _compose(self, now: float) -> None:
        """Render the active scene (crossfading the outgoing one) into _frame."""
        self._scene.render(self._frame, now - self._scene_started)

        if self._prev is not None:
            progress = (now - self._transition_started) / TRANSITION
            if progress >= 1.0:
                self._prev = None
            else:
                self._prev.render(self._prev_frame, now - self._prev_started)
                _crossfade(self._frame.buf, self._prev_frame.buf, int(progress * 255))

    def _emit(self) -> None:
        """Gamma-correct the frame, hand it to the display, notify subscribers."""
        out = self._output
        out[:] = self._frame.buf.translate(self._lut)

        try:
            self._display.push_frame(out)
        except Exception:
            logger.exception("Display rejected a frame")

        if not self._subscribers:
            return
        payload = bytes(out)
        for queue in self._subscribers:
            if queue.full():
                # Slow client: drop the frame it never read rather than block.
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    async def _run(self) -> None:
        interval = 1.0 / self._fps
        loop = asyncio.get_running_loop()
        next_tick = loop.time()
        logger.info("Render loop started at %d fps", self._fps)
        try:
            while True:
                self._compose(time.monotonic())
                self._emit()
                self._frame_index += 1

                next_tick += interval
                delay = next_tick - loop.time()
                if delay < -interval:
                    # Fell far behind (slow Pi, big panel): resync instead of
                    # trying to catch up with a burst of frames.
                    next_tick = loop.time() + interval
                    delay = interval
                await asyncio.sleep(max(delay, 0.0))
        except asyncio.CancelledError:
            logger.info("Render loop stopped after %d frames", self._frame_index)
            raise
