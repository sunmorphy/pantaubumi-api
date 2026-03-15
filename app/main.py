import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import engine, Base
from app.scheduler import start_scheduler, stop_scheduler
from app.routers.risk import router as risk_router
from app.routers.alerts import router as alerts_router
from app.routers.evacuation import router as evacuation_router
from app.routers.reports import router as reports_router
from app.routers.fcm import router as fcm_router

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO if settings.app_env == "production" else logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

# ── Rate Limiter ───────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────
    # Create tables if they don't exist (use Alembic for production migrations)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Start the background cron scheduler
    start_scheduler()

    yield

    # ── Shutdown ───────────────────────────────────────────────
    stop_scheduler()
    await engine.dispose()


_is_production = settings.app_env == "production"

_DESCRIPTION = """
## PantauBumi API 🌏

Backend for the **PantauBumi** AI-Powered Multi-Disaster Early Warning System for Indonesia.

### What it does
- Pulls weather, seismic, and flood data from external APIs **every 5 minutes**
- Runs the data through **XGBoost / Random Forest / rule-based** AI models
- Serves risk scores, alerts, evacuation points, and community reports to the Android app

### Response Envelope
Every response — success or error — is wrapped in the same envelope:
```json
{ "code": 200, "status": "Success", "message": null, "data": { } }
```

### Rate Limits
| Scope | Limit |
|---|---|
| Global (all endpoints) | 60 req / min / IP |
| `POST /reports` | 10 req / min / IP |
| `POST /fcm-token` | 20 req / min / IP |
"""

_TAGS_METADATA = [
    {
        "name": "Health",
        "description": "Service liveness check. Use `/health` to verify the API is running before making other calls.",
    },
    {
        "name": "Risk",
        "description": (
            "AI-computed disaster risk scores for a geographic coordinate. "
            "Combines **Flood** (XGBoost), **Landslide** (Random Forest), and "
            "**Earthquake** (rule-based) models into a single `overall_risk` label. "
            "Results are cached per location for 2 minutes."
        ),
    },
    {
        "name": "Alerts",
        "description": (
            "Recent disaster alerts ingested from **BMKG**, **USGS**, and the internal risk engine. "
            "Filtered by geographic radius and time window."
        ),
    },
    {
        "name": "Evacuation",
        "description": (
            "Nearest evacuation shelter points sorted by Haversine distance from the query coordinate. "
            "Seed the `evacuation_points` table with your local shelter data before use."
        ),
    },
    {
        "name": "Reports",
        "description": (
            "Community-submitted disaster reports with built-in anti-spam protection.\n\n"
            "**Anonymous device identity:** Send a stable UUID in the `X-Device-ID` header. "
            "Generated once on app install — the user never sees it.\n\n"
            "**Per-device limits (server-side):**\n"
            "- Max **5 reports per hour** per device ID\n"
            "- **10-minute cooldown** between consecutive submissions\n\n"
            "**AI verification:** IndoBERT classifier filters spam before any report goes public. "
            "Only `verified=true` **and** `visible=true` reports appear in `GET /reports`.\n\n"
            "**Community flagging:** `POST /reports/{id}/flag` — 3 unique flags auto-hides a report."
        ),
    },
    {
        "name": "Push Notifications",
        "description": (
            "Register Android device FCM tokens to receive push notifications when a "
            "`high` or `critical` severity alert is triggered in the user's area."
        ),
    },
]

app = FastAPI(
    title="PantauBumi API",
    description=_DESCRIPTION,
    version="1.0.0",
    contact={
        "name": "PantauBumi Team",
        "url": "https://github.com/sunmorphy/pantaubumi-api",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    openapi_tags=_TAGS_METADATA,
    # Hide interactive docs in production
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
    lifespan=lifespan,
)

# ── Rate limiter state ─────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
# allow_credentials=True is forbidden with wildcard origin per the CORS spec.
# When origins = ["*"] we disable credentials; in production set explicit origins.
_allow_creds = settings.cors_origins != "*"
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=_allow_creds,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
)


# ── Security headers middleware ─────────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    start = time.time()
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    if _is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Process-Time"] = str(round(time.time() - start, 4))
    return response

# ── Custom error handlers ──────────────────────────────────────────────────────
from fastapi import Request as _Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: _Request, exc: RequestValidationError):
    # Extract a readable message from the first validation error
    errors = exc.errors()
    if errors:
        first = errors[0]
        field = " → ".join(str(loc) for loc in first.get("loc", []))
        msg = f"{field}: {first['msg']}" if field else first["msg"]
    else:
        msg = "Validation error"
    return JSONResponse(
        status_code=422,
        content={"code": 422, "status": "Unprocessable Entity", "message": msg, "data": None},
    )


from fastapi import HTTPException as _HTTPException

_STATUS_LABELS = {
    400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
    404: "Not Found", 409: "Conflict", 429: "Too Many Requests",
    500: "Internal Server Error",
}


@app.exception_handler(_HTTPException)
async def http_exception_handler(_request: _Request, exc: _HTTPException):
    """Wrap all HTTPException raises in the standard response envelope."""
    label = _STATUS_LABELS.get(exc.status_code, "Error")
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "status": label, "message": exc.detail, "data": None},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(_request: _Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"code": 500, "status": "Internal Server Error", "message": "Internal Server Error", "data": None},
    )



# ── Routers ────────────────────────────────────────────────────
app.include_router(risk_router, tags=["Risk"])
app.include_router(alerts_router, tags=["Alerts"])
app.include_router(evacuation_router, tags=["Evacuation"])
app.include_router(reports_router, tags=["Reports"])
app.include_router(fcm_router, tags=["Push Notifications"])


@app.get("/health", tags=["Health"])
async def health_check():
    return {"code": 200, "status": "Success", "message": None, "data": {"service": "pantau-bumi-api"}}

