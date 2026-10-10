from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.db import Base


class RegularTask(Base):
    __tablename__ = "regular_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    employer_profile_id: Mapped[int] = mapped_column(ForeignKey("employer_profiles.id"), index=True)
    concept_id: Mapped[int | None] = mapped_column(ForeignKey("concepts.id"), nullable=True)
    statement: Mapped[str] = mapped_column(String(4000))
    task_format: Mapped[str] = mapped_column(String(32), default="multiple_choice")
    options: Mapped[list] = mapped_column(JSON, default=list)
    reference_answer: Mapped[int] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RegularTaskSubmission(Base):
    __tablename__ = "regular_task_submissions"
    __table_args__ = (UniqueConstraint("regular_task_id", "candidate_profile_id", name="uq_regular_submission"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    regular_task_id: Mapped[int] = mapped_column(ForeignKey("regular_tasks.id"), index=True)
    candidate_profile_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
