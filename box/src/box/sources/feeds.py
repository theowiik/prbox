"""RSS and Atom feeds, polled on the box.

A feed needs nothing but the internet, so it runs here rather than as a
connector: no extra process to keep alive, and it keeps working while every
other machine sleeps.

Adding a feed is one line in `FEEDS`. `show` is what a new item looks like on
the panel: `"title"` scrolls the item titles, or name a visual (`"beer"`) to
play it instead — a panel this small reads an animation from across the room.

"New" means a guid not seen before. Seen guids are kept on disk, so a restart
does not re-announce the feed, and the very first poll only records what is
already there: starting the box must not flood the panel with old items.
"""

import json
import logging
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .. import visuals
from ..events import Event, Priority, TextSpec, VisualSpec

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FeedConfig:
    #: The event source: picks the colour, names log lines, coalesces bursts.
    name: str
    url: str
    #: "title", or the name of a visual to play instead of any text.
    show: str = "title"
    #: Seconds between polls. Five minutes suits most feeds' own cache lifetime.
    interval: float = 300.0
    priority: Priority = Priority.NORMAL
    #: Seconds on the panel; None takes the priority's default.
    duration: float | None = None


#: The feeds this box follows.
FEEDS: tuple[FeedConfig, ...] = (
    # En Stor Stark Review: a new bar review pours a pint.
    FeedConfig(
        name="essr",
        url="https://enstorstarkreview.se/feed.xml",
        show="beer",
    ),
)

#: A slow site must not tie up a worker thread for long.
TIMEOUT = 15.0

#: Seen guids kept on disk. Feeds list only their latest items, so anything
#: older than this has long since scrolled off.
MAX_SEEN = 500

#: The box caps event text at 512 characters.
MAX_TEXT = 512

_ATOM = "{http://www.w3.org/2005/Atom}"


class FeedError(RuntimeError):
    """The feed could not be fetched or read. Worth retrying, not dying over."""


@dataclass(frozen=True)
class Item:
    guid: str
    title: str
    link: str = ""


def parse(xml: bytes) -> list[Item]:
    """Items in feed order (newest first, by convention), RSS 2.0 or Atom.

    Items with no id or no title are skipped. The standard library parser is
    safe for this: expat has refused entity-expansion bombs since 3.7.1.
    """
    root = ET.fromstring(xml)
    items = []
    for node in root.iter("item"):  # RSS 2.0
        link = (node.findtext("link") or "").strip()
        guid = (node.findtext("guid") or link).strip()
        title = (node.findtext("title") or "").strip()
        if guid and title:
            items.append(Item(guid, title, link))
    for node in root.iter(f"{_ATOM}entry"):  # Atom
        link_el = node.find(f"{_ATOM}link")
        link = link_el.get("href", "") if link_el is not None else ""
        guid = (node.findtext(f"{_ATOM}id") or link).strip()
        title = (node.findtext(f"{_ATOM}title") or "").strip()
        if guid and title:
            items.append(Item(guid, title, link))
    return items


class Seen:
    """The guids already shown, persisted between runs."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._guids: list[str] = []
        #: False until the file exists — the very first poll.
        self.known = False
        if path.is_file():
            try:
                self._guids = list(json.loads(path.read_text(encoding="utf-8")))
                self.known = True
            except ValueError, TypeError:
                # Treated as a first run: showing nothing beats showing the
                # entire feed at once.
                logger.warning("Ignoring unreadable state file %s", path)

    def __contains__(self, guid: str) -> bool:
        return guid in self._guids

    def add(self, guids: list[str]) -> None:
        self._guids = (self._guids + [g for g in guids if g not in self])[-MAX_SEEN:]
        self.known = True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Write-then-rename, so a crash mid-write cannot leave a corrupt file —
        # on a Pi that loses power, this matters.
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._guids), encoding="utf-8")
        tmp.replace(self.path)


class FeedSource:
    """One feed, as an on-box source. `poll()` runs on a worker thread."""

    def __init__(self, config: FeedConfig, state_dir: Path) -> None:
        if config.show != "title" and config.show not in visuals.VISUALS:
            raise ValueError(
                f"feed {config.name!r}: show must be 'title' or one of "
                f"{sorted(visuals.VISUALS)}, got {config.show!r}"
            )
        self.config = config
        self.name = config.name
        self.interval = config.interval
        self._seen = Seen(state_dir / f"feed-{config.name}.json")
        self._etag: str | None = None
        self._items: list[Item] = []

    def fetch(self) -> list[Item]:
        """Current items. An unchanged feed (304) answers from the last fetch."""
        request = urllib.request.Request(
            self.config.url, headers={"User-Agent": "box (LED display)"}
        )
        if self._etag:
            request.add_header("If-None-Match", self._etag)
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                body = response.read()
                etag = response.headers.get("ETag")
            items = parse(body)
        except urllib.error.HTTPError as exc:
            if exc.code == 304:
                return self._items
            raise FeedError(f"{self.config.url} returned {exc.code}") from exc
        except (OSError, ET.ParseError) as exc:
            # URLError and timeouts are OSErrors.
            raise FeedError(f"Could not read {self.config.url}: {exc}") from exc
        # Only after a good parse: a half-written feed is fetched in full again.
        self._etag = etag
        self._items = items
        return items

    def poll(self) -> Event | None:
        try:
            items = self.fetch()
        except FeedError as exc:
            # The network is down or the site is: say so, try next interval.
            logger.warning("%s", exc)
            return None

        if not self._seen.known:
            self._seen.add([i.guid for i in items])
            logger.info("Following %s: %d items noted", self.name, len(items))
            return None

        new = [i for i in items if i.guid not in self._seen]
        if not new:
            return None
        self._seen.add([i.guid for i in new])
        for item in new:
            logger.info("New in %s: %s %s", self.name, item.title, item.link)
        return self.event(new)

    def event(self, new: list[Item]) -> Event:
        """One event for everything new: the box keeps one pending per source,
        so separate events would leave only the last on screen."""
        if self.config.show == "title":
            text = " | ".join(i.title for i in reversed(new))  # oldest first
            if len(text) > MAX_TEXT:
                text = text[: MAX_TEXT - 3] + "..."
            scene = TextSpec(text=text)
        else:
            scene = VisualSpec(name=self.config.show)
        return Event(
            source=self.name,
            scene=scene,
            priority=self.config.priority,
            duration=self.config.duration,
        )
