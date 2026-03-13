"""
Open-Meteo Ingestion — hourly rainfall forecast for major Indonesian cities.

Open-Meteo provides free, no-auth weather forecasts. We poll key monitoring
locations (Jakarta, Bandung, Semarang, Surabaya, Makassar, Medan) and store
the next-hour precipitation forecast in the weather cache.
"""

import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.utils.cache import set_cached_weather

logger = logging.getLogger(__name__)

# Key monitoring locations across Indonesia (name, lat, lng)
MONITORING_STATIONS = [
    ("Jakarta",   -6.2088,  106.8456),
    ("Bandung",   -6.9175,  107.6191),
    ("Semarang",  -6.9932,  110.4203),
    ("Surabaya",  -7.2575,  112.7521),
    ("Makassar",  -5.1477,  119.4327),
    ("Medan",      3.5952,   98.6722),
    ("Palembang", -2.9761,  104.7754),
    ("Denpasar",  -8.6705,  115.2126),
    ("Manado",     1.4748,  124.8421),
    ("Jayapura",  -2.5337,  140.7181),
]


async def fetch_open_meteo(db: AsyncSession) -> None:
    """
    Fetch rainfall forecasts for all monitoring stations and update cache.
    The `db` param is included for API consistency; not used directly here.
    """
    for name, lat, lng in MONITORING_STATIONS:
        try:
            await _fetch_station(name, lat, lng)
        except Exception as e:
            logger.warning("Open-Meteo fetch failed for %s: %s", name, e)


async def _fetch_station(name: str, lat: float, lng: float) -> None:
    url = settings.open_meteo_base_url
    params = {
        "latitude": lat,
        "longitude": lng,
        "hourly": "precipitation,soil_moisture_0_to_7cm",
        "forecast_days": 1,
        "timezone": "Asia/Jakarta",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    hourly = data.get("hourly", {})
    precipitation = hourly.get("precipitation", [0.0])
    soil_moisture = hourly.get("soil_moisture_0_to_7cm", [0.3])

    # Use the next available (index 0 = current hour) values
    rainfall_mm = float(precipitation[0] if precipitation else 0.0)
    soil_sat = float(soil_moisture[0] if soil_moisture else 0.3)
    # Normalize soil moisture (typical range 0.01–0.57 m³/m³) to 0-1
    soil_sat_normalized = min(1.0, soil_sat / 0.57)

    set_cached_weather(lat, lng, {
        "rainfall_mm": rainfall_mm,
        "river_level_m": 1.0 + rainfall_mm / 50.0,  # proxy estimate
        "soil_saturation": soil_sat_normalized,
    })
    logger.debug("Open-Meteo updated %s: rainfall=%.1f mm, soil_sat=%.2f", name, rainfall_mm, soil_sat_normalized)
