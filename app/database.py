from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings

_test_mode = __import__("os").getenv("PANTAUBUMI_TESTING") == "1"


class Base(DeclarativeBase):
    pass


_is_postgres = settings.async_database_url.startswith("postgresql")

# In test mode use NullPool so asyncpg doesn't reuse connections across
# requests driven by the sync TestClient.
if _test_mode:
    engine = create_async_engine(
        settings.async_database_url,
        poolclass=NullPool,
    )
else:
    engine = create_async_engine(
        settings.async_database_url,
        echo=settings.app_env == "development",
        **({"pool_size": 10, "max_overflow": 20} if _is_postgres else {}),
    )

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
