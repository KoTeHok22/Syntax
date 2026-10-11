from sqlalchemy.orm import Session

from backend.core.scoring import (
    ScoreComponents,
    compute_score,
    is_verified,
    profile_completeness,
    proof_tier,
)
from backend.core.stack_proof import stack_proof_map, verified_domains
from backend.models import CandidateProfile, Concept, PvnAchievement, Task, TestAnswer, TestSession


def build_score_components(db: Session, candidate: CandidateProfile) -> ScoreComponents:
    achievements = (
        db.query(PvnAchievement)
        .filter(PvnAchievement.candidate_profile_id == candidate.id)
        .all()
    )
    latest_session = (
        db.query(TestSession)
        .filter(
            TestSession.candidate_profile_id == candidate.id,
            TestSession.status == "completed",
        )
        .order_by(TestSession.completed_at.desc())
        .first()
    )
    return ScoreComponents(
        test_score=latest_session.result_score if latest_session else None,
        pvn_achievements=min(100.0, sum(a.score for a in achievements)) if achievements else None,
        profile_completeness=profile_completeness(candidate),
    )


def candidate_score(db: Session, candidate: CandidateProfile) -> tuple[float, dict]:
    return compute_score(build_score_components(db, candidate))


def candidate_proof_tier(db: Session, candidate: CandidateProfile) -> str:
    return proof_tier(build_score_components(db, candidate))


def candidate_is_verified(db: Session, candidate: CandidateProfile) -> bool:
    return is_verified(build_score_components(db, candidate))


def build_stack_proof(db: Session, candidate: CandidateProfile) -> list[dict]:
    latest_session = (
        db.query(TestSession)
        .filter(
            TestSession.candidate_profile_id == candidate.id,
            TestSession.status == "completed",
        )
        .order_by(TestSession.completed_at.desc())
        .first()
    )
    if latest_session is None:
        return stack_proof_map(candidate.stack or [], candidate.specialization, set())
    rows = (
        db.query(TestAnswer.is_correct, Concept.domain)
        .join(Task, TestAnswer.task_id == Task.id)
        .join(Concept, Task.concept_id == Concept.id)
        .filter(TestAnswer.session_id == latest_session.id)
        .all()
    )
    domains_verified = verified_domains(
        [{"is_correct": is_correct, "domain": domain} for is_correct, domain in rows]
    )
    return stack_proof_map(candidate.stack or [], candidate.specialization, domains_verified)

