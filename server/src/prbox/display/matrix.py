from .base import DisplayState


class MatrixDisplay:
    """LED matrix display for Raspberry Pi. Not yet implemented."""

    def __init__(self) -> None:
        self._state = DisplayState()

    def show_text(self, text: str, color: str = "#00FF00") -> None:
        raise NotImplementedError("Matrix display not yet implemented")

    def clear(self) -> None:
        raise NotImplementedError("Matrix display not yet implemented")

    def set_brightness(self, brightness: float) -> None:
        raise NotImplementedError("Matrix display not yet implemented")

    def get_state(self) -> DisplayState:
        return self._state.model_copy()
