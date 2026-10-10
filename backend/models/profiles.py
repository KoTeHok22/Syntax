from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from backend.db import Base


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    contacts: Mapped[dict] = mapped_column(JSON, default=dict)
    stack: Mapped[list] = mapped_column(JSON, default=list)
    years_of_experience: Mapped[int] = mapped_column(Float, default=0.0)
    soft_skills: Mapped[list] = mapped_column(JSON, default=list)
    resume_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessment_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    portfolio_evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    embedding: Mapped[list | None] = mapped_column(Vector(1024).with_variant(JSON, "sqlite"), nullable=True)
    embedding_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    specialization: Mapped[str] = mapped_column(String(64), default="")
    grade: Mapped[str | None] = mapped_column(String(16), nullable=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    grade_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grade_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_visible: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    user: Mapped["User"] = relationship()


class EmployerProfile(Base):
    __tablename__ = "employer_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    company_name: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(String(2000), default="")
    contacts: Mapped[dict] = mapped_column(JSON, default=dict)
    ats_webhook_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    logo_data_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_zoom: Mapped[float] = mapped_column(Float, default=1.0)
    logo_offset_x: Mapped[float] = mapped_column(Float, default=0.0)
    logo_offset_y: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    user: Mapped["User"] = relationship()
    offices: Mapped[list["CompanyOffice"]] = relationship(
        back_populates="employer_profile",
        cascade="all, delete-orphan",
        order_by="CompanyOffice.id",
    )


class CompanyOffice(Base):
    __tablename__ = "company_offices"

    id: Mapped[int] = mapped_column(primary_key=True)
    employer_profile_id: Mapped[int] = mapped_column(ForeignKey("employer_profiles.id"), index=True)
    title: Mapped[str] = mapped_column(String(128), default="")
    city: Mapped[str] = mapped_column(String(128), default="")
    address: Mapped[str] = mapped_column(String(512), default="")
    is_default: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    employer_profile: Mapped["EmployerProfile"] = relationship(back_populates="offices")
