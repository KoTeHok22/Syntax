from tests.test_api import auth, register_and_login


def set_grade(email: str, grade: str) -> None:
    from backend.core.categorization import assign_category
    from backend.db import SessionLocal
    from backend.models import CandidateProfile, User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).first()
        profile.grade = grade
        assign_category(db, profile, profile.specialization, grade)
        db.commit()
    finally:
        db.close()


def test_profile_update_persists_city_and_work_format(client):
    token = register_and_login(client, "cwf-own@example.com", "candidate")
    response = client.put(
        "/candidates/me",
        json={
            "full_name": "Городской Кандидат",
            "contacts": {"email": "cwf-own@example.com"},
            "stack": ["python"],
            "specialization": "backend",
            "city": "Казань",
            "work_format": "hybrid",
        },
        headers=auth(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["city"] == "Казань"
    assert body["work_format"] == "hybrid"

    fetched = client.get("/candidates/me", headers=auth(token)).json()
    assert fetched["city"] == "Казань"
    assert fetched["work_format"] == "hybrid"


def test_card_exposes_city_and_work_format_without_identity(client):
    candidate_token = register_and_login(client, "cwf-cand@example.com", "candidate")
    client.put(
        "/candidates/me",
        json={
            "full_name": "Карточка Город",
            "contacts": {"email": "cwf-cand@example.com", "phone": "+70000000001"},
            "stack": ["python"],
            "specialization": "backend",
            "city": "Москва",
            "work_format": "remote",
        },
        headers=auth(candidate_token),
    )
    set_grade("cwf-cand@example.com", "middle")

    employer_token = register_and_login(client, "cwf-emp@example.com", "employer")
    categories = client.get("/employer/categories", headers=auth(employer_token)).json()["items"]
    category = next(c for c in categories if c["grade"] == "middle" and c["specialization"] == "backend")

    cards = client.get(
        f"/employer/categories/{category['id']}/cards",
        headers=auth(employer_token),
    ).json()
    card = next(c for c in cards if c["candidate_profile_id"] is not None)
    assert card["city"] == "Москва"
    assert card["work_format"] == "remote"
    assert "full_name" not in card
    assert "contacts" not in card


def test_card_filters_narrow_by_city_and_work_format(client):
    first_token = register_and_login(client, "cwf-f1@example.com", "candidate")
    client.put(
        "/candidates/me",
        json={
            "full_name": "Фильтр Москва",
            "contacts": {"email": "cwf-f1@example.com"},
            "stack": ["python"],
            "specialization": "backend",
            "city": "Москва",
            "work_format": "office",
        },
        headers=auth(first_token),
    )
    set_grade("cwf-f1@example.com", "middle")

    second_token = register_and_login(client, "cwf-f2@example.com", "candidate")
    client.put(
        "/candidates/me",
        json={
            "full_name": "Фильтр Казань",
            "contacts": {"email": "cwf-f2@example.com"},
            "stack": ["python"],
            "specialization": "backend",
            "city": "Казань",
            "work_format": "remote",
        },
        headers=auth(second_token),
    )
    set_grade("cwf-f2@example.com", "middle")

    employer_token = register_and_login(client, "cwf-femp@example.com", "employer")
    categories = client.get("/employer/categories", headers=auth(employer_token)).json()["items"]
    category = next(c for c in categories if c["grade"] == "middle" and c["specialization"] == "backend")
    endpoint = f"/employer/categories/{category['id']}/cards"

    all_cards = client.get(endpoint, headers=auth(employer_token)).json()
    assert len(all_cards) == 2

    by_city = client.get(endpoint, params={"city": "казань"}, headers=auth(employer_token)).json()
    assert len(by_city) == 1
    assert by_city[0]["city"] == "Казань"

    by_format = client.get(endpoint, params={"work_format": "office"}, headers=auth(employer_token)).json()
    assert len(by_format) == 1
    assert by_format[0]["work_format"] == "office"

    both = client.get(
        endpoint,
        params={"city": "Москва", "work_format": "remote"},
        headers=auth(employer_token),
    ).json()
    assert both == []


def test_empty_city_and_work_format_filters_keep_all_cards(client):
    candidate_token = register_and_login(client, "cwf-empty@example.com", "candidate")
    client.put(
        "/candidates/me",
        json={
            "full_name": "Пустой Фильтр",
            "contacts": {"email": "cwf-empty@example.com"},
            "stack": ["python"],
            "specialization": "backend",
            "city": "Новосибирск",
            "work_format": "hybrid",
        },
        headers=auth(candidate_token),
    )
    set_grade("cwf-empty@example.com", "middle")

    employer_token = register_and_login(client, "cwf-eemp@example.com", "employer")
    categories = client.get("/employer/categories", headers=auth(employer_token)).json()["items"]
    category = next(c for c in categories if c["grade"] == "middle" and c["specialization"] == "backend")
    endpoint = f"/employer/categories/{category['id']}/cards"

    baseline = client.get(endpoint, headers=auth(employer_token)).json()
    blank = client.get(endpoint, params={"city": "", "work_format": ""}, headers=auth(employer_token)).json()
    spaced = client.get(endpoint, params={"city": "   "}, headers=auth(employer_token)).json()

    assert baseline == blank == spaced
    assert len(baseline) == 1
