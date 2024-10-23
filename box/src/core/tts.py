from typing import Protocol


class TTS(Protocol):
    def say(self, text: str) -> None: ...
