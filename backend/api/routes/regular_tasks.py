from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import (
    get_candidate_profile,
    get_db,
    get_employer_profile,
)
from backend.core.demo_filter import is_demo_visible
from backend.models import (
    CandidateProfile,
    Concept,
    EmployerProfile,
    RegularTask,
    RegularTaskSubmission,
    TaskContext,
)
from backend.schemas.regular_tasks import (
    RegularTaskAnswer,
    RegularTaskAnswerResponse,
    RegularTaskCreate,
    RegularTaskResponse,
    RegularTaskSubmissionResponse,
)
from backend.services.task_generation import fallback_task, llm_task

router = APIRouter()


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
            draft = fallback_task(concept, f"regular:{employer_profile.id}:{concept.id}", context_labels)
        return RegularTask(
            employer_profile_id=employer_profile.id,
            concept_id=concept.id,
            statement=draft.statement,
            task_format=draft.task_format,
            options=draft.options,
            reference_answer=draft.reference_answer,
        )
    return RegularTask(
        employer_profile_id=employer_profile.id,
        statement=request.statement,
        task_format="multiple_choice",
        options=request.options,
        reference_answer=request.correct_index,
    )


@router.post("/regular-tasks", response_model=RegularTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_regular_task(
    request: RegularTaskCreate,
    db: Session = Depends(get_db),
    employer_profile: EmployerProfile = Depends(get_employer_profile),
):
    task = await build_regular_task_content(db, employer_profile, request)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/employer/regular-tasks", response_model=list[RegularTaskResponse])
def list_my_regular_tasks(
    db: Session = Depends(get_db),
    employer_profile: EmployerProfile = Depends(get_employer_profile),
):
    return (
        db.query(RegularTask)
        .filter(RegularTask.employer_profile_id == employer_profile.id)
        .order_by(RegularTask.created_at.desc())
        .all()
    )


@router.get("/employer/regular-tasks/{task_id}/submissions", response_model=list[RegularTaskSubmissionResponse])
def list_submissions(
    task_id: int,
    db: Session = Depends(get_db),
    employer_profile: EmployerProfile = Depends(get_employer_profile),
):
    task = db.get(RegularTask, task_id)
    if task is None or task.employer_profile_id != employer_profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задание не найдено")
    return (
        db.query(RegularTaskSubmission)
        .filter(RegularTaskSubmission.regular_task_id == task_id)
        .order_by(RegularTaskSubmission.submitted_at.desc())
        .all()
    )


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


@router.get("/regular-tasks", response_model=list[RegularTaskResponse])
def list_available_regular_tasks(
    db: Session = Depends(get_db),
    candidate_profile: CandidateProfile = Depends(get_candidate_profile),
):
    answered_ids = [
        row[0]
        for row in db.query(RegularTaskSubmission.regular_task_id)
        .filter(RegularTaskSubmission.candidate_profile_id == candidate_profile.id)
        .all()
    ]
    query = db.query(RegularTask).filter(RegularTask.is_active == True)
    if answered_ids:
        query = query.filter(RegularTask.id.notin_(answered_ids))
    tasks = query.order_by(RegularTask.created_at.desc()).all()
    return [task for task in tasks if is_demo_visible(task.statement)]


@router.post("/regular-tasks/{task_id}/answer", response_model=RegularTaskAnswerResponse)
def answer_regular_task(
    task_id: int,
    request: RegularTaskAnswer,
    db: Session = Depends(get_db),
    candidate_profile: CandidateProfile = Depends(get_candidate_profile),
):
    task = db.get(RegularTask, task_id)
    if task is None or not task.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задание не найдено или закрыто")
    existing = (
        db.query(RegularTaskSubmission)
        .filter(
            RegularTaskSubmission.regular_task_id == task_id,
            RegularTaskSubmission.candidate_profile_id == candidate_profile.id,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ответ уже отправлен")
    is_correct = request.option_index == task.reference_answer
    db.add(
        RegularTaskSubmission(
            regular_task_id=task_id,
            candidate_profile_id=candidate_profile.id,
            is_correct=is_correct,
        )
    )
    db.commit()
    return RegularTaskAnswerResponse(regular_task_id=task_id, is_correct=is_correct)
