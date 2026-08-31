"""Decides what the panel shows right now.

The render engine draws one scene; this owns *which* scene, so that events from
independent connectors can share a single small display without stomping each
other. It replaces the old last-write-wins controller.

Three tiers, in the order they win the panel:

* ``alert``   — takes the panel immediately; whatever was showing is put back.
* ``normal``  — queued, shown in turn for its duration.
* ``ambient`` — a rotation of background cards, shown whenever nothing is queued.

Ambient is a rotation rather than a single scene because a desk box wants to
cycle weather, then art, then back. Each source owns one card and updates it in
place, so a weather poller refreshes its slot instead of growing the rotation.
"""

import asyncio
import logging
import time
from collections import deque

from .events import Event, Priority, Scheduled, TextSpec, build_scene
from .render.engine import RenderEngine
from .render.scenes import BlankScene, Scene
from .state import PanelState

logger = logging.getLogger(__name__)

#: An interrupted event is requeued only if this much of it is still to come;
#: resuming a notification for half a second reads as a glitch.
MIN_RESUME = 1.5


class AmbientCard:
    """One slot in the idle rotation, owned by a source."""

    __slots__ = ("source", "scene", "dwell", "label")

    def __init__(self, source: str, scene: Scene, dwell: float, label: str) -> None:
        self.source = source
        self.scene = scene
        self.dwell = dwell
        self.label = label


