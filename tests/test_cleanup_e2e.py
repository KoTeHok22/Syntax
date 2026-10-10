from datetime import date

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from backend.db import Base
from backend.models import (
    Application,
    CandidateProfile,
    CompanyOffice,
    Concept,
    DesignerAudit,
    EmployerProfile,
    PvnAchievement,
    Invitation,
    RegularTask,
    RegularTaskSubmission,
    Task,
    TestSession as CandidateTestSession,
    User,
    Vacancy,
)
from scripts import cleanup_e2e


@pytest.fixture
def cleanup_db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(cleanup_e2e, "SessionLocal", sessions)
    with sessions() as db:
        yield db
    engine.dispose()


def seed_run(db, run_id, prefix="e2e"):
    candidate_user = User(email=f"{prefix}.candidate.{run_id}@syntax.dev", password_hash="test", role="candidate", email_confirmation_token="unconfirmed")
    employer_user = User(email=f"{prefix}.employer.{run_id}@syntax.dev", password_hash="test", role="employer")
    db.add_all([candidate_user, employer_user])
    db.flush()
    candidate = CandidateProfile(user_id=candidate_user.id)
    employer = EmployerProfile(user_id=employer_user.id)
    db.add_all([candidate, employer])
    db.flush()
    vacancy = Vacancy(employer_profile_id=employer.id, title=f"E2E {run_id}", salary_from=1, salary_to=2)
    regular_task = RegularTask(employer_profile_id=employer.id, statement=f"E2E {run_id}", reference_answer=0)
    concept = Concept(name=f"concept-{prefix}-{run_id}", domain="backend", grade="junior")
    test_session = CandidateTestSession(candidate_profile_id=candidate.id, grade="junior")
    db.add_all([vacancy, regular_task, concept, test_session])
    db.flush()
    db.add_all([
        CompanyOffice(employer_profile_id=employer.id, title="Office"),
        DesignerAudit(candidate_profile_id=candidate.id, scenario="Audit", screenshot_data_url="data:image/png;base64,test"),
        PvnAchievement(candidate_profile_id=candidate.id, achievement_type="contest", achieved_at=date(2026, 1, 1)),
        Application(candidate_profile_id=candidate.id, vacancy_id=vacancy.id),
        Invitation(candidate_profile_id=candidate.id, employer_profile_id=employer.id, message="Invitation", salary_from=1, salary_to=2, company_name="Company", contact_method="email"),
        RegularTaskSubmission(candidate_profile_id=candidate.id, regular_task_id=regular_task.id, is_correct=True),
        Task(candidate_profile_id=candidate.id, session_id=test_session.id, concept_id=concept.id, grade="junior", statement="Task", task_format="multiple_choice", reference_answer="0"),
        Task(session_id=test_session.id, concept_id=concept.id, grade="junior", statement="Session task", task_format="multiple_choice", reference_answer="0"),
    ])
    db.commit()
    return candidate, employer, vacancy, regular_task


def snapshot(db):
    return {
        table.name: list(db.execute(select(table).order_by(table.c.id)).mappings())
        for table in Base.metadata.sorted_tables
    }


