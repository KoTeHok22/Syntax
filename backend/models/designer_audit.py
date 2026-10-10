from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.db import Base


class DesignerAudit(Base):
    __tablename__ = "designer_audits"
    __table_args__ = (UniqueConstraint("candidate_profile_id", "task_key", name="uq_designer_reference_task"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_profile_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    scenario: Mapped[str] = mapped_column(String(4000))
    task_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    screenshot_data_url: Mapped[str] = mapped_column(Text)
    reference_defects: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    violations: Mapped[list] = mapped_column(JSON, default=list)
    evaluation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
