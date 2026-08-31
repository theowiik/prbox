"""Turn a GIF into panel-sized RGB frames.

All decoding happens here, on whatever machine runs the connector, so the Pi
never grows an image stack. The box only ever receives raw pixels.
"""

import base64
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageSequence

#: Panels are tiny, so a smooth downscale turns detail into grey mush. Nearest
#: keeps edges hard, which is what actually reads on a 32x32 grid.
RESAMPLE = Image.Resampling.NEAREST

#: GIF delays below this are usually "as fast as possible"; browsers clamp too.
MIN_DELAY_MS = 20
DEFAULT_DELAY_MS = 100


@dataclass(frozen=True)
class Animation:
    width: int
    height: int
    fps: float
    frames: bytes  # count * width * height * 3, row-major from top-left

    @property
    def count(self) -> int:
        return len(self.frames) // (self.width * self.height * 3)

    def encoded(self) -> str:
        return base64.b64encode(self.frames).decode("ascii")


def _fit(image: Image.Image, width: int, height: int, crop: bool) -> Image.Image:
    """Scale to the panel, either letterboxed or centre-cropped."""
    if crop:
        scale = max(width / image.width, height / image.height)
    else:
        scale = min(width / image.width, height / image.height)

    new = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    scaled = image.resize(new, RESAMPLE)

    canvas = Image.new("RGB", (width, height), (0, 0, 0))
    canvas.paste(scaled, ((width - new[0]) // 2, (height - new[1]) // 2))
    return canvas


def convert(
    path: Path,
    width: int,
    height: int,
    *,
    crop: bool = False,
    max_frames: int | None = None,
    fps: float | None = None,
) -> Animation:
    """Load `path` and render it to panel-sized RGB frames."""
    with Image.open(path) as source:
        delays: list[int] = []
        frames: list[bytes] = []

        for frame in ImageSequence.Iterator(source):
            # Convert through RGBA so transparency composites onto black rather
            # than picking up whatever the palette's index 0 happens to be.
            rgba = frame.convert("RGBA")
            flat = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
            flat.alpha_composite(rgba)

            frames.append(_fit(flat.convert("RGB"), width, height, crop).tobytes())
            delays.append(
                max(frame.info.get("duration", DEFAULT_DELAY_MS), MIN_DELAY_MS)
            )

            if max_frames and len(frames) >= max_frames:
                break

    if not frames:
        raise ValueError(f"{path} contains no frames")

    if fps is None:
        # GIFs carry a per-frame delay; the panel plays at one rate, so use the
        # average. Uneven timing is rare and not worth a variable-rate protocol.
        average_ms = sum(delays) / len(delays)
        fps = 1000.0 / average_ms

    return Animation(
        width=width,
        height=height,
        fps=min(max(fps, 0.1), 60.0),
        frames=b"".join(frames),
    )
