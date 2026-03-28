"""
In-memory TTL cache for latest ingested data.

Stores the most recently fetched weather and seismic data keyed by
grid-snapped lat/lng (0.5° resolution). This avoids re-running AI models
on the same location every second between scheduler runs.
"""

import time
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Cache TTL in seconds (slightly longer than ingestion interval)
TTL_SECONDS = 360

# In-memory stores
_weather_store: Dict[str, dict] = {}
_seismic_store: Dict[str, dict] = {}
_timestamps: Dict[str, float] = {}


def _grid_key(lat: float, lng: float, prefix: str) -> str:
    """Snap to 0.5° grid for cache key."""
    snapped_lat = round(round(lat * 2) / 2, 1)
    snapped_lng = round(round(lng * 2) / 2, 1)
    return f"{prefix}:{snapped_lat}:{snapped_lng}"


def _is_fresh(key: str) -> bool:
    return key in _timestamps and (time.time() - _timestamps[key]) < TTL_SECONDS


# ── Weather ───────────────────────────────────────────────────────────────────

def set_cached_weather(lat: float, lng: float, data: dict) -> None:
    from datetime import datetime, timezone as _tz
    key = _grid_key(lat, lng, "wx")
    # Compute river level delta from the previous reading
    prev = _weather_store.get(key, {})
    prev_level = float(prev.get("river_level_m", data.get("river_level_m", 1.0)))
    curr_level = float(data.get("river_level_m", 1.0))
    delta = curr_level - prev_level
    _weather_store[key] = {
        **data,
        "river_level_delta_per_hour": delta,
        "recorded_at": datetime.now(tz=_tz.utc).isoformat(),
    }
    _timestamps[key] = time.time()


def get_cached_weather(lat: float, lng: float) -> dict:
    from datetime import datetime, timezone as _tz
    key = _grid_key(lat, lng, "wx")
    if _is_fresh(key):
        return _weather_store[key]
    # Return neutral defaults when no fresh data is available
    return {
        "rainfall_mm": 0.0,
        "river_level_m": 1.0,
        "soil_saturation": 0.3,
        "river_level_delta_per_hour": 0.0,
        "recorded_at": datetime.now(tz=_tz.utc).isoformat(),
    }


# ── Seismic ───────────────────────────────────────────────────────────────────

def set_cached_seismic(lat: float, lng: float, data: dict) -> None:
    key = _grid_key(lat, lng, "eq")
    _seismic_store[key] = data
    _timestamps[key] = time.time()

def get_cached_seismic(lat: float, lng: float) -> dict:
    key = _grid_key(lat, lng, "eq")
    if _is_fresh(key):
        return _seismic_store[key]
        
    # TEMPORARY TEST: Simulate a massive M8.5 earthquake 5km away!
    return {"magnitude": 8.5, "distance_km": 5.0} 



# ── Generic TTL cache ─────────────────────────────────────────────────────────

_generic_store: Dict[str, Tuple[Any, float]] = {}


def cache_set(key: str, value: Any, ttl: int = TTL_SECONDS) -> None:
    _generic_store[key] = (value, time.time() + ttl)


def cache_get(key: str) -> Optional[Any]:
    if key in _generic_store:
        value, expiry = _generic_store[key]
        if time.time() < expiry:
            return value
        _generic_store.pop(key, None)
    return None


# ── Evacuation ────────────────────────────────────────────────────────────────

def _evac_grid_key(lat: float, lng: float) -> str:
    """Snap to ~1km grid (0.01 deg) for caching Overpass API."""
    snapped_lat = round(lat, 2)
    snapped_lng = round(lng, 2)
    return f"evac:{snapped_lat}:{snapped_lng}"


def set_cached_evacuation(lat: float, lng: float, data: list) -> None:
    # 24 hour TTL for static buildings
    key = _evac_grid_key(lat, lng)
    cache_set(key, data, ttl=86400)


def get_cached_evacuation(lat: float, lng: float) -> Optional[list]:
    key = _evac_grid_key(lat, lng)
    return cache_get(key)
