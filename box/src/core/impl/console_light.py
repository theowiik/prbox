from ...util import print_color
from ..light import Light


class ConsoleLight(Light):
    def on(self) -> None:
        print("💡🟢")

        print_color("hello", "#FF0000")

    def off(self) -> None:
        print("💡🚫")
