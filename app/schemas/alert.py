from datetime import datetime
from pydantic import BaseModel


class AlertResponse(BaseModel):
    id: int
    type: str
    lat: float
    lng: float
    severity: str
    message: str
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}
