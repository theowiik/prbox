"""Environment-driven configuration.

Every knob is a `BOX_*` env var so the same image runs on a laptop and on a
Raspberry Pi with nothing but the environment changing.
"""

import os
from dataclasses import dataclass, field


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class MatrixOptions:
    """Hardware wiring options, passed through to rpi-rgb-led-matrix."""

    chain_length: int = 1
    parallel: int = 1
    hardware_mapping: str = "regular"
    gpio_slowdown: int = 2
    pwm_bits: int = 11
    pwm_lsb_nanoseconds: int = 130
    brightness: int = 100

    @classmethod
    def from_env(cls) -> MatrixOptions:
        return cls(
            chain_length=_int("BOX_MATRIX_CHAIN", cls.chain_length),
            parallel=_int("BOX_MATRIX_PARALLEL", cls.parallel),
            hardware_mapping=os.getenv("BOX_MATRIX_MAPPING", cls.hardware_mapping),
            gpio_slowdown=_int("BOX_MATRIX_GPIO_SLOWDOWN", cls.gpio_slowdown),
            pwm_bits=_int("BOX_MATRIX_PWM_BITS", cls.pwm_bits),
            pwm_lsb_nanoseconds=_int("BOX_MATRIX_PWM_LSB_NS", cls.pwm_lsb_nanoseconds),
            brightness=_int("BOX_MATRIX_HW_BRIGHTNESS", cls.brightness),
        )


@dataclass(frozen=True)
class Settings:
    mode: str = "dev"
    width: int = 32
    height: int = 32
    fps: int = 30
    gamma: float = 2.2
    tty_preview: bool = False
    city: str = "Stockholm"
    #: Bind address. Defaults to all interfaces so connectors on the network
    #: (or a tailnet) can reach the box; loopback-only makes it unreachable.
    host: str = "0.0.0.0"
    port: int = 8000
    #: Shared secret for write endpoints. Empty disables auth entirely.
    token: str = ""
    #: Seconds each ambient card holds the panel before the rotation advances.
    ambient_dwell: float = 12.0
    #: How often on-Pi sources refresh their ambient card.
    source_interval: float = 60.0
    matrix: MatrixOptions = field(default_factory=MatrixOptions)

    @classmethod
    def from_env(cls) -> Settings:
        settings = cls(
            mode=os.getenv("BOX_DISPLAY_MODE", cls.mode).strip().lower(),
            width=_int("BOX_DISPLAY_WIDTH", cls.width),
            height=_int("BOX_DISPLAY_HEIGHT", cls.height),
            fps=_int("BOX_FPS", cls.fps),
            gamma=_float("BOX_GAMMA", cls.gamma),
            tty_preview=_bool("BOX_TTY_PREVIEW", cls.tty_preview),
            city=os.getenv("BOX_CITY", cls.city),
            host=os.getenv("BOX_HOST", cls.host),
            port=_int("BOX_PORT", cls.port),
            token=os.getenv("BOX_TOKEN", cls.token),
            ambient_dwell=_float("BOX_AMBIENT_DWELL", cls.ambient_dwell),
            source_interval=_float("BOX_SOURCE_INTERVAL", cls.source_interval),
            matrix=MatrixOptions.from_env(),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.mode not in {"dev", "matrix"}:
            raise ValueError(
                f"BOX_DISPLAY_MODE must be 'dev' or 'matrix', got {self.mode!r}"
            )
        if self.width < 1 or self.height < 1:
            raise ValueError("Display dimensions must be positive")
        if not 1 <= self.fps <= 120:
            raise ValueError("BOX_FPS must be between 1 and 120")
        if self.gamma <= 0:
            raise ValueError("BOX_GAMMA must be positive")
        if self.ambient_dwell <= 0:
            raise ValueError("BOX_AMBIENT_DWELL must be positive")
        if self.source_interval <= 0:
            raise ValueError("BOX_SOURCE_INTERVAL must be positive")
        if not 1 <= self.port <= 65535:
            raise ValueError("BOX_PORT must be a valid port")
