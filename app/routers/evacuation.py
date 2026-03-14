from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.evacuation import EvacuationPoint
from app.schemas.evacuation import EvacuationResponse
from app.schemas.response import APIResponse, ok
from app.utils.geo import haversine

router = APIRouter()

MAX_RESULTS = 10

_RESPONSE_200 = {
    "content": {
        "application/json": {
            "example": {
                "code": 200,
                "status": "Success",
                "message": None,
                "data": [
                    {
                        "id": 1,
                        "name": "Gedung Serbaguna RW 05",
                        "lat": -6.201,
                        "lng": 106.849,
                        "capacity": 200,
                        "type": "community_hall",
                        "address": "Jl. Merdeka No. 1, Jakarta Pusat",
                        "distance_km": 0.18,
                    },
                    {
                        "id": 7,
                        "name": "SDN Menteng 01",
                        "lat": -6.195,
                        "lng": 106.844,
                        "capacity": 300,
                        "type": "school",
                        "address": "Jl. HOS Cokroaminoto, Jakarta",
                        "distance_km": 0.94,
                    },
                ],
            }
        }
    }
}


@router.get(
    "/evacuation",
    response_model=APIResponse[List[EvacuationResponse]],
    summary="Get nearest evacuation points",
    responses={200: _RESPONSE_200},
)
async def get_evacuation(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    limit: int = Query(default=5, description="Max number of results (1–10)", ge=1, le=MAX_RESULTS),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the nearest evacuation shelters sorted by distance from the given coordinates.
    """
    result = await db.execute(select(EvacuationPoint))
    all_points = result.scalars().all()

    points_with_dist = [
        (point, haversine(lat, lng, point.lat, point.lng))
        for point in all_points
    ]
    points_with_dist.sort(key=lambda x: x[1])

    data = [
        EvacuationResponse(
            id=point.id,
            name=point.name,
            lat=point.lat,
            lng=point.lng,
            capacity=point.capacity,
            type=point.type,
            address=point.address,
            distance_km=round(dist, 2),
        ).model_dump(mode="json")
        for point, dist in points_with_dist[:limit]
    ]

    return ok(data=data)
