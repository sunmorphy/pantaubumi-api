from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.ai.risk_engine import compute_risk
from app.schemas.risk import RiskResponse
from app.utils.cache import cache_get, cache_set

router = APIRouter()


@router.get("/risk", response_model=RiskResponse, summary="Get overall disaster risk for a location")
async def get_risk(
    lat: float = Query(..., description="Latitude", ge=-11.0, le=7.0),
    lng: float = Query(..., description="Longitude", ge=95.0, le=141.0),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the combined disaster risk score for the given coordinates.

    - **flood_score**: XGBoost flood risk (0–1)
    - **landslide_score**: Random Forest landslide risk (0–1)
    - **earthquake_score**: Rule-based seismic risk (0–1)
    - **overall_risk**: Aggregated label (low / medium / high / critical)
    """
    cache_key = f"risk:{round(lat, 2)}:{round(lng, 2)}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    result = await compute_risk(lat, lng)

    response = RiskResponse(
        lat=result.lat,
        lng=result.lng,
        flood_score=result.flood_score,
        landslide_score=result.landslide_score,
        earthquake_score=result.earthquake_score,
        overall_risk=result.overall_risk,
        computed_at=result.computed_at,
    )

    cache_set(cache_key, response, ttl=120)  # Cache for 2 minutes
    return response
