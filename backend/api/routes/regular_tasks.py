from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_candidate_profile, get_db, get_employer_profile
from backend.core.config import get_settings
from backend.core.testing import SESSION_STATUS_COMPLETED, SESSION_STATUS_PENDING, result_score
from backend.models import (
    Application,
    CandidateProfile,
    Concept,
    EmployerProfile,
    RegularTask,
    RegularTaskAnswer,
    RegularTaskSession,
    TaskContext,
    Vacancy,
)
from backend.schemas.regular_tasks import (
    ApplicationTaskResult,
    RegularTaskAnswerSubmit,
    RegularTaskCreate,
    RegularTaskResponse,
    RegularTaskSessionResponse,
    RegularTaskSessionResult,
)
from backend.services.task_generation import fallback_task, llm_task

router = APIRouter()


def aware_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


async def build_regular_task_content(
    db: Session, employer_profile: EmployerProfile, request: RegularTaskCreate
) -> RegularTask:
    if request.concept_id is not None:
        concept = db.get(Concept, request.concept_id)
        if concept is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Концепт не найден")
        draft = await llm_task(concept, concept.grade)
        if draft is None:
            context_labels = [row.label for row in db.query(TaskContext).all()]
            draft = fallback_task(concept, f"regular:{employer_profile.id}:{request.vacancy_id}:{concept.id}", context_labels)
        return RegularTask(
            employer_profile_id=employer_profile.id,
            vacancy_id=request.vacancy_id,
            concept_id=concept.id,
            statement=draft.statement,
            task_format=draft.task_format,
            options=draft.options,
            reference_answer=draft.reference_answer,
        )
    return RegularTask(
        employer_profile_id=employer_profile.id,
        vacancy_id=request.vacancy_id,
        statement=request.statement,
        task_format="multiple_choice",
        options=request.options,
        reference_answer=request.correct_index,
    )


def own_vacancy(db: Session, employer_profile: EmployerProfile, vacancy_id: int) -> Vacancy:
    vacancy = db.get(Vacancy, vacancy_id)
    if vacancy is None or vacancy.employer_profile_id != employer_profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Вакансия не найдена")
    return vacancy


def vacancy_tasks(db: Session, vacancy_id: int, active_only: bool = True) -> list[RegularTask]:
    query = db.query(RegularTask).filter(RegularTask.vacancy_id == vacancy_id)
    if active_only:
        query = query.filter(RegularTask.is_active == True)
    return query.order_by(RegularTask.id).all()


