"""Mock weather source.

Deterministic per 5-minute bucket so repeated polls agree with each other and
the dashboard does not flicker between values.
"""

import random
import time
from dataclasses import dataclass

from .base import SourcePayload

BUCKET_SECONDS = 300


@dataclass(frozen=True)
class Condition:
    label: str
    color: str


_CONDITIONS = (
    Condition("Sunny", "#FFD54F"),
    Condition("Clear", "#64B5F6"),
    Condition("Cloudy", "#9E9E9E"),
    Condition("Rainy", "#4FC3F7"),
    Condition("Snow", "#B0BEC5"),
    Condition("Windy", "#80CBC4"),
    Condition("Storm", "#FF7043"),
    Condition("Foggy", "#78909C"),
)


class WeatherData(SourcePayload):
    city: str
    temp: int
    feels_like: int
    condition: str
    humidity: int
    wind_kph: int


class MockWeather:
    name = "weather"

    def __init__(self, city: str = "Stockholm") -> None:
        self.city = city

    def get(self, now: float | None = None) -> WeatherData:
        bucket = int((time.time() if now is None else now) // BUCKET_SECONDS)
        # Seed on the city too, so different cities do not report identical data.
        rng = random.Random(f"{self.city}:{bucket}")

        condition = rng.choice(_CONDITIONS)
        temp = rng.randint(-5, 35)
        wind = rng.randint(0, 45)
        # Wind makes it feel colder; strong sun makes it feel warmer.
        feels_like = temp - wind // 12 + (2 if condition.label == "Sunny" else 0)

        return WeatherData(
            city=self.city,
            temp=temp,
            feels_like=feels_like,
            condition=condition.label,
            humidity=rng.randint(25, 98),
            wind_kph=wind,
            display_text=f"{temp}°C {condition.label.upper()}",
            display_color=condition.color,
        )
