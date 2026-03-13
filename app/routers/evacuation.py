from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.evacuation import EvacuationPoint
from app.schemas.evacuation import EvacuationResponse
from app.utils.geo import haversine

router = APIRouter()

MAX_RESULTS = 10


@router.get(
    "/evacuation",
    response_model=List[EvacuationResponse],
    summary="Get nearest evacuation points",
)
async def get_evacuation(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    limit: int = Query(default=5, description="Max number of results", ge=1, le=MAX_RESULTS),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the nearest evacuation shelters sorted by distance from the given coordinates.
    """
    result = await db.execute(select(EvacuationPoint))
    all_points = result.scalars().all()

    # Compute distances and sort
    points_with_dist = [
        (point, haversine(lat, lng, point.lat, point.lng))
        for point in all_points
    ]
    points_with_dist.sort(key=lambda x: x[1])

    return [
        EvacuationResponse(
            id=point.id,
            name=point.name,
            lat=point.lat,
            lng=point.lng,
            capacity=point.capacity,
            type=point.type,
            address=point.address,
            distance_km=round(dist, 2),
        )
        for point, dist in points_with_dist[:limit]
    ]
