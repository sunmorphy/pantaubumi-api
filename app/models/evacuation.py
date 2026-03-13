from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EvacuationPoint(Base):
    """Static evacuation shelter / point data."""

    __tablename__ = "evacuation_points"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    lng: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    capacity: Mapped[int] = mapped_column(Integer, default=0)

    # e.g. "school", "mosque", "stadium", "community_hall"
    type: Mapped[str] = mapped_column(String(50), default="community_hall")
    address: Mapped[str] = mapped_column(String(500), default="")
