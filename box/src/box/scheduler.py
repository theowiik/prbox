"""Decides what the panel shows right now.

The render engine draws one scene; this owns *which* scene, so that events from
independent connectors can share a single small display without stomping each
other. It replaces the old last-write-wins controller.

Four tiers, in the order they win the panel:

* ``alarm``   — always takes the panel, interrupting even an alert.
* ``alert``   — takes the panel too, *unless* an instant event is already on it;
  then it waits at the head of the queue and shows next.
* ``normal``  — queued behind any waiting alerts, shown in turn for its duration.
* ``ambient`` — a rotation of background cards, shown whenever nothing is queued.

The split between the two instant tiers is what keeps a burst readable. Three
Discord pings landing in the same second used to mean three quarter-second
glimpses and nothing legible; now the first holds the panel and the rest line
up behind it. An alarm is the deliberate exception that still cuts in.

Ambient is a rotation rather than a single scene because a desk box wants to
cycle weather, then art, then back. Each source owns one card and updates it in
place, so a weather poller refreshes its slot instead of growing the rotation.
"""

import asyncio
import logging
import time
from collections import deque

from .events import PRIORITY_COLORS, Event, Priority, Scheduled, TextSpec, build_scene
from .render.engine import RenderEngine
from .render.scenes import BlankScene, Scene
from .state import PanelState

logger = logging.getLogger(__name__)

#: An interrupted event is requeued only if this much of it is still to come;
#: resuming a notification for half a second reads as a glitch.
MIN_RESUME = 1.5

#: How much of an event's text a log line carries. The panel takes 512.
LOG_SUMMARY = 80


def summarise(spec) -> str:
    """What an event *is*, in a few words: its text, or the kind of scene."""
    return spec.text if isinstance(spec, TextSpec) else spec.kind


class AmbientCard:
    """One slot in the idle rotation, owned by a source."""

    __slots__ = ("source", "scene", "dwell", "label", "color")

    def __init__(
        self,
        source: str,
        scene: Scene,
        dwell: float,
        label: str,
        color: str = PRIORITY_COLORS[Priority.AMBIENT],
    ) -> None:
        self.source = source
        self.scene = scene
        self.dwell = dwell
        self.label = label
        #: Reported in the panel state, so the dashboard can tint the card.
        self.color = color


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

    # -- submitting --------------------------------------------------------

    def submit(self, event: Event, focus: bool = False) -> Scheduled:
        """Accept an event and put it wherever its priority belongs.

        `focus` jumps the ambient rotation straight to this card. Interactive
        choices should feel immediate; a source refreshing on a timer should
        not hijack whatever the rotation is currently on.
        """
        item = Scheduled(event)

        if event.priority is Priority.AMBIENT:
            self._upsert_ambient(item, focus=focus)
            self._log_event(item, "ambient")
            return item

        # One pending item per source: a burst of ten Discord pings should not
        # buy eighty seconds of panel time.
        self._drop_pending_from(item.source)

        self._log_event(item, self._place(item))
        return item

    def _place(self, item: Scheduled) -> str:
        """Put a queued-tier item where its priority says, and name the choice."""
        if item.priority is Priority.ALARM:
            self._preempt(item)
            return "preempt"

        if item.priority is Priority.ALERT:
            current = self._current
            if current is not None and current.priority.rank >= Priority.ALERT.rank:
                # Let the instant event already on the panel be read; this one
                # goes next, ahead of everything ordinary that is waiting.
                self._enqueue(item)
                return "next"
            self._preempt(item)
            return "preempt"

        self._enqueue(item)
        if self._current is None:
            self._activate_next()
        return "queued"

    def _enqueue(self, item: Scheduled) -> None:
        """Insert by rank: alerts wait ahead of normals, FIFO within a tier."""
        rank = item.priority.rank
        for i, queued in enumerate(self._queue):
            if queued.priority.rank < rank:
                self._queue.insert(i, item)
                return
        self._queue.append(item)

    def _log_event(self, item: Scheduled, placement: str) -> None:
        """One line per accepted event, structured so the log view can show it.

        The fields ride on the logging record instead of a second channel, so
        the console and the debug view cannot drift apart.
        """
        logger.info(
            "%-7s %s: %s",
            placement,
            item.source,
            summarise(item.event.scene)[:LOG_SUMMARY],
            extra={
                "box_event": {
                    "source": item.source,
                    "priority": item.priority.value,
                    "duration": item.duration,
                }
            },
        )

    def _drop_pending_from(self, source: str) -> None:
        self._queue = deque(i for i in self._queue if i.source != source)

    def _preempt(self, item: Scheduled) -> None:
        now = time.monotonic()
        current = self._current
        if current is not None and current.remaining(now) >= MIN_RESUME:
            # Put the interrupted event back at the very head with what is left
            # of it — ahead even of same-rank items waiting, since it was
            # halfway through being read.
            current.duration = current.remaining(now)
            current.started_at = None
            self._queue.appendleft(current)
        self._show(item)

    def _upsert_ambient(self, item: Scheduled, focus: bool = False) -> None:
        """Replace this source's ambient card, or append a new one."""
        label = summarise(item.event.scene)
        card = AmbientCard(
            item.source, item.scene, item.duration, label, item.event.effective_color()
        )
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
        while True:
            try:
                self.tick()
            except Exception:
                logger.exception("Scheduler tick failed")
            await asyncio.sleep(0.1)

    # -- introspection -----------------------------------------------------

    def get_state(self) -> PanelState:
        width, height = self._engine.size
        current = self._current
        if current is not None:
            scene_name = current.scene.name
            source = current.source
            priority = current.priority.value
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
            priority = Priority.AMBIENT.value
            text = card.label if card and card.scene.name == "text" else ""
            color = card.color if card else PRIORITY_COLORS[Priority.AMBIENT]
        else:
            scene_name, source, text = "blank", None, ""
            color, priority = PRIORITY_COLORS[Priority.AMBIENT], None

        return PanelState(
            scene=scene_name,
            source=source,
            priority=priority,
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
