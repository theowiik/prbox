"""Raspberry Pi LED matrix backend, built on rpi-rgb-led-matrix.

The `rgbmatrix` module ships with hzeller's rpi-rgb-led-matrix library and is
not installable from PyPI, so it is imported lazily: importing this module on a
laptop must not fail.
"""

import logging

logger = logging.getLogger(__name__)


class MatrixDisplay:
    """Pushes frames to a physical HUB75 panel.

    Frames are written to an offscreen canvas and swapped on vsync, which is
    what keeps motion tear-free — drawing straight onto the live canvas shows
    partially-written frames.
    """

    def __init__(
        self,
        width: int = 32,
        height: int = 8,
        *,
        chain_length: int = 1,
        parallel: int = 1,
        hardware_mapping: str = "regular",
        gpio_slowdown: int = 2,
        pwm_bits: int = 11,
        pwm_lsb_nanoseconds: int = 130,
        brightness: int = 100,
    ) -> None:
        try:
            from rgbmatrix import RGBMatrix, RGBMatrixOptions
        except ImportError as exc:  # pragma: no cover - hardware-only path
            raise RuntimeError(
                "PRBOX_DISPLAY_MODE=matrix requires the 'rgbmatrix' Python module "
                "from https://github.com/hzeller/rpi-rgb-led-matrix (build it with "
                "`make build-python && sudo make install-python`). Use "
                "PRBOX_DISPLAY_MODE=dev off-device."
            ) from exc

        self.width = width
        self.height = height

        options = RGBMatrixOptions()
        options.rows = height // parallel
        options.cols = width // chain_length
        options.chain_length = chain_length
        options.parallel = parallel
        options.hardware_mapping = hardware_mapping
        options.gpio_slowdown = gpio_slowdown
        options.pwm_bits = pwm_bits
        options.pwm_lsb_nanoseconds = pwm_lsb_nanoseconds
        options.brightness = brightness
        # The library's own refresh thread fights the render loop for CPU on a
        # Pi Zero; dropping the privilege change keeps startup usable via systemd.
        options.drop_privileges = False

        self._matrix = RGBMatrix(options=options)
        self._canvas = self._matrix.CreateFrameCanvas()
        self._image = None
        try:
            from PIL import Image

            self._Image = Image
        except ImportError:
            self._Image = None
            logger.info("Pillow not installed; using slower per-pixel matrix writes")

        logger.info(
            "Matrix ready: %dx%d (rows=%d cols=%d chain=%d parallel=%d mapping=%s)",
            width,
            height,
            options.rows,
            options.cols,
            chain_length,
            parallel,
            hardware_mapping,
        )

    def push_frame(self, buf: bytes) -> None:
        if self._Image is not None:
            # SetImage does the whole panel in C, far cheaper than 256+ SetPixel
            # calls crossing the Python/C boundary every frame.
            image = self._Image.frombytes("RGB", (self.width, self.height), bytes(buf))
            self._canvas.SetImage(image)
        else:
            w = self.width
            for y in range(self.height):
                row = y * w
                for x in range(w):
                    i = (row + x) * 3
                    self._canvas.SetPixel(x, y, buf[i], buf[i + 1], buf[i + 2])

        self._canvas = self._matrix.SwapOnVSync(self._canvas)

    def close(self) -> None:
        matrix = getattr(self, "_matrix", None)
        if matrix is not None:
            matrix.Clear()
