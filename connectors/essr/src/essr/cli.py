"""essr — show new En Stor Stark Review reviews on your box.

Unlike the other connectors this one keeps running: it polls the feed and
sends an event whenever a review appears that it has not announced before.
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from .client import BoxClient, BoxError, box_url, load_dotenv
from .feed import FEED_URL, Feed, FeedError, Review, Seen

log = logging.getLogger("essr")

#: The feed sends `Cache-Control: max-age=300`; polling faster gains nothing.
DEFAULT_INTERVAL = 300.0
MIN_INTERVAL = 60.0

#: The box caps event text at 512 characters.
MAX_TEXT = 512


def default_state() -> Path:
    return Path.home() / ".local" / "state" / "box" / "essr.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="essr",
        description="Show new En Stor Stark Review reviews on your box.",
        epilog=(
            "The first run only records what is already in the feed; from then "
            "on each new review is sent once. Use --latest to see it work now."
        ),
    )
    parser.add_argument(
        "--url", help="box base URL (default: http://localhost:8000, env: BOX_URL)"
    )
    parser.add_argument(
        "--token",
        default=os.getenv("BOX_TOKEN"),
        help="bearer token, if the box requires one (env: BOX_TOKEN)",
    )
    parser.add_argument("--feed", default=FEED_URL, help="feed URL")
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help=f"seconds between checks (default: {DEFAULT_INTERVAL:.0f})",
    )
    parser.add_argument(
        "--priority",
        choices=("ambient", "normal", "alert", "alarm"),
        default="normal",
        help="how insistently to claim the panel (default: normal)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=20.0,
        help="seconds to hold the panel; long names need time to scroll (default: 20)",
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=default_state(),
        help="where announced reviews are remembered (default: %(default)s)",
    )
    parser.add_argument(
        "--once", action="store_true", help="check once and exit, e.g. from cron"
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="send the newest review right away, announced or not, then exit",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def compose(reviews: list[Review]) -> str:
    """One line of panel text for one or more reviews, oldest first.

    Several reviews become one event, not several: the box keeps one pending
    event per source, so separate sends would leave only the last on screen.
    """
    text = " | ".join(r.label for r in reversed(reviews))
    return text if len(text) <= MAX_TEXT else text[: MAX_TEXT - 3] + "..."


def announce(client: BoxClient, reviews: list[Review], args) -> None:
    client.send_event(
        {
            "source": "essr",
            "priority": args.priority,
            "duration": args.duration,
            "scene": {"kind": "text", "text": compose(reviews)},
        }
    )
    for review in reviews:
        log.info("Sent: %s  %s", review.label, review.link)


def check(feed: Feed, seen: Seen, client: BoxClient, args) -> None:
    """One poll: fetch, work out what is new, announce it, remember it."""
    reviews = feed.fetch()
    if not seen.known:
        # First run: everything in the feed is old news. Announcing twenty
        # reviews at once would be noise, not a notification.
        seen.add([r.guid for r in reviews])
        log.info("Watching %s: %d existing reviews noted", feed.url, len(reviews))
        return

    new = [r for r in reviews if r.guid not in seen]
    if not new:
        log.debug("No new reviews")
        return
    # Remembered only once the box has accepted them: if it is unreachable,
    # the same reviews are tried again next time rather than lost.
    announce(client, new, args)
    seen.add([r.guid for r in new])


def main(argv: list[str] | None = None) -> int:
    # Before the parser: --token defaults to BOX_TOKEN, which a .env may set.
    load_dotenv()
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S"
    )
    # httpx logs every request at INFO, which is noise for a polling loop.
    for chatty in ("httpx2", "httpcore2"):
        logging.getLogger(chatty).setLevel(logging.WARNING)
    if args.verbose:
        log.setLevel(logging.DEBUG)

    if args.interval < MIN_INTERVAL:
        log.error("--interval must be at least %.0f seconds", MIN_INTERVAL)
        return 2

    client = BoxClient(box_url(args.url), args.token)
    feed = Feed(args.feed)

    if args.latest:
        try:
            reviews = feed.fetch()
            if not reviews:
                log.error("The feed has no reviews")
                return 1
            announce(client, reviews[:1], args)
        except (BoxError, FeedError) as exc:
            log.error("%s", exc)
            return 1
        return 0

    seen = Seen(args.state)
    try:
        while True:
            try:
                check(feed, seen, client, args)
            except (BoxError, FeedError) as exc:
                # The box is asleep or the site is down: say so and try again
                # next time. A long-running watcher must not die on a blip.
                if args.once:
                    log.error("%s", exc)
                    return 1
                log.warning("%s", exc)
            if args.once:
                return 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
