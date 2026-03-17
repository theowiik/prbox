from fastapi import APIRouter

from ..sources.weather import MockWeather

router = APIRouter(prefix="/api/sources")

_weather = MockWeather()


@router.get("/weather")
def get_weather():
    return _weather.get()
