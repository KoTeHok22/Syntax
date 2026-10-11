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


def domains_verified_for_session(db: Session, session_id: int) -> set[str]:
    rows = (
        db.query(TestAnswer.is_correct, Concept.domain)
        .join(Task, TestAnswer.task_id == Task.id)
        .join(Concept, Task.concept_id == Concept.id)
        .filter(TestAnswer.session_id == session_id)
        .all()
    )
    return verified_domains(
        [{"is_correct": is_correct, "domain": domain} for is_correct, domain in rows]
    )


def latest_completed_session_ids(db: Session, candidate_ids: list[int]) -> dict[int, int]:
    if not candidate_ids:
        return {}
    rows = (
        db.query(TestSession.candidate_profile_id, TestSession.id)
        .filter(
            TestSession.candidate_profile_id.in_(candidate_ids),
            TestSession.status == "completed",
        )
        .order_by(
            TestSession.candidate_profile_id.asc(),
            TestSession.completed_at.desc(),
            TestSession.id.desc(),
        )
        .all()
    )
    latest: dict[int, int] = {}
    for candidate_id, session_id in rows:
        latest.setdefault(candidate_id, session_id)
    return latest


def verified_domains_bulk(db: Session, session_ids: list[int]) -> dict[int, set[str]]:
    if not session_ids:
        return {}
    rows = (
        db.query(TestAnswer.session_id, TestAnswer.is_correct, Concept.domain)
        .join(Task, TestAnswer.task_id == Task.id)
        .join(Concept, Task.concept_id == Concept.id)
        .filter(TestAnswer.session_id.in_(session_ids))
        .all()
    )
    grouped: dict[int, list[dict]] = {}
    for session_id, is_correct, domain in rows:
        grouped.setdefault(session_id, []).append(
            {"is_correct": is_correct, "domain": domain}
        )
    return {session_id: verified_domains(answers) for session_id, answers in grouped.items()}


def build_stack_proof_bulk(
    db: Session, candidates: list[CandidateProfile]
) -> dict[int, list[dict]]:
    if not candidates:
        return {}
    candidate_ids = [candidate.id for candidate in candidates]
    latest_sessions = latest_completed_session_ids(db, candidate_ids)
    domains_by_session = verified_domains_bulk(db, list(latest_sessions.values()))
    result: dict[int, list[dict]] = {}
    for candidate in candidates:
        session_id = latest_sessions.get(candidate.id)
        domains = domains_by_session.get(session_id, set()) if session_id is not None else set()
        result[candidate.id] = stack_proof_map(
            candidate.stack or [], candidate.specialization, domains
        )
    return result


def build_stack_proof(db: Session, candidate: CandidateProfile) -> list[dict]:
    latest_session = (
        db.query(TestSession)
        .filter(
            TestSession.candidate_profile_id == candidate.id,
            TestSession.status == "completed",
        )
        .order_by(TestSession.completed_at.desc(), TestSession.id.desc())
        .first()
    )
    if latest_session is None:
        return stack_proof_map(candidate.stack or [], candidate.specialization, set())
    return stack_proof_map(
        candidate.stack or [],
        candidate.specialization,
        domains_verified_for_session(db, latest_session.id),
    )

