from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.alert import Alert
from app.schemas.alert import AlertResponse
from app.schemas.response import APIResponse, ok
from app.utils.geo import haversine

router = APIRouter()

DEFAULT_RADIUS_KM = 100.0
MAX_ALERTS = 50

_RESPONSE_200 = {
    "content": {
        "application/json": {
            "example": {
                "code": 200,
                "status": "Success",
                "message": None,
                "data": [
                    {
                        "id": 42,
                        "type": "earthquake",
                        "lat": -6.5,
                        "lng": 107.1,
                        "severity": "high",
                        "message": "[USGS] Gempa signifikan M5.2 sejauh 85 km. Bersiaplah. Lokasi: 23 km SE of Bogor",
                        "source": "usgs",
                        "created_at": "2026-03-14T03:55:00Z",
                    }
                ],
            }
        }
    }
}


@router.get(
    "/alerts",
    response_model=APIResponse[List[AlertResponse]],
    summary="Get recent alerts near a location",
    responses={200: _RESPONSE_200},
)
async def get_alerts(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    radius_km: float = Query(default=DEFAULT_RADIUS_KM, description="Search radius in km"),
    hours: int = Query(default=24, description="Look back N hours (1–168)", ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns recent disaster alerts near the given coordinates.

    **Data sources ingested every 5 minutes:**
    - `bmkg` — BMKG weather and earthquake observations
    - `usgs` — USGS significant earthquakes (M≥2.0) within Indonesia
    - `system` — Alerts generated internally when risk scores cross thresholds

    **Severity levels:** `low` · `medium` · `high` · `critical`

    **Type values:** `flood` · `landslide` · `earthquake`

    Returns at most **50 alerts**, sorted newest first.
    Distance is computed using the Haversine formula.
    """
    since = datetime.now(tz=timezone.utc) - timedelta(hours=hours)

    result = await db.execute(
        select(Alert)
        .where(Alert.created_at >= since)
        .order_by(Alert.created_at.desc())
        .limit(MAX_ALERTS * 5)
    )
    all_alerts = result.scalars().all()

    nearby = [
        a for a in all_alerts
        if haversine(lat, lng, a.lat, a.lng) <= radius_km
    ][:MAX_ALERTS]

    return ok(data=[AlertResponse.model_validate(a).model_dump(mode="json") for a in nearby])
