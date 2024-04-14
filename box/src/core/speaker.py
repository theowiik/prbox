from typing import Protocol


class Speaker(Protocol):
    def beep(self) -> None:
        ...
