import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_candidate_profile, get_db, require_employer
from backend.core.categorization import assign_category
from backend.core.config import get_settings
from backend.core.labels import concept_domains_for_specialization
from backend.core.testing import (
    GRADE_ORDER,
    SESSION_STATUS_COMPLETED,
    SESSION_STATUS_PENDING,
    VERDICT_SUGGEST_LOWER,
    adaptive_verdict,
    grade_change_allowed,
    result_score,
    suggested_grade,
)
from backend.models import CandidateProfile, Concept, Task, TaskContext, TestSession
from backend.schemas.testing import (
    AnswerReview,
    AnswerSubmit,
    ConceptSummary,
    TestSessionCreate,
    TestSessionResponse,
    TestSessionResultResponse,
    TestSessionSummary,
)
from backend.services.task_generation import check_answer, fallback_task, llm_task
from backend.services.design_mockups import Mockup, build_llm_mockup_html, grade_annotation, normalize_annotation, render_html_to_png, renderer_available, to_data_url
from backend.services.semantic_matching import index_candidate

router = APIRouter()

DESIGN_ANNOTATION_FORMAT = "design_annotation"


async def grade_annotation_task(task: Task, submission) -> tuple[bool, str]:
    reference = task.reference_answer if isinstance(task.reference_answer, dict) else {}
    annotation = submission.annotation.model_dump() if submission.annotation is not None else None
    annotation = normalize_annotation(annotation)
    return await grade_annotation(
        task.image_data_url,
        reference.get("description", ""),
        submission.answer or "",
        annotation,
        reference.get("region"),
    )


async def build_annotation_task(concept, grade: str, seed: str, candidate_profile_id: int, session_id: int) -> Task | None:
    if not renderer_available():
        return None
    mockup: Mockup = await build_llm_mockup_html(seed)
    image_data_url = None
    try:
        png = await render_html_to_png(mockup.html)
        if len(png) <= 2 * 1024 * 1024:
            image_data_url = to_data_url(png)
    except Exception:
        image_data_url = None
    if image_data_url is None:
        return None
    return Task(
        concept_id=concept.id,
        grade=grade,
        statement=mockup.scenario,
        task_format=DESIGN_ANNOTATION_FORMAT,
        options=[],
        reference_answer={"flaw_id": mockup.flaw.flaw_id, "title": mockup.flaw.title, "description": mockup.flaw.description, "region": mockup.flaw.region},
        image_data_url=image_data_url,
        flaw_hint=mockup.flaw.title,
        candidate_profile_id=candidate_profile_id,
        session_id=session_id,
    )


@router.get("/concepts", response_model=list[ConceptSummary])
def list_concepts(
    db: Session = Depends(get_db),
    user=Depends(require_employer),
):
    concepts = db.query(Concept).order_by(Concept.domain, Concept.grade, Concept.id).all()
    return [
        ConceptSummary(id=concept.id, name=concept.name, domain=concept.domain, grade=concept.grade)
        for concept in concepts
    ]


def session_response(db: Session, session: TestSession) -> TestSessionResponse:
    tasks = db.query(Task).filter(Task.session_id == session.id).all()
    return TestSessionResponse(
        id=session.id,
        grade=session.grade,
        status=session.status,
        task_count=session.task_count,
        correct_count=session.correct_count,
        result_score=session.result_score,
        verdict=session.verdict,
        expires_at=session.expires_at.isoformat() if session.expires_at is not None else None,
        tasks=[
            {
                "id": t.id,
                "concept_id": t.concept_id,
                "grade": t.grade,
                "statement": t.statement,
                "task_format": t.task_format,
                "options": t.options,
                "image_data_url": t.image_data_url,
            }
            for t in tasks
        ],
    )


def apply_test_grade(db: Session, profile: CandidateProfile, session: TestSession) -> bool:
    now = datetime.now(timezone.utc)
    if session.verdict == VERDICT_SUGGEST_LOWER:
        return False
    profile.grade_confirmed_at = now
    current = profile.grade
    target = session.grade
    if current is None:
        profile.grade = target
        profile.grade_changed_at = now
        if profile.specialization:
            assign_category(db, profile, profile.specialization, target)
        return True
    if GRADE_ORDER.get(target, -1) > GRADE_ORDER.get(current, -1):
        settings = get_settings()
        if grade_change_allowed(profile.grade_changed_at, settings.grade_cooldown_months):
            profile.grade = target
            profile.grade_changed_at = now
            if profile.specialization:
                assign_category(db, profile, profile.specialization, target)
            return True
    return False


