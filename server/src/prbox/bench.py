"""Measure scene render throughput.

Run on the target device (`make bench`) to pick a PRBOX_FPS the hardware can
actually sustain — a render loop that cannot keep up is what makes animation
look stuttery, and the number differs a lot between a laptop and a Pi Zero.
"""

import time

from .config import Settings
from .render.frame import Frame
from .render.scenes import RainbowScene, TextScene


def measure(scene, frame: Frame, seconds: float = 2.0) -> float:
    """Frames per second this scene sustains, after a short warm-up."""
    for i in range(10):
        scene.render(frame, i * 0.03)

    count = 0
    start = time.perf_counter()
    while True:
        scene.render(frame, count * 0.03)
        count += 1
        elapsed = time.perf_counter() - start
        if elapsed >= seconds:
            return count / elapsed


def main() -> None:
    settings = Settings.from_env()
    frame = Frame(settings.width, settings.height)
    print(f"Panel: {settings.width}x{settings.height}  target: {settings.fps} fps\n")

    scenes = [
        ("text (scrolling)", TextScene("22°C FOGGY", (255, 200, 0))),
        ("rainbow (4 blobs)", RainbowScene(blobs=4)),
        ("rainbow (8 blobs)", RainbowScene(blobs=8)),
        ("rainbow (no noise)", RainbowScene(blobs=4, noise_amount=0.0)),
    ]
    for label, scene in scenes:
        fps = measure(scene, frame)
        verdict = "ok" if fps >= settings.fps * 1.5 else "TIGHT"
        print(f"  {label:<20} {fps:8.1f} fps  {verdict}")


if __name__ == "__main__":
    main()
