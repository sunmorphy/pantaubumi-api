from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class RiskResponse(BaseModel):
    lat: float
    lng: float
    flood_score: float = Field(..., ge=0.0, le=1.0, description="Flood risk score 0-1")
    landslide_score: float = Field(..., ge=0.0, le=1.0, description="Landslide risk score 0-1")
    earthquake_score: float = Field(..., ge=0.0, le=1.0, description="Earthquake risk score 0-1")
    overall_risk: Literal["low", "medium", "high", "critical"]
    computed_at: datetime

    model_config = {"from_attributes": True}
