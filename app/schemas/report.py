from datetime import datetime
from pydantic import BaseModel, Field


class ReportCreate(BaseModel):
    lat: float = Field(..., description="Latitude of the incident")
    lng: float = Field(..., description="Longitude of the incident")
    text: str = Field(..., min_length=10, max_length=2000, description="Incident description in Indonesian")
    category: str = Field(
        default="other",
        description="Incident category: flood | landslide | earthquake | fire | other",
    )


class ReportResponse(BaseModel):
    id: int
    lat: float
    lng: float
    text: str
    category: str
    verified: bool
    verification_score: float
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}
