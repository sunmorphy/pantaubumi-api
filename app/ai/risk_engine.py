"""
Risk Engine — orchestrates all AI models for a given lat/lng.

Given a location, this module:
1. Fetches latest ingested weather/seismic data from cache or DB
2. Runs flood + landslide + earthquake models
3. Aggregates into an overall risk label
4. Stores results to the risk_data table
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from app.ai.flood_model import predict_flood_risk
from app.ai.landslide_model import predict_landslide_risk
from app.ai.earthquake_alert import assess_earthquake
from app.utils.cache import get_cached_weather, get_cached_seismic

logger = logging.getLogger(__name__)


@dataclass
class RiskResult:
    lat: float
    lng: float
    flood_score: float
    landslide_score: float
    earthquake_score: float
    overall_risk: str
    computed_at: datetime


def _compute_overall_risk(flood: float, landslide: float, earthquake: float) -> str:
    """Aggregate three scores into a single risk label."""
    max_score = max(flood, landslide, earthquake)
    if max_score >= 0.75:
        return "critical"
    elif max_score >= 0.50:
        return "high"
    elif max_score >= 0.25:
        return "medium"
    else:
        return "low"


async def compute_risk(lat: float, lng: float) -> RiskResult:
    """
    Main entry-point for computing combined disaster risk at a location.
    Uses latest cached ingestion data; falls back to neutral defaults.
    """
    # ── Pull latest weather data from cache ───────────────────────
    weather = get_cached_weather(lat, lng)
    rainfall_mm = weather.get("rainfall_mm", 0.0)
    river_level_m = weather.get("river_level_m", 1.0)
    soil_saturation = weather.get("soil_saturation", 0.3)

    # ── Pull latest seismic data from cache ───────────────────────
    seismic = get_cached_seismic(lat, lng)
    magnitude = seismic.get("magnitude", 0.0)
    distance_km = seismic.get("distance_km", 9999.0)

    # ── Run AI models ─────────────────────────────────────────────
    try:
        flood_score = predict_flood_risk(rainfall_mm, river_level_m)
    except Exception as e:
        logger.warning("Flood model failed: %s", e)
        flood_score = 0.0

    try:
        landslide_score = predict_landslide_risk(rainfall_mm, soil_saturation)
    except Exception as e:
        logger.warning("Landslide model failed: %s", e)
        landslide_score = 0.0

    eq_result = assess_earthquake(magnitude, distance_km)
    earthquake_score = eq_result.score

    overall_risk = _compute_overall_risk(flood_score, landslide_score, earthquake_score)

    return RiskResult(
        lat=lat,
        lng=lng,
        flood_score=flood_score,
        landslide_score=landslide_score,
        earthquake_score=earthquake_score,
        overall_risk=overall_risk,
        computed_at=datetime.now(tz=timezone.utc),
    )
