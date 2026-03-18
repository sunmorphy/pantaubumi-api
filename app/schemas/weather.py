from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class WeatherResponse(BaseModel):
    """Raw sensor values for the nearest monitoring station."""
    rainfall_mm_per_hour: float
    river_level_m: float
    river_level_delta_per_hour: float   # positive = rising, negative = falling
    latest_magnitude: Optional[float]   # None if no recent seismic activity
    recorded_at: datetime
