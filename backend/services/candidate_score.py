from sqlalchemy.orm import Session

from backend.core.scoring import ScoreComponents, compute_score, profile_completeness
from backend.models import CandidateProfile, PvnAchievement, TestSession


def candidate_score(db: Session, candidate: CandidateProfile) -> tuple[float, dict]:
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
    components = ScoreComponents(
        test_score=latest_session.result_score if latest_session else None,
        pvn_achievements=min(100.0, sum(a.score for a in achievements)) if achievements else None,
        profile_completeness=profile_completeness(candidate),
    )
    return compute_score(components)
