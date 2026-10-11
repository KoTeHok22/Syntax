from fastapi.testclient import TestClient

from tests.test_api import auth, register_and_login


def seed_candidate(
    email: str,
    stack: list[str],
    specialization: str = "backend",
    grade: str = "middle",
) -> int:
    from backend.core.categorization import assign_category
    from backend.db import SessionLocal
    from backend.models import CandidateProfile, User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).one()
        profile.stack = stack
        profile.specialization = specialization
        profile.grade = grade
        assign_category(db, profile, specialization, grade)
        candidate_id = profile.id
        db.commit()
        return candidate_id
    finally:
        db.close()


def seed_answers(candidate_id: int, answers: list[tuple[str, bool]]) -> None:
    from backend.db import SessionLocal
    from backend.models import Concept, Task, TestAnswer, TestSession

    db = SessionLocal()
    try:
        session = TestSession(
            candidate_profile_id=candidate_id,
            grade="middle",
            status="completed",
            task_count=len(answers),
            correct_count=sum(1 for _, is_correct in answers if is_correct),
            result_score=100,
        )
        db.add(session)
        db.flush()
        for index, (domain, is_correct) in enumerate(answers):
            concept = Concept(
                name=f"Концепт {domain} {candidate_id} {index}",
                domain=domain,
                grade="middle",
            )
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
            db.add(TestAnswer(session_id=session.id, task_id=task.id, is_correct=is_correct))
        db.commit()
    finally:
        db.close()


def backend_category_id(client: TestClient, employer_token: str) -> int:
    categories = client.get("/employer/categories", headers=auth(employer_token)).json()["items"]
    return next(c for c in categories if c["specialization"] == "backend")["id"]


def card_for(client: TestClient, employer_token: str, candidate_id: int) -> dict:
    category_id = backend_category_id(client, employer_token)
    cards = client.get(
        f"/employer/categories/{category_id}/cards", headers=auth(employer_token)
    ).json()
    return next(card for card in cards if card["candidate_profile_id"] == candidate_id)


def test_category_card_exposes_stack_proof(client: TestClient):
    register_and_login(client, "card-proof@example.com", "candidate")
    candidate_id = seed_candidate("card-proof@example.com", ["postgresql", "react"])
    employer_token = register_and_login(client, "card-proof-emp@example.com", "employer")

    card = card_for(client, employer_token, candidate_id)
    assert "stack_proof" in card
    assert {item["stack"] for item in card["stack_proof"]} == {"postgresql", "react"}
    for item in card["stack_proof"]:
        assert set(item) == {"stack", "domain", "proof"}
        assert item["proof"] in {"verified", "claimed"}


def test_search_card_exposes_stack_proof(client: TestClient):
    register_and_login(client, "search-proof@example.com", "candidate")
    candidate_id = seed_candidate("search-proof@example.com", ["python", "postgresql"])
    employer_token = register_and_login(client, "search-proof-emp@example.com", "employer")

    response = client.get("/employer/search", headers=auth(employer_token))
    assert response.status_code == 200
    card = next(c for c in response.json() if c["candidate_profile_id"] == candidate_id)
    assert "stack_proof" in card
    assert {item["stack"] for item in card["stack_proof"]} == {"python", "postgresql"}


def test_badges_reflect_session_answers(client: TestClient):
    register_and_login(client, "card-badges@example.com", "candidate")
    candidate_id = seed_candidate("card-badges@example.com", ["postgresql", "react"])
    seed_answers(candidate_id, [("databases", True), ("frontend", False)])
    employer_token = register_and_login(client, "card-badges-emp@example.com", "employer")

    proof = {item["stack"]: item for item in card_for(client, employer_token, candidate_id)["stack_proof"]}
    assert proof["postgresql"]["proof"] == "verified"
    assert proof["postgresql"]["domain"] == "databases"
    assert proof["react"]["proof"] == "claimed"
    assert proof["react"]["domain"] is None


def test_card_without_session_has_all_claimed(client: TestClient):
    register_and_login(client, "card-nosession@example.com", "candidate")
    candidate_id = seed_candidate("card-nosession@example.com", ["python", "postgresql", "react"])
    employer_token = register_and_login(client, "card-nosession-emp@example.com", "employer")

    card = card_for(client, employer_token, candidate_id)
    assert len(card["stack_proof"]) == 3
    assert all(item["proof"] == "claimed" for item in card["stack_proof"])
    assert all(item["domain"] is None for item in card["stack_proof"])


def test_bulk_matches_single_stack_proof(client: TestClient):
    from backend.db import SessionLocal
    from backend.models import CandidateProfile
    from backend.services.candidate_score import build_stack_proof, build_stack_proof_bulk

    register_and_login(client, "bulk-a@example.com", "candidate")
    first_id = seed_candidate("bulk-a@example.com", ["postgresql", "react"])
    seed_answers(first_id, [("databases", True)])

    register_and_login(client, "bulk-b@example.com", "candidate")
    second_id = seed_candidate("bulk-b@example.com", ["python", "nginx"])

    db = SessionLocal()
    try:
        candidates = (
            db.query(CandidateProfile)
            .filter(CandidateProfile.id.in_([first_id, second_id]))
            .all()
        )
        bulk = build_stack_proof_bulk(db, candidates)
        for candidate in candidates:
            assert bulk[candidate.id] == build_stack_proof(db, candidate)
    finally:
        db.close()
