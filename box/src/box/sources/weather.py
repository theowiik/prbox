"""Mock weather source — the reference implementation of an on-Pi source.

Deterministic per 5-minute bucket so repeated polls agree with each other and
the dashboard does not flicker between values.
"""

import random
import time
from dataclasses import dataclass

from pydantic import BaseModel

from ..events import Event, Priority, TextSpec

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


class WeatherData(BaseModel):
    display_text: str
    display_color: str
    city: str
    temp: int
    feels_like: int
    condition: str
    humidity: int
    wind_kph: int


class MockWeather:
    """Runs on the box, so the panel still shows weather with no browser open."""

    name = "weather"

    def __init__(self, city: str = "Stockholm", dwell: float = 12.0) -> None:
        self.city = city
        self.dwell = dwell

    def poll(self) -> Event:
        """Ambient card for the idle rotation, refreshed in place each cycle."""
        data = self.get()
        return Event(
            source=self.name,
            priority=Priority.AMBIENT,
            duration=self.dwell,
            scene=TextSpec(text=data.display_text, color=data.display_color),
        )

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
