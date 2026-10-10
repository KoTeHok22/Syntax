from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.deps import get_candidate_profile, get_db, get_employer_profile
from backend.core.demo_filter import is_demo_visible
from backend.models import Application, CandidateProfile, EmployerProfile, Vacancy
from backend.schemas.matching import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationStatusUpdate,
    InterviewSchedule,
)
from backend.services.ats import deliver_application

router = APIRouter()


def application_response(application: Application, vacancy_title: str | None = None) -> ApplicationResponse:
    return ApplicationResponse(
        id=application.id,
        vacancy_id=application.vacancy_id,
        vacancy_title=vacancy_title,
        candidate_profile_id=application.candidate_profile_id,
        message=application.message,
        status=application.status,
        ats_delivery_status=application.ats_delivery_status,
        ats_delivery_attempts=application.ats_delivery_attempts,
        ats_delivery_error=application.ats_delivery_error,
        ats_delivered_at=application.ats_delivered_at,
        interview_at=application.interview_at,
        interview_duration=application.interview_duration,
        interview_format=application.interview_format,
        interview_link=application.interview_link,
        interview_address=application.interview_address,
    )


@router.post("/applications", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
def create_application(
    request: ApplicationCreate,
    db: Session = Depends(get_db),
    candidate_profile: CandidateProfile = Depends(get_candidate_profile),
):
    vacancy = db.get(Vacancy, request.vacancy_id)
    if vacancy is None or vacancy.status != "open":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Вакансия не найдена или закрыта")
    existing = (
        db.query(Application)
        .filter(
            Application.vacancy_id == request.vacancy_id,
            Application.candidate_profile_id == candidate_profile.id,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Отклик уже отправлен")
    application = Application(
        vacancy_id=request.vacancy_id,
        candidate_profile_id=candidate_profile.id,
        message=request.message,
        status="new",
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application_response(application)


@router.get("/applications/my", response_model=list[ApplicationResponse])
def list_my_applications(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    candidate_profile: CandidateProfile = Depends(get_candidate_profile),
):
    return (
        db.query(Application)
        .filter(Application.candidate_profile_id == candidate_profile.id)
        .order_by(Application.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/applications/incoming", response_model=list[ApplicationResponse])
def list_incoming_applications(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    employer_profile: EmployerProfile = Depends(get_employer_profile),
):
    rows = (
        db.query(Application, Vacancy)
        .join(Vacancy, Application.vacancy_id == Vacancy.id)
        .filter(Vacancy.employer_profile_id == employer_profile.id)
        .order_by(Application.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    visible_rows = [
        (application, vacancy)
        for application, vacancy in rows
        if is_demo_visible(vacancy.title, vacancy.description)
    ]
    title_by_vacancy = {
        application.id: vacancy.title for application, vacancy in visible_rows
    }
    return [
        application_response(application, title_by_vacancy.get(application.id))
        for application, _ in visible_rows
    ]


@router.put("/applications/{application_id}/status", response_model=ApplicationResponse)
def update_application_status(
    application_id: int,
    request: ApplicationStatusUpdate,
    db: Session = Depends(get_db),
    employer_profile: EmployerProfile = Depends(get_employer_profile),
):
    application = (
        db.query(Application)
        .join(Vacancy, Application.vacancy_id == Vacancy.id)
        .filter(Application.id == application_id, Vacancy.employer_profile_id == employer_profile.id)
        .first()
    )
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отклик не найден")
    application.status = request.status
    db.commit()
    db.refresh(application)
    vacancy = db.get(Vacancy, application.vacancy_id)
    if application.status == "accepted":
        try:
            deliver_application(db, application.id, employer_profile.id)
        except Exception:
            db.rollback()
    return application_response(application, vacancy.title if vacancy is not None else None)


@router.put("/applications/{application_id}/interview", response_model=ApplicationResponse)
def schedule_interview(
    application_id: int,
    request: InterviewSchedule,
    db: Session = Depends(get_db),
    employer_profile: EmployerProfile = Depends(get_employer_profile),
):
    application = (
        db.query(Application)
        .join(Vacancy, Application.vacancy_id == Vacancy.id)
        .filter(Application.id == application_id, Vacancy.employer_profile_id == employer_profile.id)
        .first()
    )
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отклик не найден")
    if application.status != "accepted":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Сначала примите отклик")
    scheduled_at = request.scheduled_at
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
    if scheduled_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Дата интервью не может быть в прошлом")
    application.interview_at = scheduled_at
    application.interview_duration = request.duration_minutes
    application.interview_format = request.format
    application.interview_link = (request.link or "").strip() or None
    application.interview_address = (request.address or "").strip() or None
    db.commit()
    db.refresh(application)
    vacancy = db.get(Vacancy, application.vacancy_id)
    return application_response(application, vacancy.title if vacancy is not None else None)
