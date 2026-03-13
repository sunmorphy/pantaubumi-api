from datetime import datetime
from sqlalchemy import Float, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Alert(Base):
    """Disaster alert emitted by the ingestion pipeline."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Disaster type: "flood" | "landslide" | "earthquake"
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)

    # Severity: "low" | "medium" | "high" | "critical"
    severity: Mapped[str] = mapped_column(String(20), default="medium")

    message: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(100), default="system")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
