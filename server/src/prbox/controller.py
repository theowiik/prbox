"""Ties the HTTP API to the render engine.

The engine only knows how to draw; this holds the user-facing state (what text
is showing, which scene is active) that the API reports back.
"""

from .display.base import DisplayState
from .render.engine import RenderEngine
from .render.frame import hex_to_rgb
from .render.scenes import BlankScene, RainbowScene, SolidScene, TextScene


class DisplayController:
    def __init__(self, engine: RenderEngine) -> None:
        self._engine = engine
        self._text = ""
        self._color = "#00FF00"
        self._scene_name = "blank"

    @property
    def engine(self) -> RenderEngine:
        return self._engine

    def show_text(self, text: str, color: str = "#00FF00") -> None:
        rgb = hex_to_rgb(color)
        self._text = text
        self._color = color.upper() if color.startswith("#") else f"#{color.upper()}"
        self._scene_name = "text"
        self._engine.set_scene(TextScene(text, rgb))

    def show_solid(self, color: str) -> None:
        rgb = hex_to_rgb(color)
        self._text = ""
        self._color = color.upper()
        self._scene_name = "solid"
        self._engine.set_scene(SolidScene(rgb))

    def show_rainbow(
        self,
        speed: float = 0.08,
        blobs: int = 4,
        noise: float = 0.25,
        saturation: float = 1.0,
    ) -> None:
        self._text = ""
        self._scene_name = "rainbow"
        self._engine.set_scene(
            RainbowScene(
                speed=speed,
                blobs=blobs,
                noise_amount=noise,
                saturation=saturation,
            )
        )

    def clear(self) -> None:
        self._text = ""
        self._scene_name = "blank"
        self._engine.set_scene(BlankScene())

    def set_brightness(self, brightness: float) -> None:
        self._engine.set_brightness(brightness)

    def get_state(self) -> DisplayState:
        width, height = self._engine.size
        return DisplayState(
            scene=self._scene_name,
            text=self._text,
            color=self._color,
            brightness=self._engine.brightness,
            width=width,
            height=height,
            fps=self._engine.fps,
        )
