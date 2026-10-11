import os
import re

from sqlalchemy import or_

from backend.db import SessionLocal
from backend.models import (
    Application,
    CandidateProfile,
    EmployerProfile,
    PvnAchievement,
    Invitation,
    RegularTask,
    RegularTaskSubmission,
    Task,
    TestSession,
    User,
    Vacancy,
)


def _delete_candidate(db, candidate_id: int) -> None:
    db.query(PvnAchievement).filter(PvnAchievement.candidate_profile_id == candidate_id).delete(synchronize_session=False)
    db.query(Application).filter(Application.candidate_profile_id == candidate_id).delete(synchronize_session=False)
    db.query(Invitation).filter(Invitation.candidate_profile_id == candidate_id).delete(synchronize_session=False)
    db.query(RegularTaskSubmission).filter(RegularTaskSubmission.candidate_profile_id == candidate_id).delete(synchronize_session=False)
    session_ids = db.query(TestSession.id).filter(TestSession.candidate_profile_id == candidate_id)
    db.query(Task).filter(or_(Task.candidate_profile_id == candidate_id, Task.session_id.in_(session_ids))).delete(synchronize_session=False)
    db.query(TestSession).filter(TestSession.candidate_profile_id == candidate_id).delete(synchronize_session=False)


def _delete_employer(db, employer_id: int) -> None:
    vacancy_ids = [row.id for row in db.query(Vacancy.id).filter(Vacancy.employer_profile_id == employer_id).all()]
    if vacancy_ids:
        db.query(Application).filter(Application.vacancy_id.in_(vacancy_ids)).delete(synchronize_session=False)
    db.query(Vacancy).filter(Vacancy.employer_profile_id == employer_id).delete(synchronize_session=False)
    db.query(Invitation).filter(Invitation.employer_profile_id == employer_id).delete(synchronize_session=False)
    task_ids = [row.id for row in db.query(RegularTask.id).filter(RegularTask.employer_profile_id == employer_id).all()]
    if task_ids:
        db.query(RegularTaskSubmission).filter(RegularTaskSubmission.regular_task_id.in_(task_ids)).delete(synchronize_session=False)
    db.query(RegularTask).filter(RegularTask.employer_profile_id == employer_id).delete(synchronize_session=False)


def cleanup() -> int:
    run_id = os.environ.get("E2E_RUN_ID", "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
        raise ValueError("E2E_RUN_ID must be explicit and contain only letters, digits, hyphens, or underscores")
    escaped_run_id = run_id.replace("_", r"\_")
    db = SessionLocal()
    removed = 0
    try:
        test_users = db.query(User).filter(User.email.like(f"e2e.%.{escaped_run_id}@syntax.dev", escape="\\")).all()
        for user in test_users:
            if not user.email.startswith("e2e.") or not user.email.endswith(f".{run_id}@syntax.dev"):
                continue
            candidate = db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).first()
            if candidate is not None:
                _delete_candidate(db, candidate.id)
                db.delete(candidate)
                removed += 1
            employer = db.query(EmployerProfile).filter(EmployerProfile.user_id == user.id).first()
            if employer is not None:
                _delete_employer(db, employer.id)
                db.delete(employer)
                removed += 1
            db.delete(user)
            removed += 1
            db.flush()
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return removed


if __name__ == "__main__":
    count = cleanup()
    print(f"Удалено e2e-сущностей: {count}")
