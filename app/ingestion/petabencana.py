"""
PetaBencana Ingestion — community flood reports from petabencana.id.

PetaBencana provides a public REST API of geotagged flood reports from
Indonesian communities. We fetch recent reports, run them through the
report verifier, and store them as Report records.
"""

import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.report import Report
from app.ai.report_verifier import verify_report

logger = logging.getLogger(__name__)

# Time window: last 30 minutes of reports
REPORT_WINDOW_HOURS = 1


async def fetch_petabencana(db: AsyncSession) -> None:
    """Fetch recent PetaBencana flood reports and upsert into the reports table."""
    url = settings.petabencana_base_url
    params = {
        "city": "id",  # All Indonesia
        "format": "json",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("PetaBencana fetch failed: %s", e)
        return

    features = data.get("result", {}).get("features", [])
    logger.info("PetaBencana: %d reports fetched", len(features))

    for feature in features:
        await _process_report(feature, db)


async def _process_report(feature: dict, db: AsyncSession) -> None:
    try:
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [None, None])

        if not coords or coords[0] is None:
            return

        lng = float(coords[0])
        lat = float(coords[1])
        report_id = str(props.get("pkey", ""))
        text = props.get("text", "") or props.get("title", "") or "Laporan banjir"
        created_at_str = props.get("created_at", "")

        # Skip duplicates (by checking source + report_id in text)
        existing = await db.execute(
            select(Report).where(
                Report.source == "petabencana",
                Report.text.contains(report_id),
            )
        )
        if existing.scalar_one_or_none():
            return  # Already stored

        # Verify the report text
        verification = verify_report(text)

        report = Report(
            lat=lat,
            lng=lng,
            text=f"[{report_id}] {text}",
            category="flood",  # PetaBencana is flood-only
            verified=verification.is_valid,
            verification_score=verification.confidence,
            source="petabencana",
        )
        db.add(report)

    except (KeyError, IndexError, ValueError, TypeError) as e:
        logger.warning("PetaBencana report parse error: %s", e)

    await db.commit()
