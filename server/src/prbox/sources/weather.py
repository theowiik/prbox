import random
import time

from pydantic import BaseModel

_CONDITIONS = [
    ("Sunny", "#FFD700"),
    ("Cloudy", "#9E9E9E"),
    ("Rainy", "#4FC3F7"),
    ("Snow", "#B0BEC5"),
    ("Windy", "#80CBC4"),
    ("Storm", "#FF5722"),
    ("Clear", "#64B5F6"),
    ("Foggy", "#78909C"),
]


class WeatherData(BaseModel):
    city: str
    temp: int
    condition: str
    display_text: str
    display_color: str


class MockWeather:
    def __init__(self, city: str = "Stockholm"):
        self.city = city

    def get(self) -> WeatherData:
        seed = int(time.time() // 300)
        rng = random.Random(seed)
        temp = rng.randint(-5, 35)
        condition, color = rng.choice(_CONDITIONS)
        return WeatherData(
            city=self.city,
            temp=temp,
            condition=condition,
            display_text=f"{temp}C {condition.upper()}",
            display_color=color,
        )
