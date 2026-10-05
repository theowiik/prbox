"""The tail: recent log lines and events, for the debug view.

Reads are open like the rest of the dashboard's reads; clearing the tail is a
write and takes the token.
"""

import asyncio
import logging

from fastapi import APIRouter, Query, Request, WebSocket, WebSocketDisconnect

from ...logs import CAPACITY, LogBuffer, LogEntry
from ..auth import Protected

logger = logging.getLogger(__name__)

router = APIRouter(tags=["logs"])


def _get_logs(request: Request) -> LogBuffer:
    return request.app.state.logs


@router.get("/api/logs", summary="Recent log lines and events")
def get_logs(
    request: Request,
    since: int = Query(0, ge=0, description="Only entries newer than this seq"),
    limit: int = Query(CAPACITY, ge=1, le=CAPACITY),
    channel: str | None = Query(None, pattern="^(log|event)$"),
) -> dict:
    """Poll with `since` — the cursor a client got from its last response."""
    buffer = _get_logs(request)
    entries: list[LogEntry] = buffer.since(since, limit=limit)
    if channel:
        entries = [e for e in entries if e.channel == channel]
    return {"cursor": buffer.cursor, "entries": entries}


@router.delete("/api/logs", summary="Drop the tail", dependencies=[Protected])
def clear_logs(request: Request) -> dict:
    _get_logs(request).clear()
    return {"status": "ok"}


@router.websocket("/ws/logs")
async def stream_logs(websocket: WebSocket) -> None:
    """Backlog first, then every new entry as it is appended."""
    await websocket.accept()
    buffer: LogBuffer = websocket.app.state.logs
    # Subscribe before reading the backlog so nothing appended in between is
    # lost; the client de-duplicates on seq.
    queue = buffer.subscribe()
    try:
        backlog = buffer.since(0)
        await websocket.send_json(
            {
                "type": "hello",
                "cursor": buffer.cursor,
                "entries": [e.model_dump() for e in backlog],
            }
        )
        while True:
            entry = await queue.get()
            await websocket.send_json({"type": "entry", "entry": entry.model_dump()})
    except WebSocketDisconnect, asyncio.CancelledError:
        pass
    except RuntimeError:
        # Socket closed underneath us mid-send; nothing to do but unsubscribe.
        pass
    finally:
        buffer.unsubscribe(queue)
