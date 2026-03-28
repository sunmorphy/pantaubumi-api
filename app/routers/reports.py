from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status, Form, UploadFile, File
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.report import Report
from app.models.report_flag import ReportFlag
from app.schemas.report import ReportCreate, ReportResponse
from app.schemas.flag import FlagResponse
from app.schemas.response import APIResponse, ok
from app.ai.report_verifier import verify_report
from app.utils.geo import haversine

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

DEFAULT_RADIUS_KM = 10.0
MAX_REPORTS = 50
FLAG_HIDE_THRESHOLD = 3          # Auto-hide after this many flags
DEVICE_RATE_LIMIT_COUNT = 5      # Max reports per device per hour
DEVICE_RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds
DEVICE_COOLDOWN_SECONDS = 600    # 10-minute cooldown between submissions


# ── Response example definitions ───────────────────────────────────────────────

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
                        "category": "Banjir",
                        "verified": True,
                        "verification_score": 0.85,
                        "source": "user",
                        "flag_count": 0,
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
                    "category": "Banjir",
                    "verified": True,
                    "verification_score": 0.85,
                    "source": "user",
                    "flag_count": 0,
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
    "description": "Rate Limit or Cooldown",
    "content": {
        "application/json": {
            "examples": {
                "rate_limit": {
                    "summary": "Hourly limit reached",
                    "value": {
                        "code": 429,
                        "status": "Too Many Requests",
                        "message": "Device report limit reached: 5 reports per hour. Try again later.",
                        "data": None,
                    },
                },
                "cooldown": {
                    "summary": "Cooldown active",
                    "value": {
                        "code": 429,
                        "status": "Too Many Requests",
                        "message": "Please wait 8 minutes before submitting another report.",
                        "data": None,
                    },
                },
            }
        }
    },
}

_FLAG_RESPONSE_200 = {
    "content": {
        "application/json": {
            "example": {
                "code": 200,
                "status": "Success",
                "message": None,
                "data": {"report_id": 16, "flag_count": 2, "hidden": False},
            }
        }
    }
}

_FLAG_RESPONSE_409 = {
    "description": "Already Flagged",
    "content": {
        "application/json": {
            "example": {
                "code": 409,
                "status": "Conflict",
                "message": "You have already flagged this report.",
                "data": None,
            }
        }
    },
}


# ── Helper: extract and validate X-Device-ID header ────────────────────────────

def _get_device_id(x_device_id: Optional[str] = Header(default=None)) -> str:
    """
    Extract the anonymous device ID from the X-Device-ID header.
    Falls back to an empty string (IP-based limiting still applies).
    """
    return (x_device_id or "").strip()[:128]


