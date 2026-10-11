from collections import Counter, defaultdict

from fastapi.testclient import TestClient

from backend.core.config import get_settings
from backend.core.labels import SPECIALIZATION_DOMAINS

from tests.test_api import auth, register_and_login

ANNOTATION_FORMAT = "design_annotation"
GRADES = ("junior", "middle", "senior")


def objective_concepts_by_grade() -> dict[str, int]:
    from scripts.concept_bank import CONCEPTS

    counts: Counter[str] = Counter()
    for entry in CONCEPTS:
        if entry.get("format") == ANNOTATION_FORMAT:
            continue
        counts[entry["grade"]] += 1
    return counts


def objective_concepts_per_specialization() -> dict[str, dict[str, int]]:
    from scripts.concept_bank import CONCEPTS

    per_domain: dict[str, Counter[str]] = defaultdict(Counter)
    for entry in CONCEPTS:
        if entry.get("format") == ANNOTATION_FORMAT:
            continue
        per_domain[entry["domain"]][entry["grade"]] += 1
    return {
        spec: {grade: sum(per_domain[domain][grade] for domain in domains) for grade in GRADES}
        for spec, domains in SPECIALIZATION_DOMAINS.items()
    }


def seed_candidate(client: TestClient, email: str, specialization: str, grade: str) -> str:
    token = register_and_login(client, email, "candidate")
    profile = client.put(
        "/candidates/me",
        json={"full_name": email, "contacts": {"email": email}, "specialization": specialization},
        headers=auth(token),
    )
    assert profile.status_code == 200, profile.text

    from backend.db import SessionLocal
    from backend.core.categorization import assign_category
    from backend.models import CandidateProfile, User

    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    candidate = db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).first()
    candidate.grade = grade
    candidate.specialization = specialization
    assign_category(db, candidate, specialization, grade)
    db.commit()
    db.close()
    return token


def seed_full_bank(db) -> None:
    from scripts.seed import seed_concepts, seed_contexts

    db.close()
    seed_concepts()
    seed_contexts()


def bank_has_capacity_for_both_objective_and_annotation() -> None:
    from scripts.concept_bank import CONCEPTS

    settings = get_settings()
    required = settings.tasks_per_session + 1
    counts = objective_concepts_by_grade()
    for grade in GRADES:
        assert counts[grade] >= required, f"{grade}: {counts[grade]} объективных концептов < {required}"
    total = Counter(entry["grade"] for entry in CONCEPTS)
    for grade in GRADES:
        assert total[grade] >= required, f"{grade}: {total[grade]} концептов всего < {required}"


def test_bank_has_enough_concepts_per_grade_for_full_session():
    bank_has_capacity_for_both_objective_and_annotation()


def test_bank_has_enough_concepts_per_specialization_and_grade():
    settings = get_settings()
    required = settings.tasks_per_session + 1
    per_spec = objective_concepts_per_specialization()
    per_grade = objective_concepts_by_grade()
    for spec, by_grade in per_spec.items():
        for grade in GRADES:
            reachable = by_grade[grade] + (per_grade[grade] - by_grade[grade])
            assert reachable >= required, (
                f"{spec}/{grade}: доступно {reachable} объективных концептов < {required}; "
                "specialization получит усечённую сессию"
            )


def test_session_receives_tasks_per_session_for_every_grade(client: TestClient):
    from backend.db import SessionLocal

    seed_full_bank(SessionLocal())
    expected = get_settings().tasks_per_session

    cases = [
        ("parity-backend-junior@example.com", "backend", "junior"),
        ("parity-backend-middle@example.com", "backend", "middle"),
        ("parity-backend-senior@example.com", "backend", "senior"),
        ("parity-frontend-senior@example.com", "frontend", "senior"),
        ("parity-data-senior@example.com", "data", "senior"),
        ("parity-devops-senior@example.com", "devops", "senior"),
    ]
    for email, specialization, grade in cases:
        token = seed_candidate(client, email, specialization, grade)
        response = client.post("/test-sessions", json={"grade": grade}, headers=auth(token))
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["task_count"] == expected, (
            f"{specialization}/{grade}: task_count={body['task_count']} != {expected}"
        )
        assert len(body["tasks"]) == expected, (
            f"{specialization}/{grade}: {len(body['tasks'])} задач != {expected}"
        )
