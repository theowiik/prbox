"""Talk to a box over the network.

Deliberately thin: the box's API is one endpoint with one JSON shape, so this
is a convenience, not a required SDK. `curl` works just as well and the README
shows it.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import httpx2 as httpx

logger = logging.getLogger(__name__)

#: A connector must never hang because the box is asleep or off the tailnet.
TIMEOUT = 10.0


class BoxError(RuntimeError):
    pass


#: Where the box is unless something says otherwise: same machine, same port it
#: serves on by default — the case that should need no thought.
DEFAULT_HOST = "localhost"
DEFAULT_PORT = "8000"


def _find_dotenv(start: Path) -> Path | None:
    """Nearest `.env` at or above `start`, without leaving the project.

    Bounded by the repo root: a stray `.env` in a home directory belongs to
    something else and must never end up configuring the box.
    """
    for folder in (start, *start.parents):
        candidate = folder / ".env"
        if candidate.is_file():
            return candidate
        if (folder / ".git").exists():
            break
    return None


def load_dotenv(start: Path | None = None) -> None:
    """Fill in `BOX_*` values from a `.env` in this folder or a parent.

    Optional, and only worth writing if your box is not on the default port. A
    real environment variable always wins over the file.
    """
    path = _find_dotenv((start or Path.cwd()).resolve())
    if path is None:
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def box_url(explicit: str | None = None) -> str:
    """`--url`, then `BOX_URL`, then `BOX_PORT` on localhost, then the default."""
    if explicit:
        return explicit.rstrip("/")
    load_dotenv()
    if os.getenv("BOX_URL"):
        return os.environ["BOX_URL"].rstrip("/")
    return f"http://{DEFAULT_HOST}:{os.getenv('BOX_PORT') or DEFAULT_PORT}"


@dataclass(frozen=True)
class Panel:
    width: int
    height: int


class BoxClient:
    def __init__(self, base_url: str, token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}

    def panel(self) -> Panel:
        """Ask the box how big it is, so we can send frames at native size."""
        try:
            r = httpx.get(f"{self.base_url}/api/display", timeout=TIMEOUT)
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise BoxError(
                f"Could not reach a box at {self.base_url} — is it running? "
                f"Start one with `make dev`, or set BOX_URL in a .env.\n{exc}"
            ) from exc
        data = r.json()
        return Panel(width=data["width"], height=data["height"])

    def send_event(self, event: dict) -> dict:
        try:
            r = httpx.post(
                f"{self.base_url}/api/events",
                json=event,
                headers=self._headers,
                timeout=TIMEOUT,
            )
        except httpx.HTTPError as exc:
            raise BoxError(
                f"Could not reach a box at {self.base_url} — is it running? "
                f"Start one with `make dev`, or set BOX_URL in a .env.\n{exc}"
            ) from exc

        if r.status_code == 401:
            raise BoxError("box rejected the token. Pass --token or set BOX_TOKEN.")
        if r.status_code == 422:
            raise BoxError(f"box rejected the event: {r.text}")
        if r.status_code >= 400:
            raise BoxError(f"box returned {r.status_code}: {r.text}")
        return r.json()
