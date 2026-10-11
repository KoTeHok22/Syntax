from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db import Base, SessionLocal, engine
from backend.models import CandidateProfile, User
from scripts import backfill_grade_confirmation, generate_synthetic, seed_demo

DEMO_CANDIDATE_PATTERN = "demo.candidate.%"


def _demo_profiles(db: Session) -> list[CandidateProfile]:
    return (
        db.query(CandidateProfile)
        .join(User, User.id == CandidateProfile.user_id)
        .filter(User.email.like(DEMO_CANDIDATE_PATTERN))
        .order_by(CandidateProfile.id)
        .all()
    )


def _run_seed() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_demo.main()


def _snapshot(db: Session) -> dict:
    rows = _demo_profiles(db)
    return {
        "count": len(rows),
        "profiles": {
            profile.id: (
                profile.city,
                profile.work_format,
                profile.grade,
                profile.grade_confirmed_at,
            )
            for profile in rows
        },
    }


def test_seed_fills_city_and_work_format_for_every_demo_candidate():
    _run_seed()
    db = SessionLocal()
    try:
        profiles = _demo_profiles(db)
        assert profiles, "seed should create demo candidates"
        empty_city = [p.id for p in profiles if not (p.city or "").strip()]
        empty_format = [p.id for p in profiles if not (p.work_format or "").strip()]
        assert empty_city == [], f"profiles without city: {empty_city}"
        assert empty_format == [], f"profiles without work_format: {empty_format}"
        assert {p.work_format for p in profiles} <= set(generate_synthetic.WORK_FORMATS)
        assert {p.city for p in profiles} <= set(generate_synthetic.CITIES)
    finally:
        db.close()


def test_seed_confirms_grade_for_candidates_with_confirmed_session():
    _run_seed()
    db = SessionLocal()
    try:
        confirmed_profiles = backfill_grade_confirmation.demo_profiles(db)
        candidates_with_session = [
            profile
            for profile in confirmed_profiles
            if backfill_grade_confirmation.best_session(db, profile.id) is not None
        ]
        assert candidates_with_session, "seed should produce qualifying sessions"
        missing = [profile.id for profile in candidates_with_session if profile.grade_confirmed_at is None]
        assert missing == [], f"qualifying profiles without grade_confirmed_at: {missing}"
    finally:
        db.close()


def test_reconcile_is_idempotent_across_repeated_runs():
    _run_seed()
    db = SessionLocal()
    try:
        before = _snapshot(db)
        seed_demo.reconcile_demo_data(db)
        db.commit()
        after = _snapshot(db)
        second = seed_demo.reconcile_demo_data(db)
        db.commit()
        assert before == after, "a second reconcile pass must not change demo data"
        assert second == (0, 0), "a settled stand requires no further backfill"
    finally:
        db.close()


def test_reconcile_fills_legacy_rows_missing_new_fields():
    _run_seed()
    db = SessionLocal()
    try:
        legacy = _demo_profiles(db)[0]
        legacy.city = ""
        legacy.work_format = ""
        legacy.grade_confirmed_at = None
        db.commit()

        fields, _ = seed_demo.reconcile_demo_data(db)
        db.refresh(legacy)
        assert (legacy.city or "").strip() != ""
        assert (legacy.work_format or "").strip() != ""
        assert fields >= 2
        healed_city = legacy.city
        healed_format = legacy.work_format

        legacy.city = ""
        legacy.work_format = ""
        db.commit()
        seed_demo.reconcile_demo_data(db)
        db.refresh(legacy)
        assert legacy.city == healed_city
        assert legacy.work_format == healed_format
    finally:
        db.close()


def test_demo_password_accounts_are_not_collapsed():
    _run_seed()
    db = SessionLocal()
    try:
        total = (
            db.query(func.count(CandidateProfile.id))
            .join(User, User.id == CandidateProfile.user_id)
            .filter(User.email.like(DEMO_CANDIDATE_PATTERN))
            .scalar()
        )
        assert total >= 100
    finally:
        db.close()
