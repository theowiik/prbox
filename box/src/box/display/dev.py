import logging
import shutil
import sys
import time

logger = logging.getLogger(__name__)

#: Half-block trick: one terminal cell shows two vertical pixels.
_HALF_BLOCK = "▀"


class DevDisplay:
    """Development display.

    Holds the most recent frame for the web preview and — when stdout is a TTY
    and BOX_TTY_PREVIEW is enabled — draws the panel in the terminal using
    truecolor half-blocks, so you can see the real output without a browser.
    """

    def __init__(
        self,
        width: int = 32,
        height: int = 32,
        tty_preview: bool = False,
        tty_fps: int = 10,
    ) -> None:
        self.width = width
        self.height = height
        self._frame = bytes(width * height * 3)
        self._tty = tty_preview and sys.stdout.isatty()
        self._min_interval = 1.0 / max(1, tty_fps)
        self._last_draw = 0.0
        self._lines_drawn = 0

    def push_frame(self, buf: bytes) -> None:
        self._frame = bytes(buf)
        if self._tty:
            self._draw_tty()

    def latest_frame(self) -> bytes:
        return self._frame

    def close(self) -> None:
        if self._tty and self._lines_drawn:
            sys.stdout.write("\n")
            sys.stdout.flush()

    def _draw_tty(self) -> None:
        """Repaint the terminal preview, rate-limited so it stays cheap."""
        now = time.monotonic()
        if now - self._last_draw < self._min_interval:
            return
        self._last_draw = now

        if shutil.get_terminal_size().columns < self.width:
            return

        buf = self._frame
        w = self.width
        out = []
        if self._lines_drawn:
            out.append(f"\033[{self._lines_drawn}A")

        for y in range(0, self.height - self.height % 2, 2):
            for x in range(w):
                t = (y * w + x) * 3
                b = ((y + 1) * w + x) * 3
                out.append(
                    f"\033[38;2;{buf[t]};{buf[t + 1]};{buf[t + 2]}m"
                    f"\033[48;2;{buf[b]};{buf[b + 1]};{buf[b + 2]}m{_HALF_BLOCK}"
                )
            out.append("\033[0m\n")

        self._lines_drawn = self.height // 2
        sys.stdout.write("".join(out))
        sys.stdout.flush()
