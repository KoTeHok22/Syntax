from tests.test_api import auth, register_and_login, seed_concept_bank
from tests.conftest import seed_grade


def test_regular_task_flow_and_scoring(client):
    from backend.db import SessionLocal
    from backend.models import Concept

    db = SessionLocal()
    seed_concept_bank(db)
    concept = db.query(Concept).filter(Concept.grade == "junior").first()
    db.close()

    employer_token = register_and_login(client, "reg-emp@example.com", "employer")
    created = client.post(
        "/regular-tasks",
        json={"concept_id": concept.id},
        headers=auth(employer_token),
    )
    assert created.status_code == 201
    task = created.json()
    assert task["options"] and "reference_answer" not in task

    custom = client.post(
        "/regular-tasks",
        json={"statement": "Выберите верное утверждение", "options": ["да", "нет"], "correct_index": 0},
        headers=auth(employer_token),
    )
    assert custom.status_code == 201

    invalid = client.post(
        "/regular-tasks",
        json={"statement": "без вариантов"},
        headers=auth(employer_token),
    )
    assert invalid.status_code == 422

    candidate_token = register_and_login(client, "reg-cand@example.com", "candidate")
    client.put("/candidates/me", json={"specialization": "backend", "stack": ["python"]}, headers=auth(candidate_token))
    seed_grade("reg-cand@example.com", "junior", "backend")

    available = client.get("/regular-tasks", headers=auth(candidate_token)).json()
    assert len(available) == 2

    answer = client.post(
        f"/regular-tasks/{task['id']}/answer",
        json={"option_index": 0},
        headers=auth(candidate_token),
    )
    assert answer.status_code == 200

    duplicate = client.post(
        f"/regular-tasks/{task['id']}/answer",
        json={"option_index": 0},
        headers=auth(candidate_token),
    )
    assert duplicate.status_code == 409

    remaining = client.get("/regular-tasks", headers=auth(candidate_token)).json()
    assert len(remaining) == 1

    categories = client.get("/employer/categories", headers=auth(employer_token)).json()["items"]
    cards = client.get(
        f"/employer/categories/{categories[0]['id']}/cards",
        headers=auth(employer_token),
    ).json()
    breakdown = cards[0]["score_breakdown"]
    assert "regular_task_score" in breakdown

    submissions = client.get(
        f"/employer/regular-tasks/{task['id']}/submissions",
        headers=auth(employer_token),
    ).json()
    assert len(submissions) == 1
    assert submissions[0]["is_correct"] == (answer.json()["is_correct"])

    closed = client.post(f"/employer/regular-tasks/{task['id']}/close", headers=auth(employer_token))
    assert closed.status_code == 200
    assert closed.json()["is_active"] is False


def test_cards_pagination(client):
    employer_token = register_and_login(client, "page-emp@example.com", "employer")
    tokens = []
    for i in range(3):
        token = register_and_login(client, f"page-cand{i}@example.com", "candidate")
        client.put("/candidates/me", json={"specialization": "backend", "stack": ["python"]}, headers=auth(token))
        seed_grade(f"page-cand{i}@example.com", "junior", "backend")
        tokens.append(token)

    categories = client.get("/employer/categories", headers=auth(employer_token)).json()["items"]
    category_id = next(c for c in categories if c["specialization"] == "backend")["id"]
    first_page = client.get(
        f"/employer/categories/{category_id}/cards",
        params={"limit": 2},
        headers=auth(employer_token),
    ).json()
    assert len(first_page) == 2
    second_page = client.get(
        f"/employer/categories/{category_id}/cards",
        params={"limit": 2, "skip": 2},
        headers=auth(employer_token),
    ).json()
    assert len(second_page) == 1
    assert first_page[0]["candidate_profile_id"] != second_page[0]["candidate_profile_id"]
