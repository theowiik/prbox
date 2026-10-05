"""Parsing the feed and remembering what was announced."""

from essr.feed import MAX_SEEN, Seen, parse

#: Trimmed from the real feed, Swedish characters and all.
FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
<title>En Stor Stark Review</title>
<item>
<title>Bistro Löfqvist å Vi</title>
<link>https://enstorstarkreview.se/bistro-lofqvist-a-vi</link>
<description>Västra Hamngatan 15, 411 17 Göteborg. Helhetsbetyg: 1/3.</description>
<guid isPermaLink="false">enstorstarkreview:review:b</guid>
</item>
<item>
<title>Beerista</title>
<link>https://enstorstarkreview.se/beerista</link>
<description>Kristinelundsgatan 13, 411 37 Göteborg. Helhetsbetyg: 0/3.</description>
<guid isPermaLink="false">enstorstarkreview:review:a</guid>
</item>
<item>
<title>No rating yet</title>
<link>https://enstorstarkreview.se/x</link>
<description>Somewhere.</description>
<guid>enstorstarkreview:review:c</guid>
</item>
<item><title>No guid or link</title></item>
</channel>
</rss>""".encode()


def test_parse_reads_titles_ratings_and_guids():
    reviews = parse(FEED)
    assert [r.title for r in reviews] == [
        "Bistro Löfqvist å Vi",
        "Beerista",
        "No rating yet",
    ]
    assert reviews[0].rating == "1/3"
    assert reviews[0].guid == "enstorstarkreview:review:b"
    assert reviews[0].link.endswith("/bistro-lofqvist-a-vi")


def test_label_includes_the_rating_when_there_is_one():
    reviews = parse(FEED)
    assert reviews[1].label == "Beerista 0/3"
    assert reviews[2].label == "No rating yet"


def test_first_run_is_unknown(tmp_path):
    assert not Seen(tmp_path / "seen.json").known


def test_seen_survives_a_restart(tmp_path):
    path = tmp_path / "nested" / "seen.json"
    Seen(path).add(["a", "b"])
    again = Seen(path)
    assert again.known
    assert "a" in again and "b" in again and "c" not in again


def test_seen_is_bounded(tmp_path):
    seen = Seen(tmp_path / "seen.json")
    seen.add([str(i) for i in range(MAX_SEEN + 10)])
    assert "0" not in seen
    assert str(MAX_SEEN + 9) in seen


def test_corrupt_state_counts_as_a_first_run(tmp_path):
    path = tmp_path / "seen.json"
    path.write_text("{not json", encoding="utf-8")
    assert not Seen(path).known
