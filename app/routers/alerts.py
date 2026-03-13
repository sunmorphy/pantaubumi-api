from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.alert import Alert
from app.schemas.alert import AlertResponse
from app.utils.geo import haversine

router = APIRouter()

DEFAULT_RADIUS_KM = 100.0
MAX_ALERTS = 50


@router.get("/alerts", response_model=List[AlertResponse], summary="Get recent alerts near a location")
async def get_alerts(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    radius_km: float = Query(default=DEFAULT_RADIUS_KM, description="Search radius in km"),
    hours: int = Query(default=24, description="Look back N hours", ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns recent disaster alerts within the given radius.
    Filters by time window (default: last 24 hours) and sorts by newest first.
    """
    since = datetime.now(tz=timezone.utc) - timedelta(hours=hours)

    result = await db.execute(
        select(Alert)
        .where(Alert.created_at >= since)
        .order_by(Alert.created_at.desc())
        .limit(MAX_ALERTS * 5)  # Fetch more, then filter by geo distance
    )
    all_alerts = result.scalars().all()

    # Filter by haversine distance
    nearby = [
        a for a in all_alerts
        if haversine(lat, lng, a.lat, a.lng) <= radius_km
    ][:MAX_ALERTS]

    return nearby
