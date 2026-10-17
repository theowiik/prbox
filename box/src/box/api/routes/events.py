"""The connector-facing API: one endpoint, one shape.

Everything that wants the panel — a Discord listener on a desktop, a GIF
sender, the box's own weather poller — posts the same Event here. Adding an
integration means writing a curl call, not a client library.
"""

import asyncio

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ... import visuals
from ...events import Event, Priority, prepare
from ...scheduler import Scheduler
from ..auth import Protected

router = APIRouter(prefix="/api/events", tags=["events"])


def _get_scheduler(request: Request) -> Scheduler:
    return request.app.state.scheduler


class Accepted(BaseModel):
    id: str
    source: str
    priority: Priority
    duration: float
    queued: int


# Handlers that touch the scheduler are `async def` on purpose. A plain `def`
# runs in FastAPI's threadpool, where it would mutate the queue while the
# scheduler's own tick reads it on the event loop.


@router.post("", summary="Submit an event", dependencies=[Protected])
async def submit(
    event: Event, scheduler: Scheduler = Depends(_get_scheduler)
) -> Accepted:
    # Rendering a visual can take seconds on a Pi: do it on a worker thread,
    # so the render loop keeps its cadence while the request waits.
    await asyncio.to_thread(prepare, event, scheduler.size)
    item = scheduler.submit(event)
    return Accepted(
        id=item.id,
        source=item.source,
        priority=item.priority,
        duration=item.duration,
        queued=scheduler.queue_depth,
    )


@router.get("/visuals", summary="Built-in visuals a `visual` scene can name")
def list_visuals() -> list[str]:
    return sorted(visuals.VISUALS)


@router.delete("", summary="Drop queued events", dependencies=[Protected])
async def clear(scheduler: Scheduler = Depends(_get_scheduler)) -> dict:
    scheduler.clear()
    return {"status": "ok"}
