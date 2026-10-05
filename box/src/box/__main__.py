"""Run the box: `python -m box` or the `box` console script.

Reads host and port from the same BOX_* settings as everything else (a `.env`
included), so a systemd unit on the Pi needs no uvicorn flags — only
environment — and `make dev` picks up a changed port without a second place to
edit it.
"""

import argparse
import logging

import uvicorn

from .config import Settings

logger = logging.getLogger("box")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="box", description="Run the box.")
    parser.add_argument(
        "--reload", action="store_true", help="restart on code changes (development)"
    )
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    if not settings.token:
        logger.warning(
            "BOX_TOKEN is unset — write endpoints are unauthenticated on %s",
            settings.host,
        )
    uvicorn.run(
        "box.api.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
