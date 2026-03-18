from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ReportCreate(BaseModel):
    lat: float = Field(..., description="Latitude of the incident")
    lng: float = Field(..., description="Longitude of the incident")
    text: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Incident description in Indonesian (min 10 characters)",
    )
    category: str = Field(
        default="other",
        description="Incident category hint — overridden by NLP classifier if detected",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "Flood report (Jakarta)",
                    "value": {
                        "lat": -6.2088,
                        "lng": 106.8456,
                        "text": "Banjir besar melanda kampung kami, air sudah setinggi dada orang dewasa!",
                        "category": "flood",
                    },
                },
                {
                    "summary": "Landslide report (Bogor)",
                    "value": {
                        "lat": -6.5971,
                        "lng": 106.8060,
                        "text": "Tanah longsor di lereng bukit belakang desa, beberapa rumah tertimbun!",
                        "category": "landslide",
                    },
                },
            ]
        }
    }


class ReportResponse(BaseModel):
    id: int
    lat: float
    lng: float
    text: str
    category: str
    verified: bool
    verification_score: float
    source: str
    image_url: Optional[str] = None
    flag_count: int = 0
    # device_id is intentionally excluded — never expose who submitted a report
    created_at: datetime

    model_config = {"from_attributes": True}

