from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("specialization", "grade", name="uq_category_spec_grade"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    specialization: Mapped[str] = mapped_column(String(64), index=True)
    grade: Mapped[str] = mapped_column(String(16), index=True)


try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - pgvector всегда в requirements
    Vector = None


class Domain(Base):
    __tablename__ = "domains"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(128))
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    is_curated: Mapped[bool] = mapped_column(default=False)
    embedding: Mapped[list | None] = mapped_column(
        (Vector(1024).with_variant(JSON, "sqlite") if Vector is not None else JSON),
        nullable=True,
    )
    embedding_text: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(primary_key=True)
    employer_profile_id: Mapped[int] = mapped_column(ForeignKey("employer_profiles.id"), index=True)
    candidate_profile_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    message: Mapped[str] = mapped_column(String(4000))
    salary_from: Mapped[int] = mapped_column(Integer)
    salary_to: Mapped[int] = mapped_column(Integer)
    company_name: Mapped[str] = mapped_column(String(255))
    contact_method: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default="sent", index=True)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    employer_profile: Mapped["EmployerProfile"] = relationship()
    candidate_profile: Mapped["CandidateProfile"] = relationship()


class Vacancy(Base):
    __tablename__ = "vacancies"

    id: Mapped[int] = mapped_column(primary_key=True)
    employer_profile_id: Mapped[int] = mapped_column(ForeignKey("employer_profiles.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(4000), default="")
    embedding: Mapped[list | None] = mapped_column(Vector(1024).with_variant(JSON, "sqlite"), nullable=True)
    embedding_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stack: Mapped[list] = mapped_column(JSON, default=list)
    specialization: Mapped[str] = mapped_column(String(64), default="")
    grade: Mapped[str] = mapped_column(String(16), default="")
    salary_from: Mapped[int] = mapped_column(Integer)
    salary_to: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id"), index=True)
    candidate_profile_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    message: Mapped[str] = mapped_column(String(4000), default="")
    status: Mapped[str] = mapped_column(String(16), default="new", index=True)
    ats_delivery_status: Mapped[str] = mapped_column(String(16), default="pending")
    ats_delivery_attempts: Mapped[int] = mapped_column(Integer, default=0)
    ats_delivery_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ats_delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    interview_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    interview_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interview_format: Mapped[str | None] = mapped_column(String(16), nullable=True)
    interview_link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    interview_address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    vacancy: Mapped["Vacancy"] = relationship()
    candidate_profile: Mapped["CandidateProfile"] = relationship()
