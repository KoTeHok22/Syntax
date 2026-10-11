from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from backend.core.labels import Specialization

GRADE_VALUES = ["junior", "middle", "senior"]


def validate_salary_range(salary_from: int, salary_to: int) -> None:
    if salary_from < 0 or salary_to < 0:
        raise ValueError("Зарплата не может быть отрицательной")
    if salary_to < salary_from:
        raise ValueError("Верхняя граница зарплаты не может быть меньше нижней")


class CandidateProfileUpdate(BaseModel):
    full_name: str | None = Field(default="", max_length=255)
    pvn_id: str | None = Field(default=None, max_length=64)
    contacts: dict = Field(default_factory=dict)
    stack: list[str] = Field(default_factory=list)
    years_of_experience: float = Field(default=0, ge=0)
    soft_skills: list[str] = Field(default_factory=list)
    specialization: Specialization | Literal[""] = ""
    city: str | None = Field(default="", max_length=128)
    work_format: Literal["", "remote", "office", "hybrid"] = ""
    avatar_data_url: str | None = None
    avatar_zoom: float | None = Field(default=None, ge=1, le=3)
    avatar_offset_x: float | None = Field(default=None, ge=-50, le=50)
    avatar_offset_y: float | None = Field(default=None, ge=-50, le=50)


class CandidateGradeUpdate(BaseModel):
    grade: Literal["junior", "middle", "senior"]


class CandidateProfileResponse(BaseModel):
    portfolio_evidence: dict | None = None
    id: int
    full_name: str
    contacts: dict
    stack: list
    years_of_experience: float
    soft_skills: list
    specialization: str
    city: str = ""
    work_format: str = ""
    grade: str | None
    category_id: int | None
    grade_changed_at: datetime | None
    grade_confirmed_at: datetime | None = None
    grade_confirmed: bool = False
    grade_valid_until: datetime | None = None
    is_visible: bool
    pvn_id: str | None = None
    is_pvn_verified: bool = False
    score: float = 0.0
    score_breakdown: dict = Field(default_factory=dict)
    avatar_data_url: str | None = None
    avatar_zoom: float = 1.0
    avatar_offset_x: float = 0.0
    avatar_offset_y: float = 0.0

    class Config:
        from_attributes = True


class OfficeInput(BaseModel):
    title: str = Field(default="", max_length=128)
    city: str = Field(min_length=1, max_length=128)
    address: str = Field(min_length=1, max_length=512)
    is_default: bool = False


class OfficeResponse(BaseModel):
    id: int
    title: str
    city: str
    address: str
    is_default: bool

    class Config:
        from_attributes = True


class EmployerProfileUpdate(BaseModel):
    company_name: str = Field(default="", max_length=255)
    description: str = Field(default="", max_length=2000)
    contacts: dict = Field(default_factory=dict)
    offices: list[OfficeInput] | None = Field(default=None, max_length=20)
    logo_data_url: str | None = None
    logo_zoom: float | None = Field(default=None, ge=1, le=3)
    logo_offset_x: float | None = Field(default=None, ge=-50, le=50)
    logo_offset_y: float | None = Field(default=None, ge=-50, le=50)


class EmployerProfileResponse(BaseModel):
    id: int
    company_name: str
    description: str
    contacts: dict
    offices: list[OfficeResponse] = Field(default_factory=list)
    logo_data_url: str | None = None
    logo_zoom: float = 1.0
    logo_offset_x: float = 0.0
    logo_offset_y: float = 0.0

    class Config:
        from_attributes = True


class CategoryResponse(BaseModel):
    id: int
    specialization: str
    grade: str
    candidate_count: int

    class Config:
        from_attributes = True


class CategoryPage(BaseModel):
    total: int
    items: list[CategoryResponse]


class DomainResponse(BaseModel):
    id: int
    slug: str
    title: str
    aliases: list[str] = Field(default_factory=list)
    candidate_count: int = 0
    score: float = 1.0


class DomainPage(BaseModel):
    total: int
    items: list[DomainResponse]


class DomainCreate(BaseModel):
    title: str = Field(min_length=2, max_length=128)
    aliases: list[str] = Field(default_factory=list, max_length=50)


class ScoreComponentResponse(BaseModel):
    label: str
    value: float
    weight: float


