"""Environment-driven configuration.

Every knob is a `PRBOX_*` env var so the same image runs on a laptop and on a
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
    def from_env(cls) -> "MatrixOptions":
        return cls(
            chain_length=_int("PRBOX_MATRIX_CHAIN", 1),
            parallel=_int("PRBOX_MATRIX_PARALLEL", 1),
            hardware_mapping=os.getenv("PRBOX_MATRIX_MAPPING", "regular"),
            gpio_slowdown=_int("PRBOX_MATRIX_GPIO_SLOWDOWN", 2),
            pwm_bits=_int("PRBOX_MATRIX_PWM_BITS", 11),
            pwm_lsb_nanoseconds=_int("PRBOX_MATRIX_PWM_LSB_NS", 130),
            brightness=_int("PRBOX_MATRIX_HW_BRIGHTNESS", 100),
        )


@dataclass(frozen=True)
class Settings:
    mode: str = "dev"
    width: int = 32
    height: int = 8
    fps: int = 30
    gamma: float = 2.2
    tty_preview: bool = False
    city: str = "Stockholm"
    matrix: MatrixOptions = field(default_factory=MatrixOptions)

    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls(
            mode=os.getenv("PRBOX_DISPLAY_MODE", "dev").strip().lower(),
            width=_int("PRBOX_DISPLAY_WIDTH", 32),
            height=_int("PRBOX_DISPLAY_HEIGHT", 8),
            fps=_int("PRBOX_FPS", 30),
            gamma=_float("PRBOX_GAMMA", 2.2),
            tty_preview=_bool("PRBOX_TTY_PREVIEW", False),
            city=os.getenv("PRBOX_CITY", "Stockholm"),
            matrix=MatrixOptions.from_env(),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.mode not in {"dev", "matrix"}:
            raise ValueError(
                f"PRBOX_DISPLAY_MODE must be 'dev' or 'matrix', got {self.mode!r}"
            )
        if self.width < 1 or self.height < 1:
            raise ValueError("Display dimensions must be positive")
        if not 1 <= self.fps <= 120:
            raise ValueError("PRBOX_FPS must be between 1 and 120")
        if self.gamma <= 0:
            raise ValueError("PRBOX_GAMMA must be positive")