@router.post("/test-sessions", response_model=TestSessionResponse, status_code=status.HTTP_201_CREATED)
async def start_test_session(
    request: TestSessionCreate,
    db: Session = Depends(get_db),
    candidate_profile: CandidateProfile = Depends(get_candidate_profile),
):
    settings = get_settings()
    active = (
        db.query(TestSession)
        .filter(
            TestSession.candidate_profile_id == candidate_profile.id,
            TestSession.status == SESSION_STATUS_PENDING,
        )
        .first()
    )
    if active is not None:
        return session_response(db, active)
    session = TestSession(
        candidate_profile_id=candidate_profile.id,
        grade=request.grade,
        status=SESSION_STATUS_PENDING,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.session_time_limit_minutes),
    )
    db.add(session)
    db.flush()
    target_count = settings.tasks_per_session
    context_labels = [row.label for row in db.query(TaskContext).all()]
    concept_domains = concept_domains_for_specialization(candidate_profile.specialization)
    annotation_concept = None
    if renderer_available():
        annotation_query = db.query(Concept).filter(
            Concept.grade == request.grade,
            Concept.task_format == DESIGN_ANNOTATION_FORMAT,
        )
        if concept_domains:
            annotation_query = annotation_query.filter(Concept.domain.in_(concept_domains))
        annotation_concept = annotation_query.order_by(Concept.id).first()
    reserve_annotation = annotation_concept is not None and target_count > 1
    pool_limit = target_count - 1 if reserve_annotation else target_count
    pool_query = (
        db.query(Task)
        .join(Concept, Task.concept_id == Concept.id)
        .filter(
            Task.grade == request.grade,
            Task.candidate_profile_id.is_(None),
            Task.session_id.is_(None),
            Concept.task_format != DESIGN_ANNOTATION_FORMAT,
        )
    )
    if concept_domains:
        pool_query = pool_query.filter(Concept.domain.in_(concept_domains))
    pool_tasks = pool_query.order_by(Task.id).limit(pool_limit).all()
    generated = 0
    for pool_task in pool_tasks:
        pool_task.candidate_profile_id = candidate_profile.id
        pool_task.session_id = session.id
        generated += 1
    if reserve_annotation:
        annotation_task = await build_annotation_task(
            annotation_concept, request.grade, f"{candidate_profile.id}:{session.id}:a", candidate_profile.id, session.id
        )
        if annotation_task is not None:
            db.add(annotation_task)
            generated += 1
    remaining = target_count - generated
    if remaining > 0:
        concept_query = db.query(Concept).filter(Concept.grade == request.grade)
        if concept_domains:
            concept_query = concept_query.filter(Concept.domain.in_(concept_domains))
        concepts = concept_query.order_by(Concept.id).all()
        if not concepts and concept_domains:
            concepts = (
                db.query(Concept)
                .filter(Concept.grade == request.grade)
                .order_by(Concept.id)
                .all()
            )
        if concepts:
            objective = [c for c in concepts if c.task_format != DESIGN_ANNOTATION_FORMAT][:remaining]
            drafts = await asyncio.gather(
                *(llm_task(concept, request.grade) for concept in objective)
            )
            for concept, draft in zip(objective, drafts):
                if draft is None:
                    draft = fallback_task(concept, f"{candidate_profile.id}:{session.id}:{generated}", context_labels)
                if draft is None:
                    continue
                task = Task(
                    concept_id=concept.id,
                    grade=request.grade,
                    statement=draft.statement,
                    task_format=draft.task_format,
                    options=draft.options,
                    reference_answer=draft.reference_answer,
                    candidate_profile_id=candidate_profile.id,
                    session_id=session.id,
                )
                db.add(task)
                generated += 1
    session.task_count = generated
    if generated == 0:
        db.rollback()
        raise HTTPException(status_code=409, detail="Не удалось подготовить задания, попробуйте позже")
    db.commit()
    db.refresh(session)
    return session_response(db, session)


