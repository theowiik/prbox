"""A ring buffer of recent log lines and events — what the debug view reads.

When the panel shows the wrong thing, the question is always *what did the box
just do*, and answering it meant ssh-ing to the Pi for journalctl. So the box
keeps its own tail: every logging record the process emits, plus a structured
row for each event the scheduler accepts, served over the same API as
everything else.

Events ride the logging pipeline rather than a second channel of their own. The
scheduler already has a logger; attaching the structured fields as
``extra={"box_event": {...}}`` means one path to the console, one path here,
and no way for the two to disagree about what happened.
"""

import asyncio
import logging
import threading
import time
from collections import deque
from typing import Literal

from pydantic import BaseModel

#: How many lines the box remembers. Long enough to cover the last minute of a
#: 30fps loop misbehaving, short enough to stay a rounding error on a Pi.
CAPACITY = 500

Channel = Literal["log", "event"]


class LogEntry(BaseModel):
    """One line in the tail. `seq` is the cursor clients poll with."""

    seq: int
    ts: float
    channel: Channel = "log"
    level: str = "INFO"
    logger: str = "box"
    message: str
    #: Set on `event` rows only — the scheduler's structured fields.
    source: str | None = None
    priority: str | None = None
    duration: float | None = None


class LogBuffer:
    """Bounded tail of entries, with live fan-out to WebSocket subscribers.

    Appends arrive on whatever thread called `logging`, while the subscriber
    queues belong to the event loop, so fan-out is bounced through the loop
    when the two differ.
    """

    def __init__(self, capacity: int = CAPACITY) -> None:
        self._entries: deque[LogEntry] = deque(maxlen=capacity)
        self._lock = threading.Lock()
        self._seq = 0
        self._subscribers: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        """Name the loop that owns the subscriber queues."""
        self._loop = loop

    # -- writing -----------------------------------------------------------

    def append(self, message: str, **fields) -> LogEntry:
        with self._lock:
            self._seq += 1
            entry = LogEntry(
                seq=self._seq,
                ts=fields.pop("ts", time.time()),
                message=message,
                **fields,
            )
            self._entries.append(entry)
        self._publish(entry)
        return entry

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    # -- reading -----------------------------------------------------------

    def since(
        self, seq: int = 0, limit: int = CAPACITY, channel: Channel | None = None
    ) -> list[LogEntry]:
        """Entries newer than `seq`, oldest first, most recent `limit` of them.

        `channel` filters before `limit` applies, so asking for the last 50
        events returns 50 events rather than whichever ones were among the
        last 50 lines.
        """
        with self._lock:
            newer = [
                e
                for e in self._entries
                if e.seq > seq and (channel is None or e.channel == channel)
            ]
        return newer[-limit:] if limit > 0 else []

    @property
    def cursor(self) -> int:
        """Sequence number of the newest entry ever appended."""
        with self._lock:
            return self._seq

    # -- live fan-out ------------------------------------------------------

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def _publish(self, entry: LogEntry) -> None:
        loop = self._loop
        if loop is None or not self._subscribers:
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            self._fanout(entry)
        else:
            try:
                loop.call_soon_threadsafe(self._fanout, entry)
            except RuntimeError:
                # Loop already closed — a log line during shutdown.
                pass

    def _fanout(self, entry: LogEntry) -> None:
        for queue in self._subscribers:
            if queue.full():
                # A stalled tab must not be able to stall the render loop.
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(entry)
            except asyncio.QueueFull:
                pass


class BufferHandler(logging.Handler):
    """Feeds every logging record into a LogBuffer."""

    def __init__(self, buffer: LogBuffer) -> None:
        super().__init__()
        self._buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        try:
            event = getattr(record, "box_event", None)
            self._buffer.append(
                # format() rather than getMessage(): it appends the traceback
                # of an exc_info record, which is the whole point of having a
                # log view when a display backend starts throwing.
                self.format(record),
                ts=record.created,
                channel="event" if event else "log",
                level=record.levelname,
                logger=record.name,
                **(event or {}),
            )
        except Exception:
            # A malformed log line must never take the box down with it.
            self.handleError(record)


def install(buffer: LogBuffer, level: int = logging.INFO) -> BufferHandler:
    """Tee the root logger into `buffer`. Returns the handler, to remove later."""
    handler = BufferHandler(buffer)
    handler.setLevel(level)
    root = logging.getLogger()
    # The root logger defaults to WARNING, which would starve the tail of the
    # INFO lines it exists for — whoever else configured logging, or didn't.
    if root.getEffectiveLevel() > level:
        root.setLevel(level)
    root.addHandler(handler)
    return handler


def uninstall(handler: BufferHandler) -> None:
    logging.getLogger().removeHandler(handler)
