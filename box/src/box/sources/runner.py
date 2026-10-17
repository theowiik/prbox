"""Polls on-box sources and feeds their output to the scheduler.

This is the piece that makes the box work headless. Previously the dashboard's
JavaScript ran the timer that pushed weather to the panel, so closing the tab
froze the display; now nothing about the box's own content depends on a browser
being open.

Each source runs on its own loop at its own interval: weather every minute, a
review feed every five. A feed timing out on a dead network must not hold up
the weather, so nothing waits on anything else.
"""

import asyncio
import logging

from ..events import Event, prepare
from ..scheduler import Scheduler
from .protocol import Source

logger = logging.getLogger(__name__)

#: Floor on any source's interval: a typo must not become a hot loop.
MIN_INTERVAL = 1.0


class SourceRunner:
    def __init__(self, scheduler: Scheduler, sources: list[Source]) -> None:
        self._scheduler = scheduler
        self._sources = sources
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """Start every source's loop. Each polls immediately, then on its timer."""
        if self._tasks:
            return
        for source in self._sources:
            self._tasks.append(
                asyncio.create_task(self._run(source), name=f"source-{source.name}")
            )
        if self._sources:
            logger.info(
                "Polling %s",
                ", ".join(f"{s.name} every {s.interval:.0f}s" for s in self._sources),
            )

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def poll_once(self) -> None:
        """Poll every source once, one after another. For tests and tooling."""
        for source in self._sources:
            await self._poll(source)

    def _poll_and_prepare(self, source: Source) -> Event | None:
        """Runs on a worker thread: everything here is allowed to block."""
        event = source.poll()
        if event is not None:
            # A visual takes seconds to render on a Pi; do it here, so the
            # scheduler finds it cached and the render loop never waits.
            prepare(event, self._scheduler.size)
        return event

    async def _poll(self, source: Source) -> None:
        try:
            event = await asyncio.to_thread(self._poll_and_prepare, source)
        except Exception:
            # One broken source must not stop the others or kill its loop.
            logger.exception("Source %r failed to poll", source.name)
            return
        # Back on the loop, which is the only thread allowed to touch the
        # scheduler.
        if event is not None:
            self._scheduler.submit(event)

    async def _run(self, source: Source) -> None:
        interval = max(source.interval, MIN_INTERVAL)
        while True:
            await self._poll(source)
            await asyncio.sleep(interval)
