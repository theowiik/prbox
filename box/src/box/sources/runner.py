"""Polls on-box sources and feeds their output to the scheduler.

This is the piece that makes the box work headless. Previously the dashboard's
JavaScript ran the timer that pushed weather to the panel, so closing the tab
froze the display; now nothing about the box's own content depends on a browser
being open.
"""

import asyncio
import logging

from ..scheduler import Scheduler
from .protocol import Source

logger = logging.getLogger(__name__)


class SourceRunner:
    def __init__(
        self, scheduler: Scheduler, sources: list[Source], interval: float = 60.0
    ) -> None:
        self._scheduler = scheduler
        self._sources = sources
        self._interval = max(interval, 1.0)
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is None and self._sources:
            self._task = asyncio.create_task(self._run(), name="box-sources")

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

    async def poll_once(self) -> None:
        """Refresh every source's ambient card, surviving individual failures.

        `poll()` runs on a worker thread: a real source is a blocking HTTP call,
        and a slow weather API must not freeze the render loop for its timeout.
        The result is submitted back here on the loop, which is the only thread
        allowed to touch the scheduler.
        """
        for source in self._sources:
            try:
                event = await asyncio.to_thread(source.poll)
            except Exception:
                # One broken source must not stop the others or kill the loop.
                logger.exception("Source %r failed to poll", source.name)
                continue
            if event is not None:
                self._scheduler.submit(event)

    async def _run(self) -> None:
        logger.info(
            "Polling %d source(s) every %.0fs", len(self._sources), self._interval
        )
        # The app polls once at startup, so the first wait comes first here.
        while True:
            await asyncio.sleep(self._interval)
            await self.poll_once()
