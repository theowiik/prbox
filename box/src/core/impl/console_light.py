from src.core.light_state import LightState

from ...util import print_color, str_box
from ..light import Light


class ConsoleLight(Light):
    def set_state(self, state: LightState) -> None:
        print_color(str_box("Light state set"), "#00FF00")