class Scheduler:
    def __init__(self, engine: RenderEngine) -> None:
        self._engine = engine
        self._queue: deque[Scheduled] = deque()
        self._current: Scheduled | None = None

        self._ambient: list[AmbientCard] = []
        self._ambient_index = 0
        self._ambient_started = 0.0
        self._ambient_showing: str | None = None

        self._task: asyncio.Task | None = None
        self._accepted = 0
        self._dropped = 0

    # -- lifecycle ---------------------------------------------------------

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="box-scheduler")

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

    @property
    def queue_depth(self) -> int:
        return len(self._queue)

    @property
    def current_source(self) -> str | None:
        return self._current.source if self._current else self._ambient_showing

    # -- submitting --------------------------------------------------------

    def submit(self, event: Event, focus: bool = False) -> Scheduled:
        """Accept an event and put it wherever its priority belongs.

        `focus` jumps the ambient rotation straight to this card. Interactive
        choices should feel immediate; a source refreshing on a timer should
        not hijack whatever the rotation is currently on.
        """
        item = Scheduled(event)
        self._accepted += 1

        if event.priority is Priority.AMBIENT:
            self._upsert_ambient(item, focus=focus)
            return item

        # One pending item per source: a burst of ten Discord pings should not
        # buy eighty seconds of panel time.
        self._drop_pending_from(item.source)

        if event.priority is Priority.ALERT:
            self._preempt(item)
        else:
            self._queue.append(item)
            if self._current is None:
                self._activate_next()
        return item

    def _drop_pending_from(self, source: str) -> None:
        before = len(self._queue)
        self._queue = deque(i for i in self._queue if i.source != source)
        self._dropped += before - len(self._queue)

    def _preempt(self, item: Scheduled) -> None:
        now = time.monotonic()
        current = self._current
        if current is not None and current.remaining(now) >= MIN_RESUME:
            # Put the interrupted event back at the head with what is left of it.
            current.duration = current.remaining(now)
            current.started_at = None
            self._queue.appendleft(current)
        self._show(item)

    def _upsert_ambient(self, item: Scheduled, focus: bool = False) -> None:
        """Replace this source's ambient card, or append a new one."""
        label = (
            item.event.scene.text
            if isinstance(item.event.scene, TextSpec)
            else item.event.scene.kind
        )
        card = AmbientCard(item.source, item.scene, item.duration, label)
        for i, existing in enumerate(self._ambient):
            if existing.source == card.source:
                self._ambient[i] = card
                # Refresh in place without disturbing where the rotation is.
                if focus or self._ambient_showing == card.source:
                    self._focus_ambient(i)
                return
        self._ambient.append(card)
        if focus or (self._current is None and len(self._ambient) == 1):
            self._focus_ambient(len(self._ambient) - 1)

    def _focus_ambient(self, index: int) -> None:
        """Put a specific ambient card on screen and restart its dwell."""
        card = self._ambient[index]
        self._ambient_index = index
        self._ambient_showing = card.source
        self._ambient_started = time.monotonic()
        if self._current is None:
            self._engine.set_scene(card.scene)

    def clear(self) -> None:
        """Drop everything queued and fall back to ambient."""
        self._queue.clear()
        self._current = None
        self._show_ambient(force=True)

    def clear_ambient(self) -> None:
        self._ambient.clear()
        self._ambient_showing = None
        if self._current is None:
            self._engine.set_scene(BlankScene())

    # -- the loop ----------------------------------------------------------

    def _show(self, item: Scheduled) -> None:
        item.start()
        self._current = item
        self._ambient_showing = None
        self._engine.set_scene(item.scene)

    def _activate_next(self) -> bool:
        if not self._queue:
            return False
        self._show(self._queue.popleft())
        return True

    def _show_ambient(self, force: bool = False) -> None:
        """Show the current ambient card, advancing when its dwell is up."""
        if not self._ambient:
            if force or self._ambient_showing is not None:
                self._ambient_showing = None
                self._engine.set_scene(BlankScene())
            return

        now = time.monotonic()
        self._ambient_index %= len(self._ambient)
        card = self._ambient[self._ambient_index]

        if force or self._ambient_showing is None:
            self._ambient_showing = card.source
            self._ambient_started = now
            self._engine.set_scene(card.scene)
            return

        if now - self._ambient_started >= card.dwell:
            self._ambient_index = (self._ambient_index + 1) % len(self._ambient)
            card = self._ambient[self._ambient_index]
            self._ambient_showing = card.source
            self._ambient_started = now
            self._engine.set_scene(card.scene)

    def tick(self) -> None:
        now = time.monotonic()
        if self._current is not None:
            if not self._current.expired(now):
                return
            self._current = None
            if self._activate_next():
                return
            self._show_ambient(force=True)
            return
        self._show_ambient()

    async def _run(self) -> None:
        # Ten hertz is far finer than any dwell time and costs nothing; the
        # render loop stays untouched so it can hold its frame cadence.
        try:
            while True:
                try:
                    self.tick()
                except Exception:
                    logger.exception("Scheduler tick failed")
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            raise

    # -- introspection -----------------------------------------------------

    def get_state(self) -> PanelState:
        width, height = self._engine.size
        current = self._current
        if current is not None:
            scene_name = current.scene.name
            source = current.source
            text = (
                current.event.scene.text
                if isinstance(current.event.scene, TextSpec)
                else ""
            )
            color = current.event.effective_color()
        elif self._ambient_showing is not None:
            card = next(
                (c for c in self._ambient if c.source == self._ambient_showing), None
            )
            scene_name = card.scene.name if card else "blank"
            source = self._ambient_showing
            text = card.label if card and card.scene.name == "text" else ""
            color = "#00FF00"
        else:
            scene_name, source, text, color = "blank", None, "", "#00FF00"

        return PanelState(
            scene=scene_name,
            source=source,
            text=text,
            color=color,
            brightness=self._engine.brightness,
            width=width,
            height=height,
            fps=self._engine.fps,
            queued=len(self._queue),
            ambient=[c.source for c in self._ambient],
        )

    # -- direct control, for the dashboard ---------------------------------

    def set_brightness(self, brightness: float) -> None:
        self._engine.set_brightness(brightness)

    def set_ambient_scene(self, source: str, scene: Scene, dwell: float = 12.0) -> None:
        """Install an ambient card directly, bypassing the event path."""
        card = AmbientCard(source, scene, dwell, scene.name)
        for i, existing in enumerate(self._ambient):
            if existing.source == source:
                self._ambient[i] = card
                if self._ambient_showing == source:
                    self._engine.set_scene(scene)
                return
        self._ambient.append(card)
        if self._current is None:
            self._show_ambient(force=True)


__all__ = ["AmbientCard", "Scheduler", "build_scene"]
