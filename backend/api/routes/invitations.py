from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.deps import (
    get_candidate_profile,
    get_db,
    get_employer_profile,
    require_employer,
)
from backend.core.matching import (
    INVITATION_ACCEPTED,
    INVITATION_EDITABLE_STATUSES,
    INVITATION_REJECTED,
    INVITATION_SENT,
    INVITATION_VIEWED,
    INVITATION_WITHDRAWN,
    invitation_transition_allowed,
)
from backend.models import CandidateProfile, EmployerProfile, Invitation, User
from backend.schemas.matching import InvitationCreate, InvitationResponse, InvitationUpdate

router = APIRouter()


def to_response(invitation: Invitation, reveal_contacts: bool) -> InvitationResponse:
    candidate = invitation.candidate_profile
    employer = invitation.employer_profile
    company_name = employer.company_name if employer is not None and employer.company_name else invitation.company_name
    return InvitationResponse(
        id=invitation.id,
        candidate_profile_id=invitation.candidate_profile_id,
        candidate_grade=candidate.grade,
        candidate_specialization=candidate.specialization,
        candidate_stack=list(candidate.stack or []),
        message=invitation.message,
        salary_from=invitation.salary_from,
        salary_to=invitation.salary_to,
        company_name=company_name,
        contact_method=invitation.contact_method if reveal_contacts else None,
        status=invitation.status,
        candidate_contacts=candidate.contacts if reveal_contacts else None,
        created_at=invitation.created_at.isoformat(),
    )


@router.post("/invitations", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
def create_invitation(
    request: InvitationCreate,
    db: Session = Depends(get_db),
    employer_profile: EmployerProfile = Depends(get_employer_profile),
):
    candidate = db.get(CandidateProfile, request.candidate_profile_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Кандидат не найден")
    invitation = Invitation(
        employer_profile_id=employer_profile.id,
        candidate_profile_id=candidate.id,
        message=request.message,
        salary_from=request.salary_from,
        salary_to=request.salary_to,
        company_name=request.company_name,
        contact_method=request.contact_method,
        status=INVITATION_SENT,
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return to_response(invitation, reveal_contacts=False)


def get_owned_invitation(db: Session, invitation_id: int, employer_profile: EmployerProfile) -> Invitation:
    invitation = db.get(Invitation, invitation_id)
    if invitation is None or invitation.employer_profile_id != employer_profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Приглашение не найдено")
    return invitation


@router.patch("/invitations/{invitation_id}", response_model=InvitationResponse)
def update_invitation(
    invitation_id: int,
    request: InvitationUpdate,
    db: Session = Depends(get_db),
    employer_profile: EmployerProfile = Depends(get_employer_profile),
):
    invitation = get_owned_invitation(db, invitation_id, employer_profile)
    if invitation.status not in INVITATION_EDITABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Редактировать можно только приглашение, которое кандидат ещё не просмотрел",
        )
    invitation.message = request.message
    invitation.salary_from = request.salary_from
    invitation.salary_to = request.salary_to
    invitation.company_name = request.company_name
    invitation.contact_method = request.contact_method
    db.commit()
    db.refresh(invitation)
    return to_response(invitation, reveal_contacts=False)


@router.post("/invitations/{invitation_id}/withdraw", response_model=InvitationResponse)
def withdraw_invitation(
    invitation_id: int,
    db: Session = Depends(get_db),
    employer_profile: EmployerProfile = Depends(get_employer_profile),
):
    invitation = get_owned_invitation(db, invitation_id, employer_profile)
    if not invitation_transition_allowed(invitation.status, INVITATION_WITHDRAWN):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Отозвать приглашение в статусе {invitation.status} нельзя",
        )
    invitation.status = INVITATION_WITHDRAWN
    db.commit()
    db.refresh(invitation)
    return to_response(invitation, reveal_contacts=False)


@router.get("/invitations/incoming", response_model=list[InvitationResponse])
def list_incoming_invitations(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    candidate_profile: CandidateProfile = Depends(get_candidate_profile),
):
    invitations = (
        db.query(Invitation)
        .filter(Invitation.candidate_profile_id == candidate_profile.id)
        .order_by(Invitation.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [to_response(i, reveal_contacts=True) for i in invitations]


@router.get("/invitations/sent", response_model=list[InvitationResponse])
def list_sent_invitations(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    employer_profile: EmployerProfile = Depends(get_employer_profile),
):
    invitations = (
        db.query(Invitation)
        .filter(Invitation.employer_profile_id == employer_profile.id)
        .order_by(Invitation.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [to_response(i, reveal_contacts=i.status == INVITATION_ACCEPTED) for i in invitations]


@router.post("/invitations/{invitation_id}/view", response_model=InvitationResponse)
def mark_viewed(
    invitation_id: int,
    db: Session = Depends(get_db),
    candidate_profile: CandidateProfile = Depends(get_candidate_profile),
):
    invitation = db.get(Invitation, invitation_id)
    if invitation is None or invitation.candidate_profile_id != candidate_profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Приглашение не найдено")
    if invitation_transition_allowed(invitation.status, INVITATION_VIEWED):
        invitation.status = INVITATION_VIEWED
        db.commit()
        db.refresh(invitation)
    return to_response(invitation, reveal_contacts=True)


@router.post("/invitations/{invitation_id}/accept", response_model=InvitationResponse)
def accept_invitation(
    invitation_id: int,
    db: Session = Depends(get_db),
    candidate_profile: CandidateProfile = Depends(get_candidate_profile),
):
    invitation = db.get(Invitation, invitation_id)
    if invitation is None or invitation.candidate_profile_id != candidate_profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Приглашение не найдено")
    if not invitation_transition_allowed(invitation.status, INVITATION_ACCEPTED):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Переход из статуса {invitation.status} невозможен")
    invitation.status = INVITATION_ACCEPTED
    db.commit()
    db.refresh(invitation)
    return to_response(invitation, reveal_contacts=True)


@router.post("/invitations/{invitation_id}/reject", response_model=InvitationResponse)
def reject_invitation(
    invitation_id: int,
    db: Session = Depends(get_db),
    candidate_profile: CandidateProfile = Depends(get_candidate_profile),
):
    invitation = db.get(Invitation, invitation_id)
    if invitation is None or invitation.candidate_profile_id != candidate_profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Приглашение не найдено")
    if not invitation_transition_allowed(invitation.status, INVITATION_REJECTED):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Переход из статуса {invitation.status} невозможен")
    invitation.status = INVITATION_REJECTED
    db.commit()
    db.refresh(invitation)
    return to_response(invitation, reveal_contacts=False)
