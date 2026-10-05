"""boxdemo — send generative visuals to your box."""

import argparse
import base64
import logging
import os
import sys
import time

from .client import BoxClient, BoxError, box_url, load_dotenv
from .scenes import gradient_frames, life_frames, rainbow_frames

#: Generating frames is the slow part, so cap what a single run will produce.
MAX_FRAMES = 600


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="boxdemo",
        description="Send generative visuals to your box.",
        epilog=(
            "Frames are generated here and uploaded once; the box loops them "
            "on its own, so nothing needs to keep running afterwards."
        ),
    )
    parser.add_argument(
        "visual",
        nargs="?",
        default="rainbow",
        choices=("rainbow", "life", "gradient"),
        help="what to render (default: rainbow)",
    )
    parser.add_argument(
        "--url", help="box base URL (default: http://localhost:8000, env: BOX_URL)"
    )
    parser.add_argument(
        "--token", default=os.getenv("BOX_TOKEN"), help="bearer token (env: BOX_TOKEN)"
    )
    parser.add_argument("--size", metavar="WxH", help="override the panel size")
    parser.add_argument(
        "--frames", type=int, default=180, help="frames to generate (default: 180)"
    )
    parser.add_argument("--fps", type=float, default=12.0, help="playback rate")
    parser.add_argument(
        "--priority",
        choices=("ambient", "normal", "alert", "alarm"),
        default="ambient",
        help="ambient joins the idle rotation and stays (default)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=20.0,
        help="seconds to hold the panel per turn (default: 20)",
    )
    parser.add_argument("--seed", type=int, help="make the output reproducible")
    parser.add_argument("--speed", type=float, default=0.08, help="rainbow: hue drift")
    parser.add_argument("--blobs", type=int, default=4, help="rainbow: blob count")
    parser.add_argument("--noise", type=float, default=0.25, help="rainbow: noise")
    parser.add_argument("--density", type=float, default=0.35, help="life: fill")
    parser.add_argument("--hue", type=float, default=0.45, help="life: base hue")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def parse_size(text: str) -> tuple[int, int]:
    try:
        w, h = (int(part) for part in text.lower().split("x", 1))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--size must look like 32x32, got {text!r}"
        ) from exc
    if w < 1 or h < 1:
        raise argparse.ArgumentTypeError(f"--size must be positive, got {text!r}")
    return w, h


def render(args, width: int, height: int) -> bytes:
    if args.visual == "rainbow":
        return rainbow_frames(
            width,
            height,
            args.frames,
            args.fps,
            speed=args.speed,
            blobs=args.blobs,
            noise_amount=args.noise,
            seed=args.seed,
        )
    if args.visual == "life":
        return life_frames(
            width,
            height,
            args.frames,
            density=args.density,
            hue=args.hue,
            seed=args.seed,
        )
    return gradient_frames(width, height, args.frames)


def main(argv: list[str] | None = None) -> int:
    # Before the parser: --token defaults to BOX_TOKEN, which a .env may set.
    load_dotenv()
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for chatty in ("httpx2", "httpcore2"):
        logging.getLogger(chatty).setLevel(logging.WARNING)
    log = logging.getLogger("boxdemo")
    if args.verbose:
        log.setLevel(logging.DEBUG)

    if not 1 <= args.frames <= MAX_FRAMES:
        log.error("--frames must be between 1 and %d", MAX_FRAMES)
        return 2

    try:
        client = BoxClient(box_url(args.url), args.token)
        if args.size:
            width, height = parse_size(args.size)
        else:
            panel = client.panel()
            width, height = panel.width, panel.height
            log.debug("Panel reports %dx%d", width, height)

        started = time.perf_counter()
        frames = render(args, width, height)
        payload = base64.b64encode(frames).decode("ascii")
        log.info(
            "%s -> %d frames at %dx%d, %.1f fps (%.0f KB, %.1fs to render)",
            args.visual,
            args.frames,
            width,
            height,
            args.fps,
            len(payload) / 1024,
            time.perf_counter() - started,
        )

        result = client.send_event(
            {
                "source": "boxdemo",
                "priority": args.priority,
                "duration": args.duration,
                "scene": {
                    "kind": "frames",
                    "width": width,
                    "height": height,
                    "fps": args.fps,
                    "loop": True,
                    "data": payload,
                },
            }
        )
        log.info("Sent: %s (queued behind %d)", result["id"], result["queued"])
    except (BoxError, ValueError, argparse.ArgumentTypeError) as exc:
        log.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
