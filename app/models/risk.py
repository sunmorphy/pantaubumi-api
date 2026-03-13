from datetime import datetime
from sqlalchemy import Float, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RiskData(Base):
    """Computed risk scores for a given geo-location."""

    __tablename__ = "risk_data"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    lng: Mapped[float] = mapped_column(Float, nullable=False, index=True)

    # AI model outputs (0.0 – 1.0)
    flood_score: Mapped[float] = mapped_column(Float, default=0.0)
    landslide_score: Mapped[float] = mapped_column(Float, default=0.0)
    earthquake_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Aggregated label: "low" | "medium" | "high" | "critical"
    overall_risk: Mapped[str] = mapped_column(String(20), default="low")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
