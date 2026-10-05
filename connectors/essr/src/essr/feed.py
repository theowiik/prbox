"""Reading the En Stor Stark Review feed, and remembering what was announced.

The feed is plain RSS 2.0 with a stable `guid` per review, so "new" simply
means a guid not seen before. Seen guids live in a small JSON file, so a
restart does not re-announce the whole feed and reviews published while this
was not running are still announced once it is.
"""

import json
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import httpx2 as httpx

logger = logging.getLogger(__name__)

FEED_URL = "https://enstorstarkreview.se/feed.xml"

#: Short enough that a slow site never holds the loop up for long.
TIMEOUT = 15.0

#: Seen guids kept on disk. The feed only ever lists its latest reviews, so
#: anything older than this has long since scrolled off it.
MAX_SEEN = 500

#: "Kristinelundsgatan 13, 411 37 Göteborg. Helhetsbetyg: 0/3."
_RATING = re.compile(r"Helhetsbetyg:\s*(\d+)\s*/\s*(\d+)")


class FeedError(RuntimeError):
    """The feed could not be fetched or read. Worth retrying, not dying over."""


@dataclass(frozen=True)
class Review:
    guid: str
    title: str
    link: str
    #: "1/3", or None if the description does not carry one.
    rating: str | None = None

    @property
    def label(self) -> str:
        """What the panel shows for this review."""
        return f"{self.title} {self.rating}" if self.rating else self.title


def parse(xml: bytes) -> list[Review]:
    """Reviews in feed order (newest first). Items without a guid are skipped.

    The standard library parser is fine for a feed: expat has refused
    entity-expansion bombs by default since Python 3.7.1.
    """
    root = ET.fromstring(xml)
    reviews = []
    for item in root.iter("item"):
        guid = (item.findtext("guid") or item.findtext("link") or "").strip()
        title = (item.findtext("title") or "").strip()
        if not guid or not title:
            continue
        match = _RATING.search(item.findtext("description") or "")
        reviews.append(
            Review(
                guid=guid,
                title=title,
                link=(item.findtext("link") or "").strip(),
                rating=f"{match[1]}/{match[2]}" if match else None,
            )
        )
    return reviews


class Feed:
    """Fetches the feed, asking the server to skip the body if nothing changed."""

    def __init__(self, url: str = FEED_URL) -> None:
        self.url = url
        self._etag: str | None = None
        self._reviews: list[Review] = []

    def fetch(self) -> list[Review]:
        """Current reviews, newest first.

        An unchanged feed (304) returns the cached list rather than nothing:
        a review that could not be announced last time — the box was asleep —
        must still look new on the next check.
        """
        headers = {"If-None-Match": self._etag} if self._etag else {}
        try:
            r = httpx.get(
                self.url, headers=headers, timeout=TIMEOUT, follow_redirects=True
            )
            if r.status_code == 304:
                return self._reviews
            r.raise_for_status()
            reviews = parse(r.content)
        except httpx.HTTPError as exc:
            raise FeedError(f"Could not fetch {self.url}: {exc}") from exc
        except ET.ParseError as exc:
            raise FeedError(f"{self.url} is not valid RSS: {exc}") from exc
        # Only after a successful parse: a half-written feed must be fetched
        # again in full next time, not answered with 304.
        self._etag = r.headers.get("etag")
        self._reviews = reviews
        return reviews


class Seen:
    """The guids already announced, persisted between runs."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._guids: list[str] = []
        #: False until the file exists — the very first run.
        self.known = False
        if path.is_file():
            try:
                self._guids = list(json.loads(path.read_text(encoding="utf-8")))
                self.known = True
            except (ValueError, TypeError):
                # A corrupt file is treated as a first run: announcing nothing
                # beats announcing the entire feed at once.
                logger.warning("Ignoring unreadable state file %s", path)

    def __contains__(self, guid: str) -> bool:
        return guid in self._guids

    def add(self, guids: list[str]) -> None:
        self._guids = (self._guids + [g for g in guids if g not in self])[-MAX_SEEN:]
        self.known = True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Write-then-rename, so a crash mid-write cannot leave a corrupt file.
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._guids), encoding="utf-8")
        tmp.replace(self.path)
