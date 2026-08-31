"""Talk to a box over the network.

Deliberately thin: the box's API is one endpoint with one JSON shape, so this
is a convenience, not a required SDK. `curl` works just as well and the README
shows it.
"""

import logging
from dataclasses import dataclass

import httpx2 as httpx

logger = logging.getLogger(__name__)

#: A connector must never hang because the box is asleep or off the tailnet.
TIMEOUT = 10.0


class PrboxError(RuntimeError):
    pass


@dataclass(frozen=True)
class Panel:
    width: int
    height: int


class PrboxClient:
    def __init__(self, base_url: str, token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}

    def panel(self) -> Panel:
        """Ask the box how big it is, so we can send frames at native size."""
        try:
            r = httpx.get(f"{self.base_url}/api/display", timeout=TIMEOUT)
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise PrboxError(
                f"Could not reach box at {self.base_url}: {exc}"
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
            raise PrboxError(
                f"Could not reach box at {self.base_url}: {exc}"
            ) from exc

        if r.status_code == 401:
            raise PrboxError(
                "box rejected the token. Pass --token or set BOX_TOKEN."
            )
        if r.status_code == 422:
            raise PrboxError(f"box rejected the event: {r.text}")
        if r.status_code >= 400:
            raise PrboxError(f"box returned {r.status_code}: {r.text}")
        return r.json()
