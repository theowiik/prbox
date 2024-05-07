from typing import Protocol

from .light_state import LightState


class Light(Protocol):
    def set_state(self, state: LightState) -> None: ...
