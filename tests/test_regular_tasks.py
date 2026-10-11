from tests.test_api import auth, register_and_login, seed_concept_bank
from tests.conftest import seed_grade


def create_vacancy(client, employer_token: str, title: str = "Backend разработчик") -> int:
    vacancy = client.post(
        "/vacancies",
        json={
            "title": title,
            "stack": ["python"],
            "specialization": "backend",
            "grade": "middle",
            "salary_from": 200000,
            "salary_to": 300000,
        },
        headers=auth(employer_token),
    )
    assert vacancy.status_code == 201
    return vacancy.json()["id"]


def test_regular_task_requires_vacancy_and_hides_without_application(client):
    from backend.db import SessionLocal
    from backend.models import Concept

    db = SessionLocal()
    seed_concept_bank(db)
    concept = db.query(Concept).filter(Concept.grade == "junior").first()
    db.close()

    employer_token = register_and_login(client, "reg-emp@example.com", "employer")

    no_vacancy = client.post(
        "/regular-tasks",
        json={"statement": "Выберите верное утверждение", "options": ["да", "нет"], "correct_index": 0},
        headers=auth(employer_token),
    )
    assert no_vacancy.status_code == 422

    vacancy_id = create_vacancy(client, employer_token)

    created = client.post(
        "/regular-tasks",
        json={"concept_id": concept.id, "vacancy_id": vacancy_id},
        headers=auth(employer_token),
    )
    assert created.status_code == 201
    task = created.json()
    assert task["vacancy_id"] == vacancy_id
    assert task["options"] and "reference_answer" not in task

    custom = client.post(
        "/regular-tasks",
        json={"vacancy_id": vacancy_id, "statement": "Выберите верное утверждение", "options": ["да", "нет"], "correct_index": 0},
        headers=auth(employer_token),
    )
    assert custom.status_code == 201

    other_vacancy = create_vacancy(client, employer_token, title="Другая вакансия")
    forbidden = client.post(
        "/regular-tasks",
        json={"concept_id": concept.id, "vacancy_id": other_vacancy},
        headers=auth(register_and_login(client, "reg-emp-other@example.com", "employer")),
    )
    assert forbidden.status_code == 404

    candidate_token = register_and_login(client, "reg-cand@example.com", "candidate")
    client.put("/candidates/me", json={"specialization": "backend", "stack": ["python"]}, headers=auth(candidate_token))
    seed_grade("reg-cand@example.com", "junior", "backend")

    hidden = client.get(f"/regular-tasks/vacancy/{vacancy_id}", headers=auth(candidate_token))
    assert hidden.status_code == 404

    application = client.post(
        "/applications",
        json={"vacancy_id": vacancy_id, "message": "Отклик"},
        headers=auth(candidate_token),
    )
    assert application.status_code == 201
    application_id = application.json()["id"]

    status = client.get(f"/regular-tasks/vacancy/{vacancy_id}", headers=auth(candidate_token)).json()
    assert status["application_id"] == application_id
    assert status["task_count"] == 2
    assert status["status"] == "none"

    session = client.post(f"/regular-tasks/vacancy/{vacancy_id}/session", headers=auth(candidate_token))
    assert session.status_code == 201
    body = session.json()
    assert body["task_count"] == 2
    assert body["status"] == "pending"
    assert body["expires_at"] is not None
    assert len(body["tasks"]) == 2
    assert "reference_answer" not in body["tasks"][0]

    retry = client.post(f"/regular-tasks/vacancy/{vacancy_id}/session", headers=auth(candidate_token))
    assert retry.status_code == 201
    assert retry.json()["id"] == body["id"]

    task_ids = [item["id"] for item in body["tasks"]]
    answers = [{"regular_task_id": task_ids[0], "option_index": 0}, {"regular_task_id": task_ids[1], "option_index": 1}]
    result = client.post(
        f"/regular-tasks/sessions/{body['id']}/answers",
        json=answers,
        headers=auth(candidate_token),
    )
    assert result.status_code == 200
    graded = result.json()
    assert graded["status"] == "completed"
    assert graded["task_count"] == 2
    assert graded["result_score"] is not None

    duplicate = client.post(
        f"/regular-tasks/sessions/{body['id']}/answers",
        json=answers,
        headers=auth(candidate_token),
    )
    assert duplicate.status_code == 409

    results = client.get(
        "/employer/regular-tasks/results",
        params={"vacancy_id": vacancy_id},
        headers=auth(employer_token),
    ).json()
    assert len(results) == 1
    assert results[0]["application_id"] == application_id
    assert results[0]["status"] == "completed"

    breakdown = client.get(
        f"/employer/categories/{client.get('/employer/categories', headers=auth(employer_token)).json()['items'][0]['id']}/cards",
        headers=auth(employer_token),
    ).json()[0]["score_breakdown"]
    assert "regular_task_score" not in breakdown

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