def test_cleanup_only_target_run_and_related_data(cleanup_db, monkeypatch):
    db = cleanup_db
    target, target_employer, target_vacancy, target_task = seed_run(db, "123")
    other, other_employer, other_vacancy, other_task = seed_run(db, "1234")
    demo, demo_employer, demo_vacancy, demo_task = seed_run(db, "123", prefix="demo")
    db.add_all([
        Application(candidate_profile_id=target.id, vacancy_id=demo_vacancy.id),
        Application(candidate_profile_id=demo.id, vacancy_id=target_vacancy.id),
        Invitation(candidate_profile_id=demo.id, employer_profile_id=target_employer.id, message="Target invitation", salary_from=1, salary_to=2, company_name="Company", contact_method="email"),
        Invitation(candidate_profile_id=target.id, employer_profile_id=demo_employer.id, message="Demo invitation", salary_from=1, salary_to=2, company_name="Company", contact_method="email"),
        RegularTaskSubmission(candidate_profile_id=target.id, regular_task_id=demo_task.id, is_correct=True),
        RegularTaskSubmission(candidate_profile_id=demo.id, regular_task_id=target_task.id, is_correct=True),
        User(email="ordinary.123@syntax.dev", password_hash="test", role="candidate"),
        User(email="e2e.candidate.123@example.com", password_hash="test", role="candidate"),
        User(email="e2e.candidate.123.extra@syntax.dev", password_hash="test", role="candidate"),
    ])
    db.commit()
    before = snapshot(db)
    monkeypatch.setenv("E2E_RUN_ID", "123")
    delete_statements = []

    @event.listens_for(db.get_bind(), "before_cursor_execute")
    def capture_deletes(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("DELETE"):
            delete_statements.append(statement)

    assert cleanup_e2e.cleanup() == 4
    assert delete_statements
    assert all(" WHERE " in statement for statement in delete_statements)
    assert all(" LIKE " not in statement for statement in delete_statements)
    after = snapshot(db)
    target_ids = {
        "users": {target.user_id, target_employer.user_id},
        "candidate_profiles": {target.id},
        "employer_profiles": {target_employer.id},
        "vacancies": {target_vacancy.id},
        "regular_tasks": {target_task.id},
    }
    session_ids = {row["id"] for row in before["test_sessions"] if row["candidate_profile_id"] == target.id}
    for table, rows in before.items():
        expected = [
            row for row in rows
            if row["id"] not in target_ids.get(table, set())
            and not ("candidate_profile_id" in row and row["candidate_profile_id"] == target.id)
            and not ("employer_profile_id" in row and row["employer_profile_id"] == target_employer.id)
            and not ("vacancy_id" in row and row["vacancy_id"] == target_vacancy.id)
            and not ("regular_task_id" in row and row["regular_task_id"] == target_task.id)
            and not ("session_id" in row and row["session_id"] in session_ids)
        ]
        assert after[table] == expected, table
    assert cleanup_e2e.cleanup() == 0


@pytest.mark.parametrize("run_id", ["run_1", "run-1", "AbC123"])
def test_cleanup_exact_run_suffix_and_e2e_prefix(cleanup_db, monkeypatch, run_id):
    db = cleanup_db
    seed_run(db, run_id, prefix="e2e.newcore")
    seed_run(db, run_id.replace("_", "x") + "-other")
    seed_run(db, run_id, prefix="not-e2e")
    seed_run(db, run_id.upper(), prefix="E2E")
    if run_id != run_id.upper():
        seed_run(db, run_id.upper())
    if "_" in run_id:
        seed_run(db, run_id.replace("_", "x"))
    before = snapshot(db)
    monkeypatch.setenv("E2E_RUN_ID", run_id)

    assert cleanup_e2e.cleanup() == 4
    after = snapshot(db)
    assert len(after["users"]) == len(before["users"]) - 2
    assert all(not row["email"].startswith("e2e.newcore.") for row in after["users"])
    assert len(after["designer_audits"]) == len(before["designer_audits"]) - 1


@pytest.mark.parametrize("run_id", [None, "", "   ", "%", "run%1", "run\\1", "run.1", "run@1", "run 1"])
def test_cleanup_refuses_missing_or_unsafe_run_before_session(monkeypatch, run_id):
    if run_id is None:
        monkeypatch.delenv("E2E_RUN_ID", raising=False)
    else:
        monkeypatch.setenv("E2E_RUN_ID", run_id)

    def refuse_session():
        pytest.fail("Cleanup must refuse unsafe run IDs before opening a database session")

    monkeypatch.setattr(cleanup_e2e, "SessionLocal", refuse_session)
    with pytest.raises(ValueError, match="E2E_RUN_ID"):
        cleanup_e2e.cleanup()


def test_cleanup_unknown_run_leaves_all_data_unchanged(cleanup_db, monkeypatch):
    seed_run(cleanup_db, "known")
    seed_run(cleanup_db, "missing", prefix="demo")
    before = snapshot(cleanup_db)
    monkeypatch.setenv("E2E_RUN_ID", "missing")

    assert cleanup_e2e.cleanup() == 0
    assert snapshot(cleanup_db) == before


def test_cleanup_failure_rolls_back_all_deletes(cleanup_db, monkeypatch):
    seed_run(cleanup_db, "rollback")
    before = snapshot(cleanup_db)
    monkeypatch.setenv("E2E_RUN_ID", "rollback")

    def fail_employer_delete(db, employer_id):
        raise RuntimeError("Cleanup failed")

    monkeypatch.setattr(cleanup_e2e, "_delete_employer", fail_employer_delete)
    with pytest.raises(RuntimeError, match="Cleanup failed"):
        cleanup_e2e.cleanup()
    assert snapshot(cleanup_db) == before
