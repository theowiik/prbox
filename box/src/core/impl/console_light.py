from src.core.light_state import LightState

from ...util import print_color, str_box
from ..light import Light


class ConsoleLight(Light):
    def set_state(self, state: LightState) -> None:
        state_str = "on" if state.on else "off"
        print_color(str_box(state_str), state.color)
