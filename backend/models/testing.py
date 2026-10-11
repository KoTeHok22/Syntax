from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.db import Base


class Concept(Base):
    __tablename__ = "concepts"
    __table_args__ = (UniqueConstraint("name", "grade", name="uq_concept_name_grade"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    domain: Mapped[str] = mapped_column(String(64), index=True)
    grade: Mapped[str] = mapped_column(String(16), index=True)
    difficulty_params: Mapped[dict] = mapped_column(JSON, default=dict)
    task_format: Mapped[str] = mapped_column(String(32), default="multiple_choice")
    question_template: Mapped[str] = mapped_column(String(2000), default="")
    correct_answer: Mapped[str] = mapped_column(String(1000), default="")
    distractors: Mapped[list] = mapped_column(JSON, default=list)


class TaskContext(Base):
    __tablename__ = "task_contexts"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(128), unique=True)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"), index=True)
    grade: Mapped[str] = mapped_column(String(16))
    statement: Mapped[str] = mapped_column(String(4000))
    task_format: Mapped[str] = mapped_column(String(32))
    options: Mapped[list] = mapped_column(JSON, default=list)
    reference_answer: Mapped[str] = mapped_column(JSON)
    image_data_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    flaw_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidate_profile_id: Mapped[int | None] = mapped_column(ForeignKey("candidate_profiles.id"), nullable=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("test_sessions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TestSession(Base):
    __tablename__ = "test_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_profile_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    grade: Mapped[str] = mapped_column(String(16))
    task_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    result_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verdict: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TestAnswer(Base):
    __tablename__ = "test_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("test_sessions.id"), index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    option_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    annotation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_correct: Mapped[bool] = mapped_column(default=False)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