class CandidateCardResponse(BaseModel):
    candidate_profile_id: int
    grade: str | None
    specialization: str
    city: str = ""
    work_format: str = ""
    stack: list
    score: float
    score_breakdown: dict
    has_pvn_history: bool
    is_pvn_verified: bool = False
    pvn_achievements: list
    match_relevance: float
    final_score: float
    match_breakdown: dict = Field(default_factory=dict)
    proof_tier: str = "claimed"
    is_verified: bool = False


class CandidatePublicProfileResponse(BaseModel):
    candidate_profile_id: int
    grade: str | None = None
    specialization: str = ""
    stack_proof: list[dict] = Field(default_factory=list)
    years_of_experience: float = 0.0
    soft_skills: list[str] = Field(default_factory=list)
    city: str = ""
    work_format: str = ""
    proof_tier: str = "claimed"
    is_verified: bool = False
    score: float = 0.0
    score_breakdown: dict = Field(default_factory=dict)
    match_relevance: float | None = None
    pvn_achievements: list[dict] = Field(default_factory=list)


class VisibilityUpdate(BaseModel):
    is_visible: bool


class InvitationCreate(BaseModel):
    candidate_profile_id: int
    message: str = Field(min_length=1, max_length=4000)
    salary_from: int = Field(ge=0)
    salary_to: int = Field(ge=0)
    company_name: str = Field(min_length=1, max_length=255)
    contact_method: str = Field(min_length=1, max_length=255)

    @model_validator(mode="after")
    def check_salary(self):
        validate_salary_range(self.salary_from, self.salary_to)
        return self


class InvitationUpdate(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    salary_from: int = Field(ge=0)
    salary_to: int = Field(ge=0)
    company_name: str = Field(min_length=1, max_length=255)
    contact_method: str = Field(min_length=1, max_length=255)

    @model_validator(mode="after")
    def check_salary(self):
        validate_salary_range(self.salary_from, self.salary_to)
        return self


class InvitationResponse(BaseModel):
    id: int
    candidate_profile_id: int
    candidate_grade: str | None
    candidate_specialization: str | None
    candidate_stack: list[str]
    message: str
    salary_from: int
    salary_to: int
    company_name: str
    contact_method: str | None
    status: str
    candidate_contacts: dict | None
    created_at: str
    viewed_at: str | None = None
    responded_at: str | None = None


class VacancyCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=4000)
    stack: list[str] = Field(default_factory=list)
    specialization: str = Field(default="", max_length=64)
    grade: Literal["junior", "middle", "senior"] = "junior"
    salary_from: int = Field(ge=0)
    salary_to: int = Field(ge=0)

    @model_validator(mode="after")
    def check_salary(self):
        validate_salary_range(self.salary_from, self.salary_to)
        return self


class VacancyResponse(BaseModel):
    id: int
    title: str
    description: str
    stack: list
    specialization: str
    grade: str
    salary_from: int
    salary_to: int
    status: str

    class Config:
        from_attributes = True


class ApplicationCreate(BaseModel):
    vacancy_id: int
    message: str = Field(default="", max_length=4000)


class ApplicationResponse(BaseModel):
    id: int
    vacancy_id: int
    vacancy_title: str | None = None
    candidate_profile_id: int
    message: str
    status: str
    ats_delivery_status: str = "pending"
    ats_delivery_attempts: int = 0
    ats_delivery_error: str | None = None
    ats_delivered_at: datetime | None = None
    interview_at: datetime | None = None
    interview_duration: int | None = None
    interview_format: str | None = None
    interview_link: str | None = None
    interview_address: str | None = None
    model_config = {"from_attributes": True}


class ApplicationStatusUpdate(BaseModel):
    status: Literal["new", "viewed", "accepted", "rejected"]


class InterviewSchedule(BaseModel):
    scheduled_at: datetime
    duration_minutes: int = Field(default=60, ge=15, le=480)
    format: Literal["video", "onsite", "phone"]
    link: str | None = Field(default=None, max_length=512)
    address: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def check_channel(self):
        if self.format == "video" and not (self.link or "").strip():
            raise ValueError("Укажите ссылку на видеозвонок")
        if self.format == "onsite" and not (self.address or "").strip():
            raise ValueError("Укажите адрес офиса для очной встречи")
        return self
