from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.report import Report
from app.schemas.report import ReportCreate, ReportResponse
from app.ai.report_verifier import verify_report
from app.utils.geo import haversine

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


DEFAULT_RADIUS_KM = 10.0
MAX_REPORTS = 50


@router.get(
    "/reports",
    response_model=List[ReportResponse],
    summary="Get verified community reports near a location",
)
async def get_reports(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    radius: float = Query(default=DEFAULT_RADIUS_KM, description="Search radius in km", gt=0, le=500),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns verified community disaster reports within the given radius.
    Only returns reports with `verified=True`.
    """
    result = await db.execute(
        select(Report)
        .where(Report.verified == True)  # noqa: E712
        .order_by(Report.created_at.desc())
        .limit(MAX_REPORTS * 5)
    )
    all_reports = result.scalars().all()

    nearby = [
        r for r in all_reports
        if haversine(lat, lng, r.lat, r.lng) <= radius
    ][:MAX_REPORTS]

    return nearby


@router.post(
    "/reports",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new community disaster report",
)
@limiter.limit("10/minute")
async def create_report(
    request: Request,
    payload: ReportCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a disaster report. The text is automatically analyzed by the
    IndoBERT report verifier to assign a `verified` flag and `verification_score`.
    """
    verification = verify_report(payload.text)

    report = Report(
        lat=payload.lat,
        lng=payload.lng,
        text=payload.text,
        category=verification.category if verification.category != "other" else payload.category,
        verified=verification.is_valid,
        verification_score=verification.confidence,
        source="user",
    )
    db.add(report)
    await db.flush()   # Get the auto-generated ID before commit
    await db.refresh(report)
    return report
