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

app = FastAPI(
    title="PantauBumi API",
    description="AI-Powered Multi-Disaster Early Warning System for Indonesia",
    version="0.1.0",
    # Hide interactive docs in production — serve them via /docs only in dev
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

# ── Routers ────────────────────────────────────────────────────
app.include_router(risk_router, tags=["Risk"])
app.include_router(alerts_router, tags=["Alerts"])
app.include_router(evacuation_router, tags=["Evacuation"])
app.include_router(reports_router, tags=["Reports"])
app.include_router(fcm_router, tags=["Push Notifications"])


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "pantau-bumi-api"}
