from datetime import datetime
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FCMToken(Base):
    """Device FCM tokens for push notifications."""

    __tablename__ = "fcm_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # FCM registration token from Android client
    token: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, index=True)

    # Optional device identifier for deduplication
    device_id: Mapped[str] = mapped_column(String(200), default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