@router.get("/test-sessions", response_model=list[TestSessionSummary])
def list_test_sessions(
    db: Session = Depends(get_db),
    candidate_profile: CandidateProfile = Depends(get_candidate_profile),
):
    sessions = (
        db.query(TestSession)
        .filter(TestSession.candidate_profile_id == candidate_profile.id)
        .order_by(TestSession.created_at.desc())
        .all()
    )
    return sessions


@router.get("/test-sessions/{session_id}", response_model=TestSessionResponse)
def get_test_session(
    session_id: int,
    db: Session = Depends(get_db),
    candidate_profile: CandidateProfile = Depends(get_candidate_profile),
):
    session = db.get(TestSession, session_id)
    if session is None or session.candidate_profile_id != candidate_profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена")
    return session_response(db, session)


@router.post("/test-sessions/{session_id}/answers")
async def submit_answers(
    session_id: int,
    submissions: list[AnswerSubmit],
    db: Session = Depends(get_db),
    candidate_profile: CandidateProfile = Depends(get_candidate_profile),
):
    session = db.get(TestSession, session_id)
    if session is None or session.candidate_profile_id != candidate_profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена")
    if session.status != SESSION_STATUS_PENDING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Сессия уже завершена")
    tasks = {t.id: t for t in db.query(Task).filter(Task.session_id == session.id).all()}
    if session.task_count <= 0 or len(tasks) != session.task_count:
        raise HTTPException(status_code=409, detail="Сессия не содержит полного набора заданий")
    unknown = [s.task_id for s in submissions if s.task_id not in tasks]
    if unknown:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Задачи не принадлежат сессии: {unknown}")
    if len({submission.task_id for submission in submissions}) != len(submissions):
        raise HTTPException(status_code=400, detail="Ответ на задачу можно отправить только один раз")

    annotation_inputs = [s for s in submissions if tasks[s.task_id].task_format == DESIGN_ANNOTATION_FORMAT]
    annotation_feedback: dict[int, tuple[bool, str]] = {}
    if annotation_inputs:
        graded = await asyncio.gather(
            *(grade_annotation_task(tasks[s.task_id], s) for s in annotation_inputs)
        )
        annotation_feedback = {s.task_id: result for s, result in zip(annotation_inputs, graded)}

    def is_correct(submission) -> bool:
        if tasks[submission.task_id].task_format == DESIGN_ANNOTATION_FORMAT:
            return annotation_feedback.get(submission.task_id, (False, ""))[0]
        return check_answer(tasks[submission.task_id], submission)

    correct = sum(1 for s in submissions if is_correct(s))
    review = [
        AnswerReview(
            task_id=s.task_id,
            statement=tasks[s.task_id].statement,
            options=tasks[s.task_id].options,
            selected_index=s.option_index,
            reference_answer=tasks[s.task_id].reference_answer
            if isinstance(tasks[s.task_id].reference_answer, int)
            else None,
            is_correct=is_correct(s),
            task_format=tasks[s.task_id].task_format,
            answer_text=s.answer,
            feedback=annotation_feedback.get(s.task_id, (False, ""))[1] or None,
            image_data_url=tasks[s.task_id].image_data_url if tasks[s.task_id].task_format == DESIGN_ANNOTATION_FORMAT else None,
        )
        for s in submissions
    ]
    session.correct_count = correct
    session.result_score = result_score(correct, session.task_count)
    session.verdict = adaptive_verdict(correct, session.task_count, session.grade)
    session.status = SESSION_STATUS_COMPLETED
    session.completed_at = datetime.now(timezone.utc)
    grade_applied = apply_test_grade(db, candidate_profile, session)
    open_answers = [submission.answer for submission in submissions
                    if submission.answer and not tasks[submission.task_id].options
                    and is_correct(submission) and tasks[submission.task_id].task_format != DESIGN_ANNOTATION_FORMAT]
    if open_answers:
        candidate_profile.assessment_text = "\n".join(open_answers)[:12000]
    await index_candidate(candidate_profile)
    db.commit()
    db.refresh(session)
    return TestSessionResultResponse(
        id=session.id,
        grade=session.grade,
        task_count=session.task_count,
        correct_count=correct,
        result_score=session.result_score,
        verdict=session.verdict,
        suggested_grade=suggested_grade(session.grade, session.verdict),
        grade_applied=grade_applied,
        review=review,
    )
