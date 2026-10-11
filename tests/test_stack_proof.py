from backend.core.stack_proof import (
    PROOF_CLAIMED,
    PROOF_VERIFIED,
    keyword_domain_for,
    stack_proof_map,
    verified_domains,
)
from backend.db import SessionLocal
from backend.models import CandidateProfile, Concept, Task, TestAnswer, TestSession, User


def _answer(is_correct, domain):
    return {"is_correct": is_correct, "domain": domain}


def test_domain_verified_on_correct_answer():
    domains = verified_domains(
        [
            _answer(True, "databases"),
            _answer(False, "frontend"),
            _answer(True, "frontend"),
        ]
    )
    assert domains == {"databases", "frontend"}


def test_incorrect_answers_do_not_verify_domain():
    assert verified_domains([_answer(False, "devops")]) == set()


def test_empty_answers_yield_no_domains():
    assert verified_domains([]) == set()
    assert verified_domains(None) == set()


def test_stack_without_verified_domain_is_claimed():
    result = stack_proof_map(["react"], "frontend", {"databases"})
    assert result == [{"stack": "react", "domain": None, "proof": PROOF_CLAIMED}]


def test_keyword_mapping_postgresql_kubernetes_react():
    assert keyword_domain_for("postgresql") == "databases"
    assert keyword_domain_for("kubernetes") == "devops"
    assert keyword_domain_for("react") == "frontend"
    assert keyword_domain_for("fastapi") == "backend"


def test_stack_map_marks_verified_when_domain_confirmed():
    result = stack_proof_map(
        ["postgresql", "kubernetes", "react"],
        "backend",
        {"databases", "devops", "frontend"},
    )
    assert result == [
        {"stack": "postgresql", "domain": "databases", "proof": PROOF_VERIFIED},
        {"stack": "kubernetes", "domain": "devops", "proof": PROOF_VERIFIED},
        {"stack": "react", "domain": "frontend", "proof": PROOF_VERIFIED},
    ]


def test_empty_session_makes_every_stack_claimed():
    result = stack_proof_map(["python", "postgresql", "react"], "backend", set())
    assert all(item["proof"] == PROOF_CLAIMED for item in result)
    assert all(item["domain"] is None for item in result)


def test_unknown_stack_is_claimed_and_does_not_raise():
    result = stack_proof_map(["блокчейн-магия-3000", ""], "backend", {"backend"})
    assert result == [
        {"stack": "блокчейн-магия-3000", "domain": None, "proof": PROOF_CLAIMED}
    ]


def test_build_stack_proof_reads_latest_completed_session():
    from backend.services.candidate_score import build_stack_proof

    db = SessionLocal()
    try:
        from backend.db import Base, engine

        Base.metadata.create_all(bind=engine)
        user = User(email="stack-proof@example.com", password_hash="x", role="candidate")
        db.add(user)
        db.flush()
        candidate = CandidateProfile(
            user_id=user.id,
            full_name="Тест Стек",
            stack=["postgresql", "react", "nginx"],
            specialization="backend",
        )
        db.add(candidate)
        db.flush()

        session = TestSession(
            candidate_profile_id=candidate.id,
            grade="middle",
            status="completed",
            task_count=2,
            correct_count=1,
            result_score=50,
        )
        db.add(session)
        db.flush()

        concept = Concept(name="Индексы", domain="databases", grade="middle")
        db.add(concept)
        db.flush()
        task = Task(
            concept_id=concept.id,
            grade="middle",
            statement="s",
            task_format="multiple_choice",
            reference_answer={},
        )
        db.add(task)
        db.flush()
        db.add(
            TestAnswer(session_id=session.id, task_id=task.id, is_correct=True)
        )
        db.commit()

        result = build_stack_proof(db, candidate)
        by_stack = {item["stack"]: item for item in result}
        assert by_stack["postgresql"] == {
            "stack": "postgresql",
            "domain": "databases",
            "proof": PROOF_VERIFIED,
        }
        assert by_stack["react"]["proof"] == PROOF_CLAIMED
        assert by_stack["nginx"]["proof"] == PROOF_CLAIMED
    finally:
        db.rollback()
        db.close()
