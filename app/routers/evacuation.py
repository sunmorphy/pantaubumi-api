import httpx
from typing import List
import random

from fastapi import APIRouter, Depends, Query
from app.schemas.evacuation import EvacuationResponse
from app.schemas.response import APIResponse, ok
from app.utils.geo import haversine
from app.utils.cache import get_cached_evacuation, set_cached_evacuation

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
                        "name": "RSUD Dr. Soetomo",
                        "lat": -7.267,
                        "lng": 112.758,
                        "capacity": 200,
                        "type": "hospital",
                        "address": "Jl. Mayjen Prof. Dr. Moestopo",
                        "distance_km": 0.5,
                    }
                ],
            }
        }
    }
}


@router.get(
    "/evacuation",
    response_model=APIResponse[List[EvacuationResponse]],
    summary="Get live evacuation points via OpenStreetMap",
    responses={200: _RESPONSE_200},
)
async def get_evacuation(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    limit: int = Query(default=5, description="Max number of results (1-10)", ge=1, le=MAX_RESULTS),
):
    """
    Returns nearest evacuation shelters by polling OpenStreetMap (Overpass API)
    for real-world hospitals, schools, mosques, etc. taking into account distance.
    Results are heavily cached per ~1km grid to prevent rate-limiting.
    """
    cached = get_cached_evacuation(lat, lng)
    if cached is not None:
        # Re-sort cached results using exact queried lat/lng
        for p in cached:
            p["distance_km"] = round(haversine(lat, lng, p["lat"], p["lng"]), 2)
        cached.sort(key=lambda x: x["distance_km"])
        return ok(data=cached[:limit])

    # Fetch from Overpass API (3km radius)
    query = f"""
    [out:json][timeout:15];
    (
      node["amenity"~"hospital|clinic|community_centre|school|place_of_worship|police|fire_station"](around:3000,{lat},{lng});
      way["amenity"~"hospital|clinic|community_centre|school|place_of_worship|police|fire_station"](around:3000,{lat},{lng});
    );
    out center;
    """
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post("https://overpass-api.de/api/interpreter", data={"data": query}, timeout=15.0)
            resp.raise_for_status()
            osm_data = resp.json()
        except Exception as e:
            print("Overpass API failed:", e)
            return ok(data=[])

    elements = osm_data.get("elements", [])
    extracted = []
    
    for el in elements:
        tags = el.get("tags", {})
        
        # Coords are direct on nodes, but 'center' on ways
        el_lat = el.get("lat") or el.get("center", {}).get("lat")
        el_lng = el.get("lon") or el.get("center", {}).get("lon")
        
        if not el_lat or not el_lng:
            continue
            
        amenity = tags.get("amenity", "community_centre")
        name = tags.get("name", f"Unknown Shelter ({amenity.replace('_', ' ').title()})")
        addr = tags.get("addr:street", tags.get("addr:full", ""))
        
        dist = haversine(lat, lng, el_lat, el_lng)
        
        extracted.append({
            "id": el.get("id", random.randint(1000, 99999)),
            "name": name,
            "lat": el_lat,
            "lng": el_lng,
            "capacity": 200,  # Generic static fallback
            "type": amenity,
            "address": addr,
            "distance_km": round(dist, 2)
        })

    # Sort and Cache
    extracted.sort(key=lambda x: x["distance_km"])
    set_cached_evacuation(lat, lng, extracted)
    
    return ok(data=extracted[:limit])
