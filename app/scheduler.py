"""
APScheduler setup — runs all data ingestion tasks every 5 minutes.

Uses AsyncIOScheduler (compatible with FastAPI's asyncio event loop).
The scheduler is started in app.main's lifespan context.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _run_ingestion() -> None:
    """Runs all ingestion pipelines within a single DB session."""
    from app.ingestion.bmkg import fetch_bmkg
    from app.ingestion.open_meteo import fetch_open_meteo
    from app.ingestion.usgs import fetch_usgs
    from app.ingestion.petabencana import fetch_petabencana

    logger.info("Starting ingestion cycle...")
    async with AsyncSessionLocal() as db:
        # Run all sources; each handles its own errors internally
        await fetch_open_meteo(db)   # Weather/rainfall forecast (no alerts)
        await fetch_bmkg(db)         # Current weather + flood alerts
        await fetch_usgs(db)         # Seismic + earthquake alerts + push
        await fetch_petabencana(db)  # Community flood reports
    logger.info("Ingestion cycle complete.")


def start_scheduler() -> None:
    """Initialize and start the background scheduler."""
    scheduler.add_job(
        _run_ingestion,
        trigger=IntervalTrigger(minutes=settings.ingestion_interval_minutes),
        id="ingestion_cron",
        name="Data Ingestion Cron",
        replace_existing=True,
        misfire_grace_time=60,
    )
    scheduler.start()
    logger.info(
        "Scheduler started — ingestion every %d min",
        settings.ingestion_interval_minutes,
    )


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
