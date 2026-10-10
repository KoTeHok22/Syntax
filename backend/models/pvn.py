from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


class PvnAchievement(Base):
    __tablename__ = "pvn_achievements"
    __table_args__ = (UniqueConstraint("candidate_profile_id", "source_issuer", "external_id", name="uq_pvn_external_achievement"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_profile_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    achievement_type: Mapped[str] = mapped_column(String(64))
    level: Mapped[str] = mapped_column(String(32), default="")
    achieved_at: Mapped[date] = mapped_column(Date)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    source_issuer: Mapped[str | None] = mapped_column(String(512), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    candidate_profile: Mapped["CandidateProfile"] = relationship()
