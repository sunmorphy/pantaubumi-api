from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.ai.risk_engine import compute_risk
from app.schemas.risk import RiskResponse
from app.schemas.response import APIResponse, ok
from app.utils.cache import cache_get, cache_set

router = APIRouter()

_RESPONSE_200 = {
    "content": {
        "application/json": {
            "example": {
                "code": 200,
                "status": "Success",
                "message": None,
                "data": {
                    "lat": -6.2,
                    "lng": 106.8,
                    "flood_score": 0.73,
                    "landslide_score": 0.41,
                    "earthquake_score": 0.12,
                    "overall_risk": "high",
                    "computed_at": "2026-03-14T04:00:00Z",
                },
            }
        }
    }
}

_RESPONSE_422 = {
    "description": "Validation Error",
    "content": {
        "application/json": {
            "example": {
                "code": 422,
                "status": "Unprocessable Entity",
                "message": "query → lat: Input should be less than or equal to 7.0",
                "data": None,
            }
        }
    },
}


@router.get(
    "/risk",
    response_model=APIResponse[RiskResponse],
    summary="Get overall disaster risk for a location",
    responses={200: _RESPONSE_200, 422: _RESPONSE_422},
)
async def get_risk(
    lat: float = Query(..., description="Latitude (Indonesia range: -11.0 to 7.0)", ge=-11.0, le=7.0),
    lng: float = Query(..., description="Longitude (Indonesia range: 95.0 to 141.0)", ge=95.0, le=141.0),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the combined AI-powered disaster risk score for the given coordinates.

    **Models used:**
    - `flood_score` — XGBoost trained on historical rainfall + river level data
    - `landslide_score` — Random Forest trained on rainfall + soil saturation data
    - `earthquake_score` — Rule-based: USGS magnitude × proximity decay function

    **Overall risk aggregation:**

    | `overall_risk` | Condition |
    |---|---|
    | `critical` | any score ≥ 0.75 |
    | `high` | any score ≥ 0.50 |
    | `medium` | any score ≥ 0.25 |
    | `low` | all scores < 0.25 |

    Results are cached per 0.5° grid cell for **2 minutes** to avoid redundant model inference.
    """
    cache_key = f"risk:{round(lat, 2)}:{round(lng, 2)}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    result = await compute_risk(lat, lng)

    data = RiskResponse(
        lat=result.lat,
        lng=result.lng,
        flood_score=result.flood_score,
        landslide_score=result.landslide_score,
        earthquake_score=result.earthquake_score,
        overall_risk=result.overall_risk,
        computed_at=result.computed_at,
    )

    response = ok(data=data.model_dump(mode="json"))
    cache_set(cache_key, response, ttl=120)
    return response


# ── GET /risk/zones ────────────────────────────────────────────────────────────

_ZONES_RESPONSE_200 = {
    "content": {
        "application/json": {
            "example": {
                "code": 200,
                "status": "Success",
                "message": None,
                "data": [
                    {
                        "lat": -6.2,
                        "lng": 106.8,
                        "flood_score": 0.73,
                        "landslide_score": 0.41,
                        "earthquake_score": 0.12,
                        "overall_risk": "high",
                        "computed_at": "2026-03-14T04:00:00Z",
                    }
                ]
            }
        }
    }
}

@router.get(
    "/risk/zones",
    response_model=APIResponse[list[RiskResponse]],
    summary="Get a grid of risk zones within a bounding box",
    responses={200: _ZONES_RESPONSE_200},
)
async def get_risk_zones(
    min_lat: float = Query(..., description="Minimum Latitude (South)", ge=-11.0, le=7.0),
    max_lat: float = Query(..., description="Maximum Latitude (North)", ge=-11.0, le=7.0),
    min_lng: float = Query(..., description="Minimum Longitude (West)", ge=95.0, le=141.0),
    max_lng: float = Query(..., description="Maximum Longitude (East)", ge=95.0, le=141.0),
):
    """
    Returns a 3x3 grid (9 points total) of risk scores evenly distributed within the provided bounding box.
    Useful for rendering risk heatmaps or colored polygons on a map UI.
    """
    # Ensure min < max
    real_min_lat, real_max_lat = min(min_lat, max_lat), max(min_lat, max_lat)
    real_min_lng, real_max_lng = min(min_lng, max_lng), max(min_lng, max_lng)

    # Calculate 3 steps across the bounding box
    lat_step = (real_max_lat - real_min_lat) / 2 if real_max_lat > real_min_lat else 0
    lng_step = (real_max_lng - real_min_lng) / 2 if real_max_lng > real_min_lng else 0

    points = []
    for i in range(3):
        for j in range(3):
            lat = real_min_lat + (i * lat_step)
            lng = real_min_lng + (j * lng_step)
            points.append((lat, lng))

    results = []
    import asyncio
    
    async def fetch_point(p_lat, p_lng):
        cache_key = f"risk:zone:{round(p_lat, 2)}:{round(p_lng, 2)}"
        cached = cache_get(cache_key)
        if cached:
            return cached
            
        result = await compute_risk(p_lat, p_lng)
        data = RiskResponse(
            lat=result.lat,
            lng=result.lng,
            flood_score=result.flood_score,
            landslide_score=result.landslide_score,
            earthquake_score=result.earthquake_score,
            overall_risk=result.overall_risk,
            computed_at=result.computed_at,
        ).model_dump(mode="json")
        
        cache_set(cache_key, data, ttl=120)
        return data

    tasks = [fetch_point(lat, lng) for lat, lng in points]
    point_results = await asyncio.gather(*tasks)
    
    results.extend(point_results)

    return ok(data=results)
