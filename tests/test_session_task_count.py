from fastapi.testclient import TestClient

from backend.core.config import get_settings
from backend.core.testing import VERDICT_CONFIRMED, VERDICT_SUGGEST_HIGHER

from tests.test_api import auth, register_and_login


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


def start_session(client: TestClient, token: str, grade: str) -> dict:
    response = client.post("/test-sessions", json={"grade": grade}, headers=auth(token))
    assert response.status_code == 201, response.text
    return response.json()


def seed_pool_tasks(db, count: int, grade: str = "junior", domain: str = "devops") -> set[int]:
    from backend.models import Concept, Task

    concept_ids: set[int] = set()
    for index in range(count):
        concept = Concept(
            name=f"task-count-{domain}-{grade}-{index}",
            domain=domain,
            grade=grade,
            difficulty_params={"lines": "10-15", "structures": 1, "complexity": "O(n)", "edge_cases": False},
            task_format="multiple_choice",
            question_template="",
            correct_answer="",
            distractors=[],
        )
        db.add(concept)
        db.flush()
        concept_ids.add(concept.id)
        db.add(
            Task(
                concept_id=concept.id,
                grade=grade,
                statement=f"Пул-задача {domain} {index}",
                task_format="multiple_choice",
                options=["a", "b", "c", "d"],
                reference_answer=0,
            )
        )
    db.commit()
    return concept_ids


def seed_concepts(db, count: int, grade: str, domain: str) -> None:
    from backend.models import Concept

    for index in range(count):
        db.add(
            Concept(
                name=f"bank-{grade}-{domain}-{index}",
                domain=domain,
                grade=grade,
                difficulty_params={"lines": "10-15", "structures": 1, "complexity": "O(n)", "edge_cases": False},
                task_format="multiple_choice",
                question_template="Сервис {company} обрабатывает {n} записей. Что верно?",
                correct_answer="Верный вариант",
                distractors=["Неверный вариант A", "Неверный вариант B", "Неверный вариант C"],
            )
        )
    db.commit()


def test_session_receives_exact_tasks_per_session_for_each_grade(client):
    from backend.db import SessionLocal

    expected = get_settings().tasks_per_session

    db = SessionLocal()
    for grade in ("junior", "middle", "senior"):
        seed_concepts(db, expected + 5, grade, "devops")
    db.close()

    cases = [
        ("count-junior@example.com", "backend", "junior"),
        ("count-middle@example.com", "frontend", "middle"),
        ("count-senior@example.com", "backend", "senior"),
    ]
    for email, specialization, grade in cases:
        token = seed_candidate(client, email, specialization, grade)
        body = start_session(client, token, grade)
        assert body["task_count"] == expected, f"{grade}: {body['task_count']} != {expected}"
        assert len(body["tasks"]) == expected


def test_session_backfills_from_general_pool_when_domain_pool_is_short(client):
    from backend.db import SessionLocal
    from backend.models import Task

    db = SessionLocal()
    devops_concept_ids = seed_pool_tasks(db, 3, grade="junior", domain="devops")
    seed_concepts(db, get_settings().tasks_per_session + 5, "junior", "devops")
    db.close()
    expected = get_settings().tasks_per_session

    token = seed_candidate(client, "backfill@example.com", "backend", "junior")
    body = start_session(client, token, "junior")

    assert body["task_count"] == expected
    assert len(body["tasks"]) == expected
    task_ids = {task["id"] for task in body["tasks"]}

    db = SessionLocal()
    pool_tasks = db.query(Task).filter(Task.concept_id.in_(devops_concept_ids)).all()
    assert len(pool_tasks) == 3
    assert {task.id for task in pool_tasks}.issubset(task_ids), "домен-специфичные пул-задачи должны быть использованы"

    session_tasks = db.query(Task).filter(Task.session_id == body["id"]).all()
    concepts_in_session = {task.concept_id for task in session_tasks}
    assert len(concepts_in_session) == expected
    db.close()


def test_session_never_truncates_silently_when_bank_is_short(client):
    from backend.db import SessionLocal
    from backend.models import Concept, TestSession

    db = SessionLocal()
    assert db.query(Concept).count() == 0
    seed_pool_tasks(db, 5, grade="junior", domain="devops")
    db.close()
    expected = get_settings().tasks_per_session

    token = seed_candidate(client, "short-pool@example.com", "backend", "junior")
    body = start_session(client, token, "junior")

    assert body["task_count"] >= 1
    assert body["task_count"] == len(body["tasks"])
    assert body["task_count"] <= expected

    db = SessionLocal()
    stored = db.get(TestSession, body["id"])
    assert stored is not None
    assert stored.task_count == len(body["tasks"])
    db.close()


def test_task_count_equals_number_of_tasks(client):
    from backend.db import SessionLocal
    from backend.models import Task, TestSession

    db = SessionLocal()
    seed_concepts(db, get_settings().tasks_per_session + 5, "junior", "devops")
    seed_pool_tasks(db, 2, grade="junior", domain="devops")
    db.close()

    token = seed_candidate(client, "consistency@example.com", "backend", "junior")
    body = start_session(client, token, "junior")

    db = SessionLocal()
    stored = db.get(TestSession, body["id"])
    task_rows = db.query(Task).filter(Task.session_id == body["id"]).all()
    assert stored is not None
    assert stored.task_count == len(task_rows)
    assert stored.task_count == len(body["tasks"])
    assert stored.task_count == body["task_count"]
    db.close()


def test_verdict_uses_real_task_count(client):
    from backend.db import SessionLocal
    from backend.models import Task

    db = SessionLocal()
    seed_concepts(db, get_settings().tasks_per_session + 5, "junior", "devops")
    seed_pool_tasks(db, 4, grade="junior", domain="devops")
    db.close()

    token = seed_candidate(client, "verdict@example.com", "backend", "junior")
    body = start_session(client, token, "junior")
    expected = get_settings().tasks_per_session
    assert body["task_count"] == expected

    db = SessionLocal()
    tasks = db.query(Task).filter(Task.session_id == body["id"]).all()
    submissions = [
        {"task_id": task.id, "option_index": task.reference_answer if isinstance(task.reference_answer, int) else 0}
        for task in tasks
    ]
    db.close()

    result = client.post(
        f"/test-sessions/{body['id']}/answers",
        json=submissions,
        headers=auth(token),
    )
    assert result.status_code == 200, result.text
    payload = result.json()

    assert payload["task_count"] == expected
    assert payload["correct_count"] == expected
    assert payload["result_score"] == 100
    assert payload["verdict"] in {VERDICT_CONFIRMED, VERDICT_SUGGEST_HIGHER}

    review = client.get(f"/test-sessions/{body['id']}/review", headers=auth(token))
    assert review.status_code == 200
    assert review.json()["task_count"] == expected
    assert len(review.json()["review"]) == expected
