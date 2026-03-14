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
