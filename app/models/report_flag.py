from datetime import datetime
from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ReportFlag(Base):
    """
    Tracks which device flagged which report.
    Unique constraint on (report_id, device_id) prevents double-flagging.
    When a Report's flag_count reaches 3, visible is set to False.
    """

    __tablename__ = "report_flags"
    __table_args__ = (
        UniqueConstraint("report_id", "device_id", name="uq_report_flag_device"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
