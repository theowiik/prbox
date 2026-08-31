"""gifcast — send a GIF to your box."""

import argparse
import logging
import os
import sys
from pathlib import Path

from .client import PrboxClient, PrboxError
from .convert import convert

DEFAULT_URL = os.getenv("BOX_URL", "http://box:8000")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gifcast",
        description="Send a GIF to your box.",
        epilog=(
            "The GIF is decoded and resized here, so the box only receives raw "
            "pixels. Panel size is read from the box unless --size is given."
        ),
    )
    parser.add_argument(
        "gif", type=Path, help="path to a .gif (or any image PIL reads)"
    )
    parser.add_argument(
        "--url", default=DEFAULT_URL, help=f"box base URL (default: {DEFAULT_URL})"
    )
    parser.add_argument(
        "--token",
        default=os.getenv("BOX_TOKEN"),
        help="bearer token, if the box requires one (env: BOX_TOKEN)",
    )
    parser.add_argument(
        "--size",
        metavar="WxH",
        help="override the panel size instead of asking the box, e.g. 32x32",
    )
    parser.add_argument(
        "--crop",
        action="store_true",
        help="fill the panel and crop, instead of letterboxing",
    )
    parser.add_argument("--fps", type=float, help="override playback rate")
    parser.add_argument(
        "--max-frames",
        type=int,
        default=120,
        help="stop after this many frames (default: 120)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="seconds to hold the panel (default: 10)",
    )
    parser.add_argument(
        "--priority",
        choices=("ambient", "normal", "alert"),
        default="normal",
        help="how insistently to claim the panel (default: normal)",
    )
    parser.add_argument("--source", default="gifcast", help="source name for the event")
    parser.add_argument(
        "--once", action="store_true", help="play through once instead of looping"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def parse_size(text: str) -> tuple[int, int]:
    try:
        w, h = text.lower().split("x", 1)
        return int(w), int(h)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--size must look like 32x32, got {text!r}"
        ) from exc


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # httpx logs every request at INFO, which is noise for a one-shot CLI.
    for chatty in ("httpx2", "httpcore2", "PIL"):
        logging.getLogger(chatty).setLevel(logging.WARNING)

    log = logging.getLogger("gifcast")
    if args.verbose:
        # Only our own logger: httpx and PIL at DEBUG bury the useful output.
        log.setLevel(logging.DEBUG)

    if not args.gif.is_file():
        log.error("No such file: %s", args.gif)
        return 2

    client = PrboxClient(args.url, args.token)

    try:
        if args.size:
            width, height = parse_size(args.size)
        else:
            panel = client.panel()
            width, height = panel.width, panel.height
            log.debug("Panel reports %dx%d", width, height)

        animation = convert(
            args.gif,
            width,
            height,
            crop=args.crop,
            max_frames=args.max_frames,
            fps=args.fps,
        )
        payload = animation.encoded()
        log.info(
            "%s -> %d frames at %dx%d, %.1f fps (%.0f KB)",
            args.gif.name,
            animation.count,
            width,
            height,
            animation.fps,
            len(payload) / 1024,
        )

        result = client.send_event(
            {
                "source": args.source,
                "priority": args.priority,
                "duration": args.duration,
                "scene": {
                    "kind": "frames",
                    "width": width,
                    "height": height,
                    "fps": animation.fps,
                    "loop": not args.once,
                    "data": payload,
                },
            }
        )
        log.info("Sent: %s (queued behind %d)", result["id"], result["queued"])
    except (PrboxError, ValueError, argparse.ArgumentTypeError) as exc:
        log.error("%s", exc)
        return 1
    except OSError as exc:
        log.error("Could not read %s: %s", args.gif, exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
