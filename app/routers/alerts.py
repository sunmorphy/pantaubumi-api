from datetime import datetime, timedelta, timezone
from typing import List, Optional

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
MAX_LIMIT = 60
DEFAULT_LIMIT = 20
# Over-fetch factor to compensate for Python-side geo filtering
_FETCH_MULTIPLIER = 10

_RESPONSE_200 = {
    "content": {
        "application/json": {
            "example": {
                "code": 200,
                "status": "Success",
                "message": None,
                "data": {
                    "items": [
                        {
                            "id": 42,
                            "type": "earthquake",
                            "lat": -6.5,
                            "lng": 107.1,
                            "severity": "high",
                            "message": "[USGS] Gempa signifikan M5.2 sejauh 85 km. Bersiaplah.",
                            "source": "usgs",
                            "created_at": "2026-03-14T03:55:00Z",
                        },
                        {
                            "id": 37,
                            "type": "flood",
                            "lat": -6.2,
                            "lng": 106.8,
                            "severity": "medium",
                            "message": "[BMKG] Curah hujan tinggi terdeteksi. Waspada banjir.",
                            "source": "bmkg",
                            "created_at": "2026-03-14T03:40:00Z",
                        },
                    ],
                    "next_cursor": 37,
                    "has_more": True,
                },
            }
        }
    }
}


@router.get(
    "/alerts",
    response_model=APIResponse[dict],
    summary="Get recent alerts near a location (paginated)",
    responses={200: _RESPONSE_200},
)
async def get_alerts(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    radius_km: float = Query(default=DEFAULT_RADIUS_KM, description="Search radius in km"),
    hours: int = Query(default=24, description="Look back N hours (1–168)", ge=1, le=168),
    limit: int = Query(
        default=DEFAULT_LIMIT,
        description=f"Results per page (1–{MAX_LIMIT})",
        ge=1,
        le=MAX_LIMIT,
    ),
    before_id: Optional[int] = Query(
        default=None,
        description=(
            "Cursor for the next page — pass the `next_cursor` value from the previous response. "
            "Returns alerts with `id < before_id`."
        ),
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns recent disaster alerts near the given coordinates, newest first.

    **Cursor-based pagination:**
    - Use `limit` to control page size (default 20, max 50)
    - On the first request, omit `before_id`
    - For subsequent pages, pass `next_cursor` from the previous response as `before_id`
    - When `has_more=false`, you have reached the last page

    **Data sources ingested every 5 minutes:**
    - `bmkg` — BMKG weather and earthquake observations
    - `usgs` — USGS significant earthquakes (M≥2.0) within Indonesia
    - `system` — Alerts generated internally when risk scores cross thresholds

    **Severity levels:** `low` · `medium` · `high` · `critical`
    """

    # Build query with optional cursor filter
    query = (
        select(Alert)
        .order_by(Alert.created_at.desc(), Alert.id.desc())
        .limit(limit * _FETCH_MULTIPLIER)  # over-fetch to compensate for geo filter
    )
    if before_id is not None:
        query = query.where(Alert.id < before_id)

    result = await db.execute(query)
    candidates: List[Alert] = list(result.scalars().all())

    # Python-side geo filter, then take the requested page size
    nearby: List[Alert] = []
    for a in candidates:
        if haversine(lat, lng, a.lat, a.lng) <= radius_km:
            nearby.append(a)
            if len(nearby) == limit:
                break

    has_more = len(nearby) == limit
    next_cursor: Optional[int] = nearby[-1].id if (has_more and nearby) else None

    return ok(data={
        "items": [AlertResponse.model_validate(a).model_dump(mode="json") for a in nearby],
        "next_cursor": next_cursor,
        "has_more": has_more,
    })