@router.post("/regular-tasks", response_model=RegularTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_regular_task(
    request: RegularTaskCreate,
    db: Session = Depends(get_db),
    employer_profile: EmployerProfile = Depends(get_employer_profile),
):
    own_vacancy(db, employer_profile, request.vacancy_id)
    task = await build_regular_task_content(db, employer_profile, request)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/employer/regular-tasks", response_model=list[RegularTaskResponse])
def list_my_regular_tasks(
    vacancy_id: int | None = None,
    db: Session = Depends(get_db),
    employer_profile: EmployerProfile = Depends(get_employer_profile),
):
    query = db.query(RegularTask).filter(RegularTask.employer_profile_id == employer_profile.id)
    if vacancy_id is not None:
        query = query.filter(RegularTask.vacancy_id == vacancy_id)
    return query.order_by(RegularTask.created_at.desc()).all()


@router.post("/employer/regular-tasks/{task_id}/close", response_model=RegularTaskResponse)
def close_regular_task(
    task_id: int,
    db: Session = Depends(get_db),
    employer_profile: EmployerProfile = Depends(get_employer_profile),
):
    task = db.get(RegularTask, task_id)
    if task is None or task.employer_profile_id != employer_profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задание не найдено")
    task.is_active = False
    db.commit()
    db.refresh(task)
    return task


@router.get("/employer/regular-tasks/results", response_model=list[ApplicationTaskResult])
def list_vacancy_results(
    vacancy_id: int,
    db: Session = Depends(get_db),
    employer_profile: EmployerProfile = Depends(get_employer_profile),
):
    own_vacancy(db, employer_profile, vacancy_id)
    sessions = (
        db.query(RegularTaskSession)
        .filter(RegularTaskSession.vacancy_id == vacancy_id)
        .order_by(RegularTaskSession.completed_at.desc())
        .all()
    )
    return [
        ApplicationTaskResult(
            application_id=session.application_id,
            vacancy_id=session.vacancy_id,
            status=session.status,
            task_count=session.task_count,
            correct_count=session.correct_count,
            result_score=session.result_score,
            forced_finish=session.forced_finish,
            completed_at=session.completed_at,
        )
        for session in sessions
    ]


def candidate_application(
    db: Session, candidate_profile: CandidateProfile, vacancy_id: int
) -> Application | None:
    return (
        db.query(Application)
        .filter(
            Application.vacancy_id == vacancy_id,
            Application.candidate_profile_id == candidate_profile.id,
        )
        .first()
    )


def session_response(db: Session, session: RegularTaskSession, tasks: list[RegularTask]) -> RegularTaskSessionResponse:
    return RegularTaskSessionResponse(
        id=session.id,
        application_id=session.application_id,
        vacancy_id=session.vacancy_id,
        status=session.status,
        task_count=session.task_count,
        correct_count=session.correct_count,
        result_score=session.result_score,
        forced_finish=session.forced_finish,
        expires_at=session.expires_at,
        completed_at=session.completed_at,
        tasks=[
            {
                "id": task.id,
                "statement": task.statement,
                "task_format": task.task_format,
                "options": task.options,
            }
            for task in tasks
        ],
    )


@router.get("/regular-tasks/vacancy/{vacancy_id}")
def vacancy_task_status(
    vacancy_id: int,
    db: Session = Depends(get_db),
    candidate_profile: CandidateProfile = Depends(get_candidate_profile),
):
    application = candidate_application(db, candidate_profile, vacancy_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отклик на вакансию не найден")
    tasks = vacancy_tasks(db, vacancy_id)
    session = (
        db.query(RegularTaskSession)
        .filter(RegularTaskSession.application_id == application.id)
        .first()
    )
    return {
        "application_id": application.id,
        "vacancy_id": vacancy_id,
        "task_count": len(tasks),
        "status": session.status if session is not None else "none",
        "result_score": session.result_score if session is not None else None,
        "correct_count": session.correct_count if session is not None else 0,
        "forced_finish": session.forced_finish if session is not None else False,
    }


@router.post("/regular-tasks/vacancy/{vacancy_id}/session", response_model=RegularTaskSessionResponse, status_code=status.HTTP_201_CREATED)
def start_regular_task_session(
    vacancy_id: int,
    db: Session = Depends(get_db),
    candidate_profile: CandidateProfile = Depends(get_candidate_profile),
):
    application = candidate_application(db, candidate_profile, vacancy_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отклик на вакансию не найден")
    tasks = vacancy_tasks(db, vacancy_id)
    if not tasks:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Для вакансии нет активных заданий")
    existing = (
        db.query(RegularTaskSession)
        .filter(RegularTaskSession.application_id == application.id)
        .first()
    )
    if existing is not None and existing.status == SESSION_STATUS_COMPLETED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Задания по вакансии уже пройдены")
    if existing is not None:
        return session_response(db, existing, tasks)
    settings = get_settings()
    session = RegularTaskSession(
        application_id=application.id,
        candidate_profile_id=candidate_profile.id,
        vacancy_id=vacancy_id,
        task_count=len(tasks),
        status=SESSION_STATUS_PENDING,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.session_time_limit_minutes),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session_response(db, session, tasks)


@router.post("/regular-tasks/sessions/{session_id}/answers", response_model=RegularTaskSessionResult)
def submit_regular_task_answers(
    session_id: int,
    submissions: list[RegularTaskAnswerSubmit],
    db: Session = Depends(get_db),
    candidate_profile: CandidateProfile = Depends(get_candidate_profile),
):
    session = db.get(RegularTaskSession, session_id)
    if session is None or session.candidate_profile_id != candidate_profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена")
    if session.status != SESSION_STATUS_PENDING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Сессия уже завершена")
    tasks = {task.id: task for task in vacancy_tasks(db, session.vacancy_id)}
    if not tasks:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Для вакансии нет активных заданий")
    unknown = [submission.regular_task_id for submission in submissions if submission.regular_task_id not in tasks]
    if unknown:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Задания не относятся к вакансии: {unknown}")
    if len({submission.regular_task_id for submission in submissions}) != len(submissions):
        raise HTTPException(status_code=400, detail="Ответ на задание можно отправить только один раз")
    now = datetime.now(timezone.utc)
    expired = session.expires_at is not None and now >= aware_utc(session.expires_at)
    correct = 0
    for submission in submissions:
        task = tasks[submission.regular_task_id]
        is_correct = submission.option_index == task.reference_answer
        if is_correct:
            correct += 1
        db.add(
            RegularTaskAnswer(
                session_id=session.id,
                regular_task_id=task.id,
                option_index=submission.option_index,
                is_correct=is_correct,
            )
        )
    session.task_count = len(tasks)
    session.correct_count = correct
    session.result_score = result_score(correct, len(tasks))
    session.status = SESSION_STATUS_COMPLETED
    session.forced_finish = expired
    session.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return RegularTaskSessionResult(
        id=session.id,
        status=session.status,
        task_count=session.task_count,
        correct_count=session.correct_count,
        result_score=session.result_score,
        forced_finish=session.forced_finish,
    )
