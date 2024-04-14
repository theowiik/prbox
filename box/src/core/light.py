from typing import Protocol


class Light(Protocol):
    def on(self) -> None:
        ...

    def off(self) -> None:
        ...
