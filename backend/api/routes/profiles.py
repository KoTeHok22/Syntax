import base64
import binascii
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.api.deps import (
    get_candidate_profile,
    get_db,
    get_employer_profile,
)
from backend.core.categorization import assign_category
from backend.core.config import get_settings
from backend.core.testing import (
    GRADE_ORDER,
    grade_change_allowed,
    grade_confirmation_active,
    grade_confirmation_expires_at,
)
from backend.models import CandidateProfile, CompanyOffice, PvnAchievement, TestSession, User
from backend.schemas.matching import (
    CandidateGradeUpdate,
    CandidateProfileResponse,
    CandidateProfileUpdate,
    EmployerProfileResponse,
    EmployerProfileUpdate,
    OfficeInput,
    VisibilityUpdate,
)
from backend.services.pdf_parser import PROFILE_FIELDS, parse_resume
from backend.services.profile_pdf import build_profile_pdf
from backend.services.candidate_score import candidate_score
from backend.services.semantic_matching import index_candidate

router = APIRouter()


def candidate_profile_response(profile: CandidateProfile, db: Session) -> CandidateProfileResponse:
    payload = CandidateProfileResponse.model_validate(profile)
    payload.grade_confirmed = grade_confirmation_active(profile.grade_confirmed_at)
    payload.grade_valid_until = grade_confirmation_expires_at(profile.grade_confirmed_at)
    payload.score, payload.score_breakdown = candidate_score(db, profile)
    return payload


@router.get("/candidates/me/profile.pdf")
def download_profile_pdf(
    profile: CandidateProfile = Depends(get_candidate_profile),
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(TestSession)
        .filter(TestSession.candidate_profile_id == profile.id)
        .order_by(TestSession.created_at.desc())
        .all()
    )
    achievements = (
        db.query(PvnAchievement)
        .filter(PvnAchievement.candidate_profile_id == profile.id)
        .all()
    )
    pdf_bytes = build_profile_pdf(profile, sessions, achievements)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="profile_{profile.id}.pdf"'},
    )


@router.get("/candidates/me", response_model=CandidateProfileResponse)
def get_my_candidate_profile(
    profile: CandidateProfile = Depends(get_candidate_profile),
    db: Session = Depends(get_db),
):
    return candidate_profile_response(profile, db)


@router.put("/candidates/me", response_model=CandidateProfileResponse)
async def update_my_candidate_profile(
    request: CandidateProfileUpdate,
    profile: CandidateProfile = Depends(get_candidate_profile),
    db: Session = Depends(get_db),
):
    for field, value in request.model_dump().items():
        setattr(profile, field, value)
    if profile.grade and profile.specialization:
        assign_category(db, profile, profile.specialization, profile.grade)
    await index_candidate(profile)
    db.commit()
    db.refresh(profile)
    return candidate_profile_response(profile, db)


@router.put("/candidates/me/grade", response_model=CandidateProfileResponse)
def update_my_grade(
    request: CandidateGradeUpdate,
    profile: CandidateProfile = Depends(get_candidate_profile),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    current_rank = GRADE_ORDER.get(profile.grade or "", -1)
    target_rank = GRADE_ORDER.get(request.grade, -1)
    if target_rank > current_rank:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Повышение грейда подтверждается тестом: пройдите тестирование на целевой грейд",
        )
    if not grade_change_allowed(profile.grade_changed_at, settings.grade_cooldown_months):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Смена грейда доступна не раньше чем через {settings.grade_cooldown_months} мес. после предыдущей смены",
        )
    if profile.grade != request.grade:
        profile.grade = request.grade
        profile.grade_changed_at = datetime.now(timezone.utc)
        if profile.specialization:
            assign_category(db, profile, profile.specialization, request.grade)
    db.commit()
    db.refresh(profile)
    return candidate_profile_response(profile, db)


@router.put("/candidates/me/visibility", response_model=CandidateProfileResponse)
def update_visibility(
    request: VisibilityUpdate,
    profile: CandidateProfile = Depends(get_candidate_profile),
    db: Session = Depends(get_db),
):
    profile.is_visible = request.is_visible
    db.commit()
    db.refresh(profile)
    return candidate_profile_response(profile, db)


@router.post("/candidates/me/resume")
async def upload_resume(
    file: UploadFile,
    profile: CandidateProfile = Depends(get_candidate_profile),
    db: Session = Depends(get_db),
):
    file_bytes = await file.read(5 * 1024 * 1024 + 1)
    if len(file_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF больше 5 МБ")
    parsed = await parse_resume(file_bytes)
    if parsed.get("invalid_pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Файл не является корректным PDF или не содержит текста")
    profile.resume_text = parsed.pop("resume_text", None)
    applied = {}
    for field, value in parsed.items():
        if field in PROFILE_FIELDS and value is not None:
            setattr(profile, field, value)
            applied[field] = value
    if profile.grade and profile.specialization:
        assign_category(db, profile, profile.specialization, profile.grade)
    await index_candidate(profile)
    db.commit()
    return {"applied": applied}


@router.get("/employers/me", response_model=EmployerProfileResponse)
def get_my_employer_profile(profile=Depends(get_employer_profile)):
    return profile


LOGO_ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp"}
LOGO_MAX_BYTES = 512 * 1024


def validate_logo_data_url(value: str) -> str:
    header, separator, payload = value.partition(",")
    if separator == "" or not header.startswith("data:") or ";base64" not in header:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Логотип должен быть изображением")
    mime = header[len("data:"):].split(";", 1)[0]
    if mime not in LOGO_ALLOWED_MIME:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Допустимы только PNG, JPEG и WebP")
    try:
        decoded_size = len(base64.b64decode(payload, validate=True))
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Логотип повреждён")
    if decoded_size > LOGO_MAX_BYTES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Логотип больше 512 КБ")
    return value


def normalize_offices(offices: list[OfficeInput]) -> list[OfficeInput]:
    if not offices:
        return []
    defaults = [index for index, office in enumerate(offices) if office.is_default]
    chosen = defaults[0] if defaults else 0
    return [
        office.model_copy(update={"is_default": index == chosen})
        for index, office in enumerate(offices)
    ]


@router.put("/employers/me", response_model=EmployerProfileResponse)
def update_my_employer_profile(
    request: EmployerProfileUpdate,
    profile=Depends(get_employer_profile),
    db: Session = Depends(get_db),
):
    profile.company_name = request.company_name
    profile.description = request.description
    profile.contacts = request.contacts
    if request.logo_data_url is not None:
        profile.logo_data_url = validate_logo_data_url(request.logo_data_url) if request.logo_data_url else None
        if profile.logo_data_url is None:
            profile.logo_zoom = 1.0
            profile.logo_offset_x = 0.0
            profile.logo_offset_y = 0.0
    if request.logo_zoom is not None:
        profile.logo_zoom = request.logo_zoom
    if request.logo_offset_x is not None:
        profile.logo_offset_x = request.logo_offset_x
    if request.logo_offset_y is not None:
        profile.logo_offset_y = request.logo_offset_y
    if request.offices is not None:
        profile.offices = [
            CompanyOffice(
                title=office.title,
                city=office.city,
                address=office.address,
                is_default=office.is_default,
            )
            for office in normalize_offices(request.offices)
        ]
    db.commit()
    db.refresh(profile)
    return profile
