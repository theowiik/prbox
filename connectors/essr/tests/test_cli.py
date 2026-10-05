"""The watch loop: what gets announced, when, and what happens on failure."""

from types import SimpleNamespace

import pytest

from essr.cli import MAX_TEXT, build_parser, check, compose, main
from essr.client import BoxError
from essr.feed import Review, Seen


def review(n: int, rating: str | None = "1/3") -> Review:
    return Review(f"guid-{n}", f"Bar {n}", f"https://example/{n}", rating)


class FakeFeed:
    url = "https://example/feed.xml"

    def __init__(self, reviews):
        self.reviews = reviews

    def fetch(self):
        return list(self.reviews)


class FakeBox:
    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    def send_event(self, event):
        if self.fail:
            raise BoxError("box is asleep")
        self.sent.append(event)
        return {"id": "x", "queued": 0}


ARGS = SimpleNamespace(priority="normal", duration=20.0)


@pytest.fixture
def seen(tmp_path):
    return Seen(tmp_path / "seen.json")


def test_first_run_records_the_feed_without_announcing(seen):
    box = FakeBox()
    check(FakeFeed([review(2), review(1)]), seen, box, ARGS)
    assert box.sent == []
    assert "guid-1" in seen and "guid-2" in seen


def test_a_new_review_is_announced_once(seen):
    feed, box = FakeFeed([review(1)]), FakeBox()
    check(feed, seen, box, ARGS)  # first run
    feed.reviews = [review(2), review(1)]
    check(feed, seen, box, ARGS)
    check(feed, seen, box, ARGS)
    assert len(box.sent) == 1
    event = box.sent[0]
    assert event["source"] == "essr"
    assert event["scene"] == {"kind": "text", "text": "Bar 2 1/3"}


def test_several_new_reviews_become_one_event_oldest_first(seen):
    """The box keeps one pending event per source, so a burst must be one send."""
    feed, box = FakeFeed([]), FakeBox()
    check(feed, seen, box, ARGS)
    feed.reviews = [review(3), review(2)]  # feed order: newest first
    check(feed, seen, box, ARGS)
    assert [e["scene"]["text"] for e in box.sent] == ["Bar 2 1/3 | Bar 3 1/3"]


def test_an_unreachable_box_does_not_lose_the_review(seen):
    feed = FakeFeed([])
    check(feed, seen, FakeBox(), ARGS)
    feed.reviews = [review(1)]
    with pytest.raises(BoxError):
        check(feed, seen, FakeBox(fail=True), ARGS)
    assert "guid-1" not in seen

    box = FakeBox()
    check(feed, seen, box, ARGS)
    assert len(box.sent) == 1


def test_long_text_is_truncated_to_what_the_box_accepts():
    text = compose([review(n) for n in range(200)])
    assert len(text) == MAX_TEXT
    assert text.endswith("...")


def test_interval_has_a_floor(capsys):
    assert main(["--interval", "5"]) == 2


def test_defaults():
    args = build_parser().parse_args([])
    assert (args.priority, args.duration, args.interval) == ("normal", 20.0, 300.0)
    assert args.feed == "https://enstorstarkreview.se/feed.xml"
