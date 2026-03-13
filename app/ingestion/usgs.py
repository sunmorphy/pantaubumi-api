"""
USGS Ingestion — seismic activity from the USGS Earthquake Hazards Program.

Polls the USGS FDSN event API for earthquakes in and around Indonesia in the
last 10 minutes, magnitude ≥ 2.0. For each significant quake:
  1. Updates the seismic cache for affected area
  2. Triggers earthquake alert logic
  3. Creates Alert DB records for high/critical events
  4. Sends push notifications for critical alerts
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.alert import Alert
from app.ai.earthquake_alert import assess_earthquake
from app.utils.cache import set_cached_seismic
from app.utils.geo import haversine

logger = logging.getLogger(__name__)

# Indonesia centroid (approx.)
INDONESIA_CENTER = (-2.5, 118.0)

# Bounding box for USGS query (Indonesia + nearby seas)
INDONESIA_BBOX = "minlatitude=-11&maxlatitude=7&minlongitude=95&maxlongitude=141"


async def fetch_usgs(db: AsyncSession) -> None:
    """Fetch recent earthquakes near Indonesia and process alerts."""
    now = datetime.now(tz=timezone.utc)
    start_time = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S")

    url = settings.usgs_base_url
    params = {
        "format": "geojson",
        "starttime": start_time,
        "minmagnitude": 2.0,
        "minlatitude": -11,
        "maxlatitude": 7,
        "minlongitude": 95,
        "maxlongitude": 141,
        "orderby": "time",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("USGS fetch failed: %s", e)
        return

    features = data.get("features", [])
    logger.info("USGS: %d earthquakes fetched", len(features))

    for feature in features:
        await _process_quake(feature, db)


async def _process_quake(feature: dict, db: AsyncSession) -> None:
    try:
        props = feature["properties"]
        coords = feature["geometry"]["coordinates"]

        quake_lng = float(coords[0])
        quake_lat = float(coords[1])
        magnitude = float(props.get("mag", 0.0))
        place = props.get("place", "Unknown location")

        # Distance from Indonesia center
        dist_km = haversine(INDONESIA_CENTER[0], INDONESIA_CENTER[1], quake_lat, quake_lng)

        # Update seismic cache
        set_cached_seismic(quake_lat, quake_lng, {
            "magnitude": magnitude,
            "distance_km": 0.0,  # distance from quake epicenter to itself = 0
        })

        # Assess alert level
        result = assess_earthquake(magnitude, dist_km)
        if result.triggered:
            alert = Alert(
                type="earthquake",
                lat=quake_lat,
                lng=quake_lng,
                severity=result.severity,
                message=f"[USGS] {result.message} Lokasi: {place}",
                source="usgs",
            )
            db.add(alert)
            await db.commit()
            logger.info(
                "Earthquake alert [%s] M%.1f at (%.3f, %.3f) dist=%.0f km",
                result.severity, magnitude, quake_lat, quake_lng, dist_km,
            )

            # Push notifications for high/critical
            if result.severity in ("high", "critical"):
                await _send_push_for_quake(alert, db)

    except (KeyError, IndexError, ValueError) as e:
        logger.warning("USGS quake parse error: %s", e)


async def _send_push_for_quake(alert: Alert, db: AsyncSession) -> None:
    """Broadcast a push notification for severe earthquake alerts."""
    try:
        from app.services.firebase import broadcast_notification
        from app.models.fcm_token import FCMToken
        from sqlalchemy import select

        result = await db.execute(select(FCMToken))
        tokens = [row.token for row in result.scalars().all()]

        if tokens:
            await broadcast_notification(
                tokens=tokens,
                title="⚠️ Peringatan Gempa Bumi",
                body=alert.message,
            )
            logger.info("Push notification sent to %d devices", len(tokens))
    except Exception as e:
        logger.error("Failed to send push notifications: %s", e)
