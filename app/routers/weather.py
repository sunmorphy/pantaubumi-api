from fastapi import APIRouter, Query

from app.schemas.weather import WeatherResponse
from app.schemas.response import APIResponse, ok
from app.utils.cache import get_cached_weather, get_cached_seismic

router = APIRouter()

_RESPONSE_200 = {
    "content": {
        "application/json": {
            "examples": {
                "with_rain": {
                    "summary": "Active rainfall (Jakarta)",
                    "value": {
                        "code": 200,
                        "status": "Success",
                        "message": None,
                        "data": {
                            "rainfall_mm_per_hour": 82.0,
                            "river_level_m": 3.4,
                            "river_level_delta_per_hour": 0.8,
                            "latest_magnitude": None,
                            "recorded_at": "2026-03-18T09:00:00Z",
                        },
                    },
                },
                "with_quake": {
                    "summary": "Post-earthquake area",
                    "value": {
                        "code": 200,
                        "status": "Success",
                        "message": None,
                        "data": {
                            "rainfall_mm_per_hour": 5.0,
                            "river_level_m": 1.3,
                            "river_level_delta_per_hour": 0.1,
                            "latest_magnitude": 4.7,
                            "recorded_at": "2026-03-18T06:30:00Z",
                        },
                    },
                },
            }
        }
    }
}


@router.get(
    "/weather",
    response_model=APIResponse[WeatherResponse],
    summary="Get current weather and seismic readings for a location",
    responses={200: _RESPONSE_200},
    tags=["Weather"],
)
async def get_weather(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
):
    """
    Returns the latest ingested weather and seismic sensor readings for the
    nearest monitoring station to the given coordinates.

    **Data sources (refreshed every 5 minutes):**
    - `rainfall_mm_per_hour` — Open-Meteo hourly precipitation forecast
    - `river_level_m` — Estimated from rainfall + soil moisture (proxy model)
    - `river_level_delta_per_hour` — Change since last reading (positive = rising)
    - `latest_magnitude` — Most recent USGS earthquake M≥2.0 near this location
      (`null` if no recent seismic activity)

    Data is served from the **in-memory weather cache** (TTL 6 minutes).
    If no ingestion has run yet for this grid cell, neutral default values are returned.
    """
    wx = get_cached_weather(lat, lng)
    seismic = get_cached_seismic(lat, lng)

    # latest_magnitude: only report if there was a real quake (default is 0.0)
    raw_mag = seismic.get("magnitude", 0.0)
    latest_magnitude = float(raw_mag) if raw_mag and float(raw_mag) > 0.0 else None

    data = WeatherResponse(
        rainfall_mm_per_hour=round(float(wx.get("rainfall_mm", 0.0)), 2),
        river_level_m=round(float(wx.get("river_level_m", 1.0)), 2),
        river_level_delta_per_hour=round(float(wx.get("river_level_delta_per_hour", 0.0)), 3),
        latest_magnitude=latest_magnitude,
        recorded_at=wx.get("recorded_at"),
    )

    return ok(data=data.model_dump(mode="json"))
