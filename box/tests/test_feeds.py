"""On-box feeds: parsing, what counts as new, and fetching over real HTTP."""

import http.server
import threading

import pytest

from box.events import TextSpec, VisualSpec
from box.sources.feeds import MAX_SEEN, FeedConfig, FeedSource, Item, Seen, parse

#: Trimmed from the real En Stor Stark Review feed, Swedish characters and all.
RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>En Stor Stark Review</title>
<item>
<title>Bistro Löfqvist å Vi</title>
<link>https://enstorstarkreview.se/bistro-lofqvist-a-vi</link>
<guid isPermaLink="false">enstorstarkreview:review:b</guid>
</item>
<item>
<title>Beerista</title>
<link>https://enstorstarkreview.se/beerista</link>
<guid isPermaLink="false">enstorstarkreview:review:a</guid>
</item>
<item><title>No guid or link</title></item>
</channel></rss>""".encode()

ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry><id>tag:x,1</id><title>Release 1.2</title>
<link href="https://example.com/1.2"/></entry>
</feed>"""


# -- parsing -------------------------------------------------------------------


def test_rss_items_in_feed_order():
    items = parse(RSS)
    assert [i.title for i in items] == ["Bistro Löfqvist å Vi", "Beerista"]
    assert items[0].guid == "enstorstarkreview:review:b"


def test_atom_entries():
    assert parse(ATOM) == [Item("tag:x,1", "Release 1.2", "https://example.com/1.2")]


# -- what is new ---------------------------------------------------------------


class StubFeed(FeedSource):
    """A FeedSource whose fetch returns whatever the test sets."""

    items: list[Item] = []

    def fetch(self):
        return list(self.items)


def item(n: int) -> Item:
    return Item(f"guid-{n}", f"Bar {n}")


@pytest.fixture
def feed(tmp_path):
    return StubFeed(FeedConfig("essr", "http://unused", show="title"), tmp_path)


def test_first_poll_records_without_showing_anything(feed):
    feed.items = [item(2), item(1)]
    assert feed.poll() is None


def test_a_new_item_is_shown_once(feed):
    feed.items = [item(1)]
    feed.poll()
    feed.items = [item(2), item(1)]
    event = feed.poll()
    assert event.source == "essr"
    assert event.scene == TextSpec(text="Bar 2")
    assert feed.poll() is None


def test_a_burst_is_one_event_oldest_first(feed):
    """The box keeps one pending event per source, so a burst must be one."""
    feed.poll()
    feed.items = [item(3), item(2)]
    assert feed.poll().scene.text == "Bar 2 | Bar 3"


def test_a_feed_can_play_a_visual_instead_of_text(tmp_path):
    feed = StubFeed(FeedConfig("essr", "http://unused", show="beer"), tmp_path)
    feed.poll()
    feed.items = [item(1)]
    assert feed.poll().scene == VisualSpec(name="beer")


def test_seen_survives_a_restart(tmp_path):
    first = StubFeed(FeedConfig("essr", "http://unused"), tmp_path)
    first.items = [item(1)]
    first.poll()
    again = StubFeed(FeedConfig("essr", "http://unused"), tmp_path)
    again.items = [item(1)]
    assert again.poll() is None, "already seen before the restart"


def test_unknown_show_fails_at_startup(tmp_path):
    with pytest.raises(ValueError, match="show must be"):
        FeedSource(FeedConfig("x", "http://unused", show="fireworks"), tmp_path)


def test_seen_is_bounded(tmp_path):
    seen = Seen(tmp_path / "seen.json")
    seen.add([str(i) for i in range(MAX_SEEN + 10)])
    assert "0" not in seen and str(MAX_SEEN + 9) in seen


def test_corrupt_state_counts_as_a_first_run(tmp_path):
    path = tmp_path / "seen.json"
    path.write_text("{not json", encoding="utf-8")
    assert not Seen(path).known


# -- over HTTP -----------------------------------------------------------------


@pytest.fixture
def server():
    """A local feed server that honours ETags, and counts full responses."""
    state = {"full": 0, "body": RSS, "fail": False}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if state["fail"]:
                self.send_response(503)
                self.end_headers()
                return
            etag = f'"{hash(state["body"])}"'
            if self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                self.end_headers()
                return
            state["full"] += 1
            self.send_response(200)
            self.send_header("ETag", etag)
            self.end_headers()
            self.wfile.write(state["body"])

        def log_message(self, *args):
            pass

    httpd = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}/feed.xml", state
    httpd.shutdown()


def test_an_unchanged_feed_is_not_downloaded_again(server, tmp_path):
    url, state = server
    feed = FeedSource(FeedConfig("essr", url), tmp_path)
    assert len(feed.fetch()) == 2
    assert len(feed.fetch()) == 2, "a 304 answers from the last fetch"
    assert state["full"] == 1


def test_a_failing_site_is_a_quiet_none_not_a_crash(server, tmp_path):
    url, state = server
    state["fail"] = True
    assert FeedSource(FeedConfig("essr", url), tmp_path).poll() is None
