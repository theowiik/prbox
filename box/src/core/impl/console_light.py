from ..light import Light


class ConsoleLight(Light):
    def on(self) -> None:
        print("💡🟢")

    def off(self) -> None:
        print("💡🚫")
