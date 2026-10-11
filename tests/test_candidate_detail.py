from fastapi.testclient import TestClient

from tests.test_api import auth, register_and_login


def seed_candidate(
    email: str,
    full_name: str,
    stack: list[str],
    specialization: str = "backend",
    grade: str = "middle",
    contacts: dict | None = None,
    pvn_id: str | None = None,
) -> int:
    from backend.db import SessionLocal
    from backend.models import CandidateProfile, User
    from backend.core.categorization import assign_category

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).one()
        profile.full_name = full_name
        profile.stack = stack
        profile.years_of_experience = 4
        profile.soft_skills = ["коммуникация"]
        profile.city = "Москва"
        profile.work_format = "remote"
        profile.specialization = specialization
        profile.contacts = contacts or {"email": f"{email}", "phone": "+79990000000"}
        if pvn_id is not None:
            user.pvn_id = pvn_id
        profile.grade = grade
        assign_category(db, profile, specialization, grade)
        candidate_id = profile.id
        db.commit()
        return candidate_id
    finally:
        db.close()


def test_candidate_detail_returns_stack_proof(client: TestClient):
    candidate_token = register_and_login(client, "detail-stack@example.com", "candidate")
    candidate_id = seed_candidate(
        "detail-stack@example.com",
        "Деталь Стеков",
        ["postgresql", "react"],
    )
    employer_token = register_and_login(client, "detail-emp@example.com", "employer")

    response = client.get(f"/employer/candidates/{candidate_id}", headers=auth(employer_token))
    assert response.status_code == 200
    body = response.json()
    proof = {item["stack"]: item for item in body["stack_proof"]}
    assert set(proof) == {"postgresql", "react"}
    assert all(item["proof"] in {"verified", "claimed"} for item in body["stack_proof"])
    assert proof["postgresql"]["proof"] == "claimed"


def test_candidate_detail_hides_identity_fields(client: TestClient):
    register_and_login(client, "detail-priv@example.com", "candidate")
    candidate_id = seed_candidate(
        "detail-priv@example.com",
        "Приват Персонов",
        ["python"],
        pvn_id="PVN-SECRET-123",
    )
    employer_token = register_and_login(client, "detail-priv-emp@example.com", "employer")

    response = client.get(f"/employer/candidates/{candidate_id}", headers=auth(employer_token))
    assert response.status_code == 200
    body = response.json()
    for forbidden in ("full_name", "contacts", "avatar_data_url", "resume_text", "pvn_id"):
        assert forbidden not in body
    assert "Приват Персонов" not in response.text
    assert "PVN-SECRET-123" not in response.text


def test_candidate_detail_aggregates_pvn_achievements(client: TestClient):
    from datetime import date

    from backend.db import SessionLocal
    from backend.models import PvnAchievement

    register_and_login(client, "detail-pvn@example.com", "candidate")
    candidate_id = seed_candidate("detail-pvn@example.com", "ПВН Деталь", ["python"])

    db = SessionLocal()
    try:
        db.add(
            PvnAchievement(
                candidate_profile_id=candidate_id,
                achievement_type="хакатон",
                level="победитель",
                achieved_at=date(2026, 3, 14),
                score=40.0,
                source_issuer="Лига Уникальных Соревнований",
            )
        )
        db.commit()
    finally:
        db.close()

    employer_token = register_and_login(client, "detail-pvn-emp@example.com", "employer")
    response = client.get(f"/employer/candidates/{candidate_id}", headers=auth(employer_token))
    assert response.status_code == 200
    body = response.json()
    assert body["pvn_achievements"] == [{"type": "хакатон", "level": "победитель"}]
    assert "2026-03-14" not in response.text
    assert "Лига Уникальных Соревнований" not in response.text


def test_hidden_candidate_detail_is_404(client: TestClient):
    candidate_token = register_and_login(client, "detail-hidden@example.com", "candidate")
    candidate_id = seed_candidate("detail-hidden@example.com", "Скрытый Профиль", ["python"])
    employer_token = register_and_login(client, "detail-hidden-emp@example.com", "employer")

    assert client.get(f"/employer/candidates/{candidate_id}", headers=auth(employer_token)).status_code == 200
    hidden = client.put("/candidates/me/visibility", json={"is_visible": False}, headers=auth(candidate_token))
    assert hidden.status_code == 200
    assert client.get(f"/employer/candidates/{candidate_id}", headers=auth(employer_token)).status_code == 404
    assert client.get("/employer/candidates/999999", headers=auth(employer_token)).status_code == 404


def test_candidate_without_session_has_all_stack_claimed(client: TestClient):
    register_and_login(client, "detail-nosession@example.com", "candidate")
    candidate_id = seed_candidate(
        "detail-nosession@example.com",
        "Без Сессии",
        ["python", "postgresql", "react"],
    )
    employer_token = register_and_login(client, "detail-nosession-emp@example.com", "employer")

    response = client.get(f"/employer/candidates/{candidate_id}", headers=auth(employer_token))
    assert response.status_code == 200
    body = response.json()
    assert len(body["stack_proof"]) == 3
    assert all(item["proof"] == "claimed" for item in body["stack_proof"])
    assert all(item["domain"] is None for item in body["stack_proof"])
    assert body["is_verified"] is False
    assert body["proof_tier"] == "claimed"


def test_candidate_detail_requires_employer_role(client: TestClient):
    candidate_token = register_and_login(client, "detail-role@example.com", "candidate")
    candidate_id = seed_candidate("detail-role@example.com", "Роль Проверка", ["python"])

    forbidden = client.get(f"/employer/candidates/{candidate_id}", headers=auth(candidate_token))
    assert forbidden.status_code == 403
    assert client.get(f"/employer/candidates/{candidate_id}").status_code == 401


def test_candidate_detail_match_relevance_with_vacancy(client: TestClient):
    register_and_login(client, "detail-match@example.com", "candidate")
    candidate_id = seed_candidate("detail-match@example.com", "Матч Деталь", ["python", "postgresql"])
    employer_token = register_and_login(client, "detail-match-emp@example.com", "employer")

    no_vacancy = client.get(f"/employer/candidates/{candidate_id}", headers=auth(employer_token)).json()
    assert no_vacancy["match_relevance"] is None

    vacancy = client.post(
        "/vacancies",
        json={
            "title": "Backend",
            "stack": ["python", "redis"],
            "specialization": "backend",
            "grade": "middle",
            "salary_from": 100000,
            "salary_to": 200000,
        },
        headers=auth(employer_token),
    )
    assert vacancy.status_code == 201
    with_vacancy = client.get(
        f"/employer/candidates/{candidate_id}",
        params={"vacancy_id": vacancy.json()["id"]},
        headers=auth(employer_token),
    )
    assert with_vacancy.status_code == 200
    assert with_vacancy.json()["match_relevance"] == 0.5

    foreign = client.get(
        f"/employer/candidates/{candidate_id}",
        params={"vacancy_id": 999999},
        headers=auth(employer_token),
    )
    assert foreign.status_code == 404
