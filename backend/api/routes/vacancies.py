from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.deps import get_db, get_employer_profile
from backend.core.demo_filter import is_demo_visible
from backend.core.matching import VACANCY_CLOSED, VACANCY_OPEN
from backend.models import EmployerProfile, Vacancy
from backend.schemas.matching import VacancyCreate, VacancyResponse
from backend.services.semantic_matching import index_vacancy
from backend.services.vacancy_moderation import moderate_vacancy

router = APIRouter()


@router.post("/vacancies", response_model=VacancyResponse, status_code=status.HTTP_201_CREATED)
async def create_vacancy(
    request: VacancyCreate,
    db: Session = Depends(get_db),
    employer_profile: EmployerProfile = Depends(get_employer_profile),
):
    moderation = await moderate_vacancy(request)
    if moderation.blocked:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=moderation.reason)
    vacancy = Vacancy(
        employer_profile_id=employer_profile.id,
        title=request.title,
        description=request.description,
        stack=request.stack,
        specialization=request.specialization.strip().lower(),
        grade=request.grade,
        salary_from=request.salary_from,
        salary_to=request.salary_to,
        status=VACANCY_OPEN,
    )
    db.add(vacancy)
    await index_vacancy(vacancy)
    db.commit()
    db.refresh(vacancy)
    return vacancy


@router.get("/vacancies", response_model=list[VacancyResponse])
def list_vacancies(
    grade: str | None = None,
    specialization: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Vacancy).filter(Vacancy.status == VACANCY_OPEN)
    if grade is not None:
        query = query.filter(Vacancy.grade == grade)
    if specialization is not None:
        query = query.filter(Vacancy.specialization == specialization.strip().lower())
    vacancies = query.order_by(Vacancy.created_at.desc()).offset(skip).limit(limit).all()
    return [
        vacancy
        for vacancy in vacancies
        if is_demo_visible(vacancy.title, vacancy.description)
    ]


@router.get("/vacancies/my", response_model=list[VacancyResponse])
def list_my_vacancies(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    employer_profile: EmployerProfile = Depends(get_employer_profile),
):
    return (
        db.query(Vacancy)
        .filter(Vacancy.employer_profile_id == employer_profile.id)
        .order_by(Vacancy.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/vacancies/{vacancy_id}", response_model=VacancyResponse)
def get_vacancy(vacancy_id: int, db: Session = Depends(get_db)):
    vacancy = db.get(Vacancy, vacancy_id)
    if vacancy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Вакансия не найдена")
    return vacancy


@router.put("/vacancies/{vacancy_id}", response_model=VacancyResponse)
async def update_vacancy(
    vacancy_id: int,
    request: VacancyCreate,
    db: Session = Depends(get_db),
    employer_profile: EmployerProfile = Depends(get_employer_profile),
):
    vacancy = db.get(Vacancy, vacancy_id)
    if vacancy is None or vacancy.employer_profile_id != employer_profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Вакансия не найдена")
    moderation = await moderate_vacancy(request)
    if moderation.blocked:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=moderation.reason)
    vacancy.title = request.title
    vacancy.description = request.description
    vacancy.stack = request.stack
    vacancy.specialization = request.specialization.strip().lower()
    vacancy.grade = request.grade
    vacancy.salary_from = request.salary_from
    vacancy.salary_to = request.salary_to
    await index_vacancy(vacancy)
    db.commit()
    db.refresh(vacancy)
    return vacancy


@router.post("/vacancies/{vacancy_id}/close", response_model=VacancyResponse)
def close_vacancy(
    vacancy_id: int,
    db: Session = Depends(get_db),
    employer_profile: EmployerProfile = Depends(get_employer_profile),
):
    vacancy = db.get(Vacancy, vacancy_id)
    if vacancy is None or vacancy.employer_profile_id != employer_profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Вакансия не найдена")
    vacancy.status = VACANCY_CLOSED
    db.commit()
    db.refresh(vacancy)
    return vacancy
