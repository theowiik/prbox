from fastapi import APIRouter, HTTPException, Request

from ...sources.weather import WeatherData

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("/weather", summary="Current (mock) weather")
def get_weather(request: Request) -> WeatherData:
    """Read-only view of the on-box weather source.

    The panel does not depend on anyone calling this — `SourceRunner` already
    pushes weather into the ambient rotation. This is for the dashboard.
    """
    weather = next((s for s in request.app.state.sources if s.name == "weather"), None)
    if weather is None:
        raise HTTPException(status_code=404, detail="No weather source configured")
    return weather.get()
