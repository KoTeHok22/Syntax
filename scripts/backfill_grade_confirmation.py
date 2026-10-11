from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.api.routes.test_sessions import apply_test_grade
from backend.core.testing import VERDICT_CONFIRMED, VERDICT_SUGGEST_HIGHER
from backend.db import SessionLocal
from backend.models import CandidateProfile, TestSession, User

DEMO_CANDIDATE_PATTERN = "demo.candidate.%"
QUALIFYING_VERDICTS = (VERDICT_CONFIRMED, VERDICT_SUGGEST_HIGHER)


def best_session(db: Session, profile_id: int) -> TestSession | None:
    return (
        db.query(TestSession)
        .filter(
            TestSession.candidate_profile_id == profile_id,
            TestSession.status == "completed",
            TestSession.verdict.in_(QUALIFYING_VERDICTS),
        )
        .order_by(TestSession.completed_at.desc().nullslast(), TestSession.id.desc())
        .first()
    )


def demo_profiles(db: Session) -> list[CandidateProfile]:
    return (
        db.query(CandidateProfile)
        .join(User, User.id == CandidateProfile.user_id)
        .filter(User.email.like(DEMO_CANDIDATE_PATTERN))
        .order_by(CandidateProfile.id)
        .all()
    )


def backfill(db: Session) -> int:
    updated = 0
    now = datetime.now(timezone.utc)
    for profile in demo_profiles(db):
        if profile.grade_confirmed_at is not None:
            continue
        session = best_session(db, profile.id)
        if session is None:
            continue
        apply_test_grade(db, profile, session)
        profile.grade_confirmed_at = session.completed_at or now
        updated += 1
    db.commit()
    return updated


def main() -> None:
    db = SessionLocal()
    try:
        updated = backfill(db)
        total = (
            db.query(func.count(CandidateProfile.id))
            .join(User, User.id == CandidateProfile.user_id)
            .filter(User.email.like(DEMO_CANDIDATE_PATTERN))
            .scalar()
        )
        print(f"Обновлено профилей: {updated} из {total}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
