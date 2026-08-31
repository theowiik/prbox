from fastapi import APIRouter, Depends, Request

from ..sources.weather import MockWeather, WeatherData

router = APIRouter(prefix="/api/sources", tags=["sources"])


def _get_weather(request: Request) -> MockWeather:
    return request.app.state.weather


@router.get("/weather", summary="Current (mock) weather")
def get_weather(weather: MockWeather = Depends(_get_weather)) -> WeatherData:
    return weather.get()