# ── GET /reports ───────────────────────────────────────────────────────────────

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
    category: Optional[str] = Query(default=None, description="Optional filter by hazard category (e.g., Banjir, Longsor, Gempa)"),
    limit: int = Query(default=50, description="Max number of reports to return", gt=0, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns verified community disaster reports within the given radius.
    Only returns reports where `visible=True` (not hidden by flags).
    Can be optionally filtered by `category`.
    """
    query = select(Report).where(Report.visible == True)  # noqa: E712
    
    if category:
        query = query.where(Report.category == category)
        
    query = query.order_by(Report.created_at.desc()).limit(limit * 5)
    
    result = await db.execute(query)
    all_reports = result.scalars().all()

    nearby = [
        r for r in all_reports
        if haversine(lat, lng, r.lat, r.lng) <= radius
    ][:limit]

    return ok(data=[ReportResponse.model_validate(r).model_dump(mode="json") for r in nearby])


# ── POST /reports ──────────────────────────────────────────────────────────────

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
    lat: float = Form(..., description="Latitude of the incident"),
    lng: float = Form(..., description="Longitude of the incident"),
    text: str = Form(..., min_length=10, max_length=2000, description="Incident description"),
    category: str = Form("Lainnya", description="Incident category hint"),
    image: Optional[UploadFile] = File(None, description="Optional photo of the incident"),
    db: AsyncSession = Depends(get_db),
    device_id: str = Depends(_get_device_id),
):
    """
    Submit a community disaster report. The text is automatically classified by the
    **IndoBERT NLP verifier** (keyword heuristic by default; set `INDOBERT_ENABLED=true`
    for the full HuggingFace model).

    **Anonymous device identity:**
    Send your device's UUID in the `X-Device-ID` header. This is never returned in responses
    and is used only for server-side anti-spam enforcement. If omitted, IP-based limiting applies.

    **Server-side anti-spam (per device):**
    - Max **5 reports per hour** per device
    - **10-minute cooldown** between consecutive submissions

    **Classification output:**
    - `verified` — `true` if classified as a real disaster event
    - `verification_score` — classifier confidence (0–1)
    - `category` — detected category overrides your hint if a match is found

    **Valid categories:** `Banjir` · `Longsor` · `Gempa` · `Kebakaran` · `Lainnya`
    """
    # ── Per-device rate checks (only when a device_id is provided) ─────────────
    if device_id:
        now = datetime.now(tz=timezone.utc)
        window_start = now - timedelta(seconds=DEVICE_RATE_LIMIT_WINDOW)
        cooldown_start = now - timedelta(seconds=DEVICE_COOLDOWN_SECONDS)

        # Count reports in last hour for this device
        count_result = await db.execute(
            select(func.count(Report.id))
            .where(Report.device_id == device_id)
            .where(Report.created_at >= window_start)
        )
        hour_count = count_result.scalar_one()

        if hour_count >= DEVICE_RATE_LIMIT_COUNT:
            raise HTTPException(
                status_code=429,
                detail=f"Device report limit reached: {DEVICE_RATE_LIMIT_COUNT} reports per hour. Try again later.",
            )

        # Check cooldown: most recent report by this device
        last_result = await db.execute(
            select(Report.created_at)
            .where(Report.device_id == device_id)
            .order_by(Report.created_at.desc())
            .limit(1)
        )
        last_at = last_result.scalar_one_or_none()
        if last_at and last_at >= cooldown_start:
            wait_minutes = int((DEVICE_COOLDOWN_SECONDS - (now - last_at).total_seconds()) // 60) + 1
            raise HTTPException(
                status_code=429,
                detail=f"Please wait {wait_minutes} minute(s) before submitting another report.",
            )

    # ── AI classification ──────────────────────────────────────────────────────
    verification = verify_report(text)

    final_category = verification.category if verification.category != "Lainnya" else category

    # ── Cloudflare R2 Image Upload ──
    image_url = None
    if image:
        from app.services.storage import upload_image_to_storage
        file_bytes = await image.read()
        image_url = await upload_image_to_storage(file_bytes, image.filename, image.content_type)

    report_db = Report(
        lat=lat,
        lng=lng,
        text=text,
        category=final_category,
        image_url=image_url if image_url else None,
        verified=verification.is_valid,
        verification_score=verification.confidence,
        device_id=device_id,
        source="user",
    )
    db.add(report_db)
    await db.flush()
    await db.refresh(report_db)

    return ok(data=ReportResponse.model_validate(report_db).model_dump(mode="json"), code=201)


# ── POST /reports/{id}/flag ────────────────────────────────────────────────────

@router.post(
    "/reports/{report_id}/flag",
    response_model=APIResponse[FlagResponse],
    summary="Flag a report as inaccurate or a hoax",
    responses={200: _FLAG_RESPONSE_200, 409: _FLAG_RESPONSE_409},
)
@limiter.limit("30/minute")
async def flag_report(
    request: Request,
    report_id: int,
    db: AsyncSession = Depends(get_db),
    device_id: str = Depends(_get_device_id),
):
    """
    Flag a community report as inaccurate or a potential hoax.

    - Each device can flag the same report **only once** (409 if already flagged)
    - When `flag_count` reaches **3**, the report is automatically hidden from `GET /reports`
    - Hidden reports remain in the database and can be restored by an admin

    Send your device UUID in the `X-Device-ID` header. Anonymous flagging (without header)
    uses `"anonymous"` as device ID — note this means unlimited anonymous flags from different IPs.
    """
    if not device_id:
        device_id = "anonymous"

    # Verify the report exists and is visible
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")

    # Insert flag — unique constraint will raise IntegrityError on duplicate
    flag = ReportFlag(report_id=report_id, device_id=device_id)
    db.add(flag)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="You have already flagged this report.")

    # Increment flag count and potentially hide the report
    report.flag_count += 1
    if report.flag_count >= FLAG_HIDE_THRESHOLD:
        report.visible = False

    await db.flush()
    await db.refresh(report)

    return ok(data=FlagResponse(
        report_id=report.id,
        flag_count=report.flag_count,
        hidden=not report.visible,
    ).model_dump())
