from typing import List

from fastapi import APIRouter, Depends, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.report import Report
from app.schemas.report import ReportCreate, ReportResponse
from app.schemas.response import APIResponse, ok
from app.ai.report_verifier import verify_report
from app.utils.geo import haversine

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

DEFAULT_RADIUS_KM = 10.0
MAX_REPORTS = 50

_RESPONSE_200 = {
    "content": {
        "application/json": {
            "example": {
                "code": 200,
                "status": "Success",
                "message": None,
                "data": [
                    {
                        "id": 15,
                        "lat": -6.21,
                        "lng": 106.80,
                        "text": "Banjir parah di depan rumah saya, air sudah setinggi lutut!",
                        "category": "flood",
                        "verified": True,
                        "verification_score": 0.85,
                        "source": "user",
                        "created_at": "2026-03-14T03:40:00Z",
                    }
                ],
            }
        }
    }
}

_RESPONSE_201 = {
    "description": "Report Created",
    "content": {
        "application/json": {
            "example": {
                "code": 201,
                "status": "Created",
                "message": None,
                "data": {
                    "id": 16,
                    "lat": -6.2,
                    "lng": 106.8,
                    "text": "Banjir besar melanda kampung kami, air sudah setinggi dada orang dewasa!",
                    "category": "flood",
                    "verified": True,
                    "verification_score": 0.85,
                    "source": "user",
                    "created_at": "2026-03-14T04:10:00Z",
                },
            }
        }
    },
}

_RESPONSE_422 = {
    "description": "Validation Error",
    "content": {
        "application/json": {
            "example": {
                "code": 422,
                "status": "Unprocessable Entity",
                "message": "body → text: String should have at least 10 characters",
                "data": None,
            }
        }
    },
}

_RESPONSE_429 = {
    "description": "Rate Limit Exceeded",
    "content": {
        "application/json": {
            "example": {
                "code": 429,
                "status": "Too Many Requests",
                "message": "10 per 1 minute",
                "data": None,
            }
        }
    },
}


@router.get(
    "/reports",
    response_model=APIResponse[List[ReportResponse]],
    summary="Get verified community reports near a location",
    responses={200: _RESPONSE_200},
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

    return ok(data=[ReportResponse.model_validate(r).model_dump(mode="json") for r in nearby])


@router.post(
    "/reports",
    response_model=APIResponse[ReportResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new community disaster report",
    responses={201: _RESPONSE_201, 422: _RESPONSE_422, 429: _RESPONSE_429},
)
@limiter.limit("10/minute")
async def create_report(
    request: Request,
    payload: ReportCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a community disaster report. The text is automatically classified by the
    **IndoBERT NLP verifier** (keyword heuristic by default; set `INDOBERT_ENABLED=true`
    for the full HuggingFace model).

    **Classification output:**
    - `verified` — `true` if classified as a real disaster event
    - `verification_score` — classifier confidence (0–1)
    - `category` — detected category overrides your hint if a match is found

    **Valid categories:** `flood` · `landslide` · `earthquake` · `fire` · `other`

    **Rate limit:** 10 requests / minute / IP
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
    await db.flush()
    await db.refresh(report)

    return ok(data=ReportResponse.model_validate(report).model_dump(mode="json"), code=201)
