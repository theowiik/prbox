import logging

from .base import DisplayState

logger = logging.getLogger(__name__)


def _hex_to_rgb(hex_code: str) -> tuple[int, int, int]:
    hex_code = hex_code.lstrip("#")
    return (int(hex_code[0:2], 16), int(hex_code[2:4], 16), int(hex_code[4:6], 16))


class DevDisplay:
    """Development display that prints to console and exposes state for web preview."""

    def __init__(self, width: int = 32, height: int = 8) -> None:
        self._state = DisplayState(width=width, height=height)

    def show_text(self, text: str, color: str = "#00FF00") -> None:
        self._state.text = text
        self._state.color = color
        r, g, b = _hex_to_rgb(color)
        print(f"\033[38;2;{r};{g};{b}m[DISPLAY] {text}\033[0m")

    def clear(self) -> None:
        self._state.text = ""
        logger.info("[Display] Cleared")

    def set_brightness(self, brightness: float) -> None:
        if not 0.0 <= brightness <= 1.0:
            raise ValueError("Brightness must be between 0.0 and 1.0")
        self._state.brightness = brightness
        logger.info("[Display] Brightness: %.0f%%", brightness * 100)

    def get_state(self) -> DisplayState:
        return self._state.model_copy()
