from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.db import Base
from backend.models import CandidateProfile, TestSession, User
from scripts import backfill_grade_confirmation as backfill_module


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with sessions() as session:
        yield session
    engine.dispose()


def make_candidate(db, index, email=None):
    user = User(
        email=email or f"demo.candidate.{index:03d}@example.com",
        password_hash="test",
        role="candidate",
        is_email_confirmed=True,
    )
    db.add(user)
    db.flush()
    profile = CandidateProfile(user_id=user.id, full_name=f"Кандидат {index}", specialization="backend", grade="middle")
    db.add(profile)
    db.flush()
    return profile


def make_session(db, profile, verdict, grade="middle", status="completed", completed_at=None):
    session = TestSession(
        candidate_profile_id=profile.id,
        grade=grade,
        task_count=5,
        correct_count=4,
        result_score=80,
        verdict=verdict,
        status=status,
        completed_at=completed_at or (datetime.now(timezone.utc) - timedelta(days=15)),
    )
    db.add(session)
    db.flush()
    return session


def test_backfill_confirms_confirmed_and_suggest_higher(db):
    confirmed = make_candidate(db, 1)
    higher = make_candidate(db, 2)
    make_session(db, confirmed, "confirmed")
    make_session(db, higher, "suggest_higher", grade="senior")
    db.commit()

    updated = backfill_module.backfill(db)

    assert updated == 2
    assert confirmed.grade_confirmed_at is not None
    assert higher.grade_confirmed_at is not None


def test_backfill_anchors_confirmation_to_session_completed_at(db):
    profile = make_candidate(db, 1)
    completed_at = datetime.now(timezone.utc) - timedelta(days=40)
    make_session(db, profile, "confirmed", completed_at=completed_at)
    db.commit()

    backfill_module.backfill(db)
    db.refresh(profile)

    assert profile.grade_confirmed_at is not None
    stored = profile.grade_confirmed_at
    if stored.tzinfo is None:
        stored = stored.replace(tzinfo=timezone.utc)
    assert abs((stored - completed_at).total_seconds()) < 1


def test_backfill_ignores_suggest_lower(db):
    profile = make_candidate(db, 1)
    make_session(db, profile, "suggest_lower")
    db.commit()

    updated = backfill_module.backfill(db)

    assert updated == 0
    assert profile.grade_confirmed_at is None


def test_backfill_ignores_pending_sessions(db):
    profile = make_candidate(db, 1)
    make_session(db, profile, "confirmed", status="pending")
    db.commit()

    updated = backfill_module.backfill(db)

    assert updated == 0
    assert profile.grade_confirmed_at is None


def test_backfill_ignores_non_demo_candidates(db):
    profile = make_candidate(db, 900, email="real.candidate@corp.example.com")
    make_session(db, profile, "confirmed")
    db.commit()

    updated = backfill_module.backfill(db)

    assert updated == 0
    assert profile.grade_confirmed_at is None


def test_backfill_is_idempotent(db):
    profile = make_candidate(db, 1)
    make_session(db, profile, "confirmed")
    db.commit()

    first = backfill_module.backfill(db)
    first_stamp = profile.grade_confirmed_at
    second = backfill_module.backfill(db)

    assert first == 1
    assert second == 0
    assert profile.grade_confirmed_at == first_stamp


def test_backfill_upgrades_grade_to_confirmed_session_grade(db):
    profile = make_candidate(db, 1)
    profile.grade = "middle"
    make_session(db, profile, "suggest_higher", grade="senior")
    db.commit()

    backfill_module.backfill(db)
    db.refresh(profile)

    assert profile.grade == "senior"


def test_best_session_prefers_latest_qualifying(db):
    profile = make_candidate(db, 1)
    make_session(db, profile, "suggest_lower")
    latest = make_session(db, profile, "confirmed", completed_at=datetime.now(timezone.utc) - timedelta(days=2))
    db.commit()

    chosen = backfill_module.best_session(db, profile.id)

    assert chosen is not None
    assert chosen.id == latest.id
