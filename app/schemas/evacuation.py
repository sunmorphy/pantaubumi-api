from pydantic import BaseModel, Field


class EvacuationResponse(BaseModel):
    id: int
    name: str
    lat: float
    lng: float
    capacity: int
    type: str
    address: str
    distance_km: float = Field(..., description="Distance from query point in kilometres")

    model_config = {"from_attributes": True}
