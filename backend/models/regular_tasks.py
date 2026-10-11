from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.db import Base


class RegularTask(Base):
    __tablename__ = "regular_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    employer_profile_id: Mapped[int] = mapped_column(ForeignKey("employer_profiles.id"), index=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id"), index=True)
    concept_id: Mapped[int | None] = mapped_column(ForeignKey("concepts.id"), nullable=True)
    statement: Mapped[str] = mapped_column(String(4000))
    task_format: Mapped[str] = mapped_column(String(32), default="multiple_choice")
    options: Mapped[list] = mapped_column(JSON, default=list)
    reference_answer: Mapped[int] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RegularTaskSession(Base):
    __tablename__ = "regular_task_sessions"
    __table_args__ = (UniqueConstraint("application_id", name="uq_regular_session_application"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    candidate_profile_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id"), index=True)
    task_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    result_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    forced_finish: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RegularTaskAnswer(Base):
    __tablename__ = "regular_task_answers"
    __table_args__ = (UniqueConstraint("session_id", "regular_task_id", name="uq_regular_answer_task"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("regular_task_sessions.id"), index=True)
    regular_task_id: Mapped[int] = mapped_column(ForeignKey("regular_tasks.id"), index=True)
    option_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
