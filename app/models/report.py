from datetime import datetime
from sqlalchemy import Boolean, Float, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Report(Base):
    """Community-submitted disaster report, analyzed by IndoBERT."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    lng: Mapped[float] = mapped_column(Float, nullable=False, index=True)

    text: Mapped[str] = mapped_column(Text, nullable=False)

    # e.g. "flood", "landslide", "earthquake", "fire", "other"
    category: Mapped[str] = mapped_column(String(50), default="other")

    # IndoBERT verification output
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Source: "user" | "petabencana"
    source: Mapped[str] = mapped_column(String(50), default="user")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
