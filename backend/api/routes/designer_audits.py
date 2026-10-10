from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy import and_, or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.api.deps import get_candidate_profile, get_db
from backend.models.designer_audit import DesignerAudit
from backend.models.profiles import CandidateProfile
from backend.schemas.designer_audit import (
    DesignerAuditCreate,
    DesignerAuditResponse,
    DesignerAuditSubmit,
    HeuristicChecklistItem,
    PortfolioMetricsResponse,
)
from backend.services.designer_audit import (
    MAX_PORTFOLIO_BYTES,
    MAX_SCREENSHOT_BYTES,
    REFERENCE_SCENARIO,
    REFERENCE_TASK_KEY,
    evaluate_audit,
    extract_portfolio_metrics,
    get_checklist,
    reference_task_image,
    screenshot_data_url,
    validate_screenshot_data_url,
)
from backend.services.designer_mockups import generate_mockup, mockup_data_url, render_html_to_png


router = APIRouter(prefix="/designer-audits", tags=["designer-audits"])


def audit_response(audit: DesignerAudit) -> DesignerAuditResponse:
    return DesignerAuditResponse(
        id=audit.id, scenario=audit.scenario, task_key=audit.task_key, screenshot_data_url=audit.screenshot_data_url,
        status=audit.status, checklist=get_checklist(), violations=audit.violations,
        evaluation=audit.evaluation, created_at=audit.created_at, submitted_at=audit.submitted_at,
    )


def owned_audit(audit_id: int, profile: CandidateProfile, db: Session) -> DesignerAudit:
    audit = db.query(DesignerAudit).filter(
        DesignerAudit.id == audit_id, DesignerAudit.candidate_profile_id == profile.id,
    ).first()
    if audit is None:
        raise HTTPException(status_code=404, detail="Аудит не найден")
    return audit


@router.get("/checklist", response_model=list[HeuristicChecklistItem])
def checklist(profile: CandidateProfile = Depends(get_candidate_profile)):
    return get_checklist()


@router.post("", response_model=DesignerAuditResponse, status_code=201)
def create_audit(
    request: DesignerAuditCreate,
    profile: CandidateProfile = Depends(get_candidate_profile),
    db: Session = Depends(get_db),
):
    try:
        image = validate_screenshot_data_url(request.screenshot_data_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit = DesignerAudit(candidate_profile_id=profile.id, scenario=request.scenario, screenshot_data_url=image)
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit_response(audit)


@router.post("/upload", response_model=DesignerAuditResponse, status_code=201)
async def upload_audit(
    file: UploadFile,
    scenario: str = Form(..., min_length=10, max_length=4000),
    profile: CandidateProfile = Depends(get_candidate_profile),
    db: Session = Depends(get_db),
):
    try:
        image = screenshot_data_url(await file.read(MAX_SCREENSHOT_BYTES + 1), file.content_type or "")
        request = DesignerAuditCreate(scenario=scenario, screenshot_data_url=image)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Укажите сценарий длиной от 10 до 4000 символов") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return create_audit(request, profile, db)


@router.post("/portfolio", response_model=PortfolioMetricsResponse)
async def portfolio_metrics(
    file: UploadFile,
    profile: CandidateProfile = Depends(get_candidate_profile),
    db: Session = Depends(get_db),
):
    try:
        evidence = extract_portfolio_metrics(await file.read(MAX_PORTFOLIO_BYTES + 1))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    profile.portfolio_evidence = evidence.model_dump()
    db.commit()
    return evidence


@router.post("/task", response_model=DesignerAuditResponse, status_code=201)
async def create_reference_task(profile: CandidateProfile = Depends(get_candidate_profile), db: Session = Depends(get_db)):
    audit = db.query(DesignerAudit).filter(
        DesignerAudit.candidate_profile_id == profile.id, DesignerAudit.task_key == REFERENCE_TASK_KEY,
    ).first()
    if audit is None:
        scenario = REFERENCE_SCENARIO
        image = None
        defects: list = []
        generated = await generate_mockup()
        if generated is not None:
            try:
                image = mockup_data_url(await render_html_to_png(generated.html))
                scenario = generated.scenario
                defects = generated.defects
            except Exception:
                image = None
        if image is None:
            image = reference_task_image()
        audit = DesignerAudit(
            candidate_profile_id=profile.id, scenario=scenario,
            screenshot_data_url=image, task_key=REFERENCE_TASK_KEY, reference_defects=defects,
        )
        db.add(audit)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            audit = db.query(DesignerAudit).filter(
                DesignerAudit.candidate_profile_id == profile.id, DesignerAudit.task_key == REFERENCE_TASK_KEY,
            ).one()
        db.refresh(audit)
    return audit_response(audit)


@router.get("/{audit_id}", response_model=DesignerAuditResponse)
def get_audit(audit_id: int, profile: CandidateProfile = Depends(get_candidate_profile), db: Session = Depends(get_db)):
    return audit_response(owned_audit(audit_id, profile, db))


@router.post("/{audit_id}/submit", response_model=DesignerAuditResponse)
async def submit_audit(
    audit_id: int,
    request: DesignerAuditSubmit,
    profile: CandidateProfile = Depends(get_candidate_profile),
    db: Session = Depends(get_db),
):
    audit = owned_audit(audit_id, profile, db)
    retryable_reference = (
        audit.status == "submitted"
        and audit.task_key == REFERENCE_TASK_KEY
        and isinstance(audit.evaluation, dict)
        and audit.evaluation.get("testing_score") is None
    )
    if audit.status != "pending" and not retryable_reference:
        raise HTTPException(status_code=409, detail="Этот аудит уже отправлен")
    if retryable_reference:
        if request.model_dump()["violations"] != audit.violations:
            raise HTTPException(status_code=409, detail="Повторная проверка должна использовать сохранённые ответы")
        request = DesignerAuditSubmit.model_validate({"violations": audit.violations})
    evaluation = await evaluate_audit(audit.scenario, request, audit.task_key, audit.screenshot_data_url, audit.reference_defects)
    result = db.execute(update(DesignerAudit).where(
        DesignerAudit.id == audit.id,
        DesignerAudit.candidate_profile_id == profile.id,
        DesignerAudit.status == audit.status,
        DesignerAudit.submitted_at == audit.submitted_at,
        or_(
            DesignerAudit.status == "pending",
            and_(
                DesignerAudit.status == "submitted",
                DesignerAudit.task_key == REFERENCE_TASK_KEY,
                DesignerAudit.evaluation["testing_score"].as_float().is_(None),
            ),
        ),
    ).values(
        status="submitted", violations=request.model_dump()["violations"],
        evaluation=evaluation.model_dump(), submitted_at=datetime.now(timezone.utc),
    ))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Этот аудит уже отправлен")
    db.commit()
    db.refresh(audit)
    return audit_response(audit)
