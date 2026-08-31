"""Run the box: `python -m box` or the `box` console script.

Reads host and port from the same BOX_* settings as everything else, so a
systemd unit on the Pi needs no uvicorn flags — only environment.
"""

import logging

import uvicorn

from .config import Settings

logger = logging.getLogger("box")


def main() -> None:
    settings = Settings.from_env()
    if not settings.token:
        logger.warning(
            "BOX_TOKEN is unset — write endpoints are unauthenticated on %s",
            settings.host,
        )
    uvicorn.run(
        "box.api.app:app",
        host=settings.host,
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
