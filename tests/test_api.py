from fastapi.testclient import TestClient

from backend.core.config import get_settings

def register_and_login(client: TestClient, email: str, role: str) -> str:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "password123", "role": role, "consent_accepted": True},
    )
    assert response.status_code == 201
    confirmation_url = response.json()["confirmation_url"]
    assert client.get(confirmation_url).status_code == 200
    login = client.post("/auth/login", data={"username": email, "password": "password123"})
    assert login.status_code == 200
    return login.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_health(client):
    assert client.get("/health").status_code == 200


def test_register_requires_consent(client):
    response = client.post(
        "/auth/register",
        json={"email": "no-consent@example.com", "password": "password123", "role": "candidate", "consent_accepted": False},
    )
    assert response.status_code == 400


def test_register_rejects_free_text_specialization(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "junk-spec@example.com",
            "password": "password123",
            "role": "candidate",
            "consent_accepted": True,
            "specialization": "Backend, аналитика, ML",
            "grade": "junior",
        },
    )
    assert response.status_code == 422


def test_profile_update_rejects_free_text_specialization(client):
    token = register_and_login(client, "spec-guard@example.com", "candidate")
    response = client.put(
        "/candidates/me",
        json={"full_name": "Гард", "specialization": "Backend, аналитика, ML"},
        headers=auth(token),
    )
    assert response.status_code == 422


def test_register_accepts_known_specialization(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "known-spec@example.com",
            "password": "password123",
            "role": "candidate",
            "consent_accepted": True,
            "specialization": "devops",
            "grade": "middle",
        },
    )
    assert response.status_code == 201
    assert response.json()["category_id"] is not None


def test_register_candidate_assigns_category_immediately(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "categorized@example.com",
            "password": "password123",
            "role": "candidate",
            "consent_accepted": True,
            "specialization": "backend",
            "grade": "middle",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["category_id"] is not None
    assert client.get(body["confirmation_url"]).status_code == 200
    token = client.post(
        "/auth/login", data={"username": "categorized@example.com", "password": "password123"}
    ).json()["access_token"]
    profile = client.get("/candidates/me", headers=auth(token)).json()
    assert profile["specialization"] == "backend"
    assert profile["grade"] == "middle"


def test_register_candidate_without_category_leaves_it_empty(client):
    response = client.post(
        "/auth/register",
        json={"email": "plain@example.com", "password": "password123", "role": "candidate", "consent_accepted": True},
    )
    assert response.status_code == 201
    assert response.json()["category_id"] is None


def test_demo_fixtures_populate_every_role_screen(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.core.config import get_settings
    from backend.db import Base, SessionLocal, engine
    from backend.main import app
    from backend.models import Application, Invitation, RegularTask

    monkeypatch.setenv("SEED_DEMO", "1")
    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    try:
        with TestClient(app) as demo_client:
            db = SessionLocal()
            try:
                assert db.query(Invitation).count() > 0
                assert db.query(Application).count() > 0
                assert db.query(RegularTask).count() > 0
                statuses = {row.status for row in db.query(Invitation).all()}
                assert statuses == {"sent", "viewed", "accepted", "rejected"}
            finally:
                db.close()
            login = demo_client.post(
                "/auth/login", data={"username": "demo-employer@example.com", "password": "demo-password"}
            )
            assert login.status_code == 200
    finally:
        Base.metadata.drop_all(bind=engine)
        monkeypatch.delenv("SEED_DEMO", raising=False)
        get_settings.cache_clear()


def test_login_requires_email_confirmation(client):
    client.post(
        "/auth/register",
        json={"email": "unconfirmed@example.com", "password": "password123", "role": "candidate", "consent_accepted": True},
    )
    response = client.post("/auth/login", data={"username": "unconfirmed@example.com", "password": "password123"})
    assert response.status_code == 403


def test_my_vacancies_include_closed_and_update_flow(client):
    employer_token = register_and_login(client, "emp20@example.com", "employer")
    other_token = register_and_login(client, "emp21@example.com", "employer")

    headers = auth(employer_token)
    first = client.post(
        "/vacancies",
        json={
            "title": "Backend разработчик",
            "stack": ["python"],
            "specialization": "backend",
            "grade": "middle",
            "salary_from": 200000,
            "salary_to": 300000,
        },
        headers=headers,
    )
    second = client.post(
        "/vacancies",
        json={
            "title": "Frontend разработчик",
            "stack": ["react"],
            "specialization": "frontend",
            "grade": "junior",
            "salary_from": 100000,
            "salary_to": 150000,
        },
        headers=headers,
    )
    first_id = first.json()["id"]
    second_id = second.json()["id"]
    assert client.post(f"/vacancies/{second_id}/close", headers=headers).status_code == 200

    my = client.get("/vacancies/my", headers=headers)
    assert my.status_code == 200
    assert {v["id"] for v in my.json()} == {first_id, second_id}
    closed = next(v for v in my.json() if v["id"] == second_id)
    assert closed["status"] == "closed"

    other_my = client.get("/vacancies/my", headers=auth(other_token))
    assert other_my.json() == []

    updated = client.put(
        f"/vacancies/{first_id}",
        json={
            "title": "Senior Backend разработчик",
            "description": "Обновлено",
            "stack": ["python", "postgresql"],
            "specialization": "Backend",
            "grade": "senior",
            "salary_from": 300000,
            "salary_to": 400000,
        },
        headers=headers,
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["title"] == "Senior Backend разработчик"
    assert body["specialization"] == "backend"
    assert body["grade"] == "senior"
    assert body["salary_from"] == 300000
    assert body["salary_to"] == 400000
    assert body["status"] == "open"

    not_owner = client.put(
        f"/vacancies/{first_id}",
        json={
            "title": "Чужая вакансия",
            "salary_from": 100,
            "salary_to": 200,
        },
        headers=auth(other_token),
    )
    assert not_owner.status_code == 404

    inverted = client.put(
        f"/vacancies/{first_id}",
        json={
            "title": "Рнверсия",
            "salary_from": 500000,
            "salary_to": 100000,
        },
        headers=headers,
    )
    assert inverted.status_code == 422


def test_invitations_and_applications_pagination(client):
    candidate_token = register_and_login(client, "cand30@example.com", "candidate")
    employer_token = register_and_login(client, "emp30@example.com", "employer")

    client.put(
        "/candidates/me",
        json={
            "full_name": "Пагинация Кандидатов",
            "contacts": {"email": "p@example.com"},
            "stack": ["python"],
            "specialization": "backend",
        },
        headers=auth(candidate_token),
    )
    from backend.db import SessionLocal as _SessionLocal2
    from backend.models import CandidateProfile as _CandidateProfile2
    from backend.core.categorization import assign_category as _assign_category2

    _db2 = _SessionLocal2()
    _profile2 = _db2.query(_CandidateProfile2).filter(_CandidateProfile2.full_name == "Пагинация Кандидатов").first()
    _profile2.grade = "junior"
    _assign_category2(_db2, _profile2, "backend", "junior")
    _db2.commit()
    _db2.close()

    category_id = client.get("/employer/categories", headers=auth(employer_token)).json()["items"][0]["id"]
    card = client.get(f"/employer/categories/{category_id}/cards", headers=auth(employer_token)).json()[0]

    for _ in range(3):
        invitation = client.post(
            "/invitations",
            json={
                "candidate_profile_id": card["candidate_profile_id"],
                "message": "РџСЂРёРіР»Р°С€ение",
                "salary_from": 100000,
                "salary_to": 150000,
                "company_name": "ООО Пагинация",
                "contact_method": "hr@example.com",
            },
            headers=auth(employer_token),
        )
        assert invitation.status_code == 201

    incoming = client.get("/invitations/incoming", params={"limit": 1}, headers=auth(candidate_token))
    assert incoming.status_code == 200
    assert len(incoming.json()) == 1
    sent = client.get("/invitations/sent", params={"limit": 1}, headers=auth(employer_token))
    assert sent.status_code == 200
    assert len(sent.json()) == 1
    sent_skipped = client.get(
        "/invitations/sent", params={"skip": 2, "limit": 1}, headers=auth(employer_token)
    )
    assert len(sent_skipped.json()) == 1

    for i in range(2):
        vacancy = client.post(
            "/vacancies",
            json={
                "title": f"Вакансия {i}",
                "salary_from": 100000,
                "salary_to": 150000,
            },
            headers=auth(employer_token),
        )
        application = client.post(
            "/applications",
            json={"vacancy_id": vacancy.json()["id"], "message": "Отклик"},
            headers=auth(candidate_token),
        )
        assert application.status_code == 201

    my = client.get("/applications/my", params={"limit": 1}, headers=auth(candidate_token))
    assert my.status_code == 200
    assert len(my.json()) == 1
    incoming_apps = client.get(
        "/applications/incoming", params={"limit": 1}, headers=auth(employer_token)
    )
    assert incoming_apps.status_code == 200
    assert len(incoming_apps.json()) == 1


def test_full_matching_flow(client):
    candidate_token = register_and_login(client, "cand@example.com", "candidate")
    response = client.put(
        "/candidates/me",
        json={
            "full_name": "Рван Кандидатов",
            "contacts": {"email": "ivan@example.com", "phone": "+70000000000"},
            "stack": ["python", "fastapi"],
            "years_of_experience": 2,
            "soft_skills": ["teamwork"],
            "specialization": "backend",
        },
        headers=auth(candidate_token),
    )
    assert response.status_code == 200
    promotion = client.put("/candidates/me/grade", json={"grade": "junior"}, headers=auth(candidate_token))
    assert promotion.status_code == 409
    assert client.get("/employer/categories", headers=auth(candidate_token)).status_code == 403

    from backend.db import SessionLocal as _SessionLocal3
    from backend.models import CandidateProfile as _CandidateProfile3
    from backend.core.categorization import assign_category as _assign_category3

    _db3 = _SessionLocal3()
    _profile3 = _db3.query(_CandidateProfile3).filter(_CandidateProfile3.full_name == "Рван Кандидатов").first()
    _profile3.grade = "junior"
    _assign_category3(_db3, _profile3, "backend", "junior")
    _db3.commit()
    _db3.close()

    employer_token = register_and_login(client, "emp@example.com", "employer")
    categories = client.get("/employer/categories", headers=auth(employer_token))
    assert categories.status_code == 200
    category_id = categories.json()["items"][0]["id"]

    cards = client.get(f"/employer/categories/{category_id}/cards", headers=auth(employer_token))
    assert cards.status_code == 200
    card = cards.json()[0]
    assert "full_name" not in card
    assert "contacts" not in card
    assert card["has_pvn_history"] is False
    assert card["score"] == 100.0
    assert set(card["score_breakdown"].keys()) == {"profile_completeness"}
    assert card["score_breakdown"]["profile_completeness"]["weight"] == 1.0
    assert card["proof_tier"] == "claimed"
    assert card["is_verified"] is False

    invitation = client.post(
        "/invitations",
        json={
            "candidate_profile_id": card["candidate_profile_id"],
            "message": "РџСЂРёРіР»Р°С€ение в команду",
            "salary_from": 100000,
            "salary_to": 150000,
            "company_name": "ООО Пример",
            "contact_method": "hr@example.com",
        },
        headers=auth(employer_token),
    )
    assert invitation.status_code == 201
    invitation_id = invitation.json()["id"]

    invalid_salary = client.post(
        "/invitations",
        json={
            "candidate_profile_id": card["candidate_profile_id"],
            "message": "x",
            "salary_from": 150000,
            "salary_to": 100000,
            "company_name": "y",
            "contact_method": "z",
        },
        headers=auth(employer_token),
    )
    assert invalid_salary.status_code == 422

    incoming = client.get("/invitations/incoming", headers=auth(candidate_token))
    assert incoming.json()[0]["contact_method"] is None
    assert incoming.json()[0]["candidate_contacts"] is None
    sent = client.get("/invitations/sent", headers=auth(employer_token))
    assert sent.json()[0]["candidate_contacts"] is None

    assert client.post(f"/invitations/{invitation_id}/view", headers=auth(candidate_token)).status_code == 200
    accepted = client.post(f"/invitations/{invitation_id}/accept", headers=auth(candidate_token))
    assert accepted.json()["status"] == "accepted"
    accepted_incoming = client.get("/invitations/incoming", headers=auth(candidate_token))
    assert accepted_incoming.json()[0]["contact_method"] == "hr@example.com"
    assert accepted_incoming.json()[0]["candidate_contacts"] is None
    sent_after_accept = client.get("/invitations/sent", headers=auth(employer_token))
    assert sent_after_accept.json()[0]["candidate_contacts"] is not None


def test_cards_filters_and_match_relevance(client):
    from backend.db import SessionLocal
    from backend.models import PvnAchievement
    from datetime import date

    candidate_token = register_and_login(client, "cand10@example.com", "candidate")
    update = client.put(
        "/candidates/me",
        json={
            "full_name": "Фильтр Кандидатов",
            "contacts": {"email": "f@example.com"},
            "stack": ["python", "postgresql"],
            "years_of_experience": 3,
            "soft_skills": ["коммуникация"],
            "specialization": "backend",
        },
        headers=auth(candidate_token),
    )
    assert update.status_code == 200
    from backend.db import SessionLocal as _SessionLocal
    from backend.models import CandidateProfile as _CandidateProfile
    from backend.core.categorization import assign_category as _assign_category

    _db = _SessionLocal()
    _profile = _db.query(_CandidateProfile).filter(_CandidateProfile.full_name == "Фильтр Кандидатов").first()
    _profile.grade = "middle"
    _assign_category(_db, _profile, "backend", "middle")
    _db.commit()
    _db.close()

    employer_token = register_and_login(client, "emp10@example.com", "employer")
    categories = client.get("/employer/categories", headers=auth(employer_token)).json()["items"]
    category = next(c for c in categories if c["grade"] == "middle" and c["specialization"] == "backend")

    cards = client.get(
        f"/employer/categories/{category['id']}/cards",
        params={"stack": ["python", "redis"]},
        headers=auth(employer_token),
    )
    assert cards.status_code == 200
    card = cards.json()[0]
    assert card["match_relevance"] == 0.5
    from backend.core.scoring import final_score as _final_score

    assert card["final_score"] == round(_final_score(card["score"], 0.5), 2)
    assert card["has_pvn_history"] is False

    db = SessionLocal()
    candidate_id = card["candidate_profile_id"]
    db.add(PvnAchievement(candidate_profile_id=candidate_id, achievement_type="хакатон", level="победитель", achieved_at=date(2026, 5, 1), score=35.0))
    db.commit()
    db.close()

    pvn_cards = client.get(
        f"/employer/categories/{category['id']}/cards",
        params={"has_pvn": True},
        headers=auth(employer_token),
    )
    assert pvn_cards.status_code == 200
    assert len(pvn_cards.json()) == 1
    assert pvn_cards.json()[0]["has_pvn_history"] is True

    hidden = client.put("/candidates/me/visibility", json={"is_visible": False}, headers=auth(candidate_token))
    assert hidden.status_code == 200
    empty_cards = client.get(
        f"/employer/categories/{category['id']}/cards",
        params={"has_pvn": True},
        headers=auth(employer_token),
    )
    assert empty_cards.json() == []
    visible = client.put("/candidates/me/visibility", json={"is_visible": True}, headers=auth(candidate_token))
    assert visible.json()["is_visible"] is True


def test_task_pool_used_before_generation(client):
    from backend.db import SessionLocal
    from backend.models import Concept, Task, TaskContext
    from scripts.concept_bank import CONCEPTS, CONTEXT_LABELS

    db = SessionLocal()
    seed_concept_bank(db)
    junior_concepts = db.query(Concept).filter(Concept.grade == "junior").order_by(Concept.id).limit(5).all()
    pool_ids = []
    for concept in junior_concepts:
        pool_task = Task(
            concept_id=concept.id,
            grade="junior",
            statement=f"Пул-задача {concept.name}",
            task_format="multiple_choice",
            options=["a", "b", "c", "d"],
            reference_answer=0,
        )
        db.add(pool_task)
        db.flush()
        pool_ids.append(pool_task.id)
    db.commit()

    first_token = register_and_login(client, "cand7@example.com", "candidate")
    session = client.post("/test-sessions", json={"grade": "junior"}, headers=auth(first_token))
    tasks = session.json()["tasks"]
    task_ids = {t["id"] for t in tasks}
    assert set(pool_ids).issubset(task_ids)
    assert len(tasks) == get_settings().tasks_per_session
    pool_in_session = [t for t in tasks if t["id"] in set(pool_ids)]
    assert len(pool_in_session) == len(pool_ids)
    generated_in_session = [t for t in tasks if t["id"] not in set(pool_ids)]
    assert len(generated_in_session) == len(tasks) - len(pool_ids)

    second_token = register_and_login(client, "cand8@example.com", "candidate")
    second = client.post("/test-sessions", json={"grade": "junior"}, headers=auth(second_token))
    second_ids = {t["id"] for t in second.json()["tasks"]}
    assert second_ids.isdisjoint(task_ids)
    db.close()


def test_employer_search_by_semantic_query_finds_postgres(client):
    db_token = register_and_login(client, "sem-db@example.com", "candidate")
    client.put(
        "/candidates/me",
        json={"full_name": "Базы Данных", "contacts": {"email": "db@example.com"}, "stack": ["python", "postgresql", "sql"], "specialization": "backend"},
        headers=auth(db_token),
    )
    client.put("/candidates/me/grade", json={"grade": "middle"}, headers=auth(db_token))
    ui_token = register_and_login(client, "sem-ui@example.com", "candidate")
    client.put(
        "/candidates/me",
        json={"full_name": "РРЅС‚РµСЂС„РµР№сы", "contacts": {"email": "ui@example.com"}, "stack": ["react", "css"], "specialization": "frontend"},
        headers=auth(ui_token),
    )
    client.put("/candidates/me/grade", json={"grade": "middle"}, headers=auth(ui_token))

    employer_token = register_and_login(client, "sem-emp@example.com", "employer")
    from backend.db import SessionLocal
    from backend.models import CandidateProfile

    db = SessionLocal()
    db_candidate_id = db.query(CandidateProfile).filter(CandidateProfile.full_name == "Базы Данных").one().id
    ui_candidate_id = db.query(CandidateProfile).filter(CandidateProfile.full_name == "РРЅС‚РµСЂС„РµР№сы").one().id
    db.close()

    for query in ["база данных", "хранилище данных", "субд", "postgres"]:
        found = client.get("/employer/search", params={"q": query}, headers=auth(employer_token))
        assert found.status_code == 200, query
        ids = [card["candidate_profile_id"] for card in found.json()]
        assert db_candidate_id in ids, f"кандидат с Postgres не РЅР°Р№ден по «{query}»"

    ui_results = client.get("/employer/search", params={"q": "фронтенд верстка"}, headers=auth(employer_token))
    assert ui_results.status_code == 200
    ui_ids = [card["candidate_profile_id"] for card in ui_results.json()]
    assert ui_candidate_id in ui_ids
    assert db_candidate_id not in ui_ids


def test_employer_domains_list_and_create(client):
    token = register_and_login(client, "dom-emp@example.com", "employer")
    seeded = client.get("/employer/domains", params={"q": "база данных"}, headers=auth(token))
    assert seeded.status_code == 200
    titles = [item["title"] for item in seeded.json()["items"]]
    assert any("Базы данных" in title for title in titles)
    assert seeded.json()["items"][0]["score"] > 0.5

    created = client.post("/employer/domains", json={"title": "Квантовые вычисления", "aliases": ["quantum"]}, headers=auth(token))
    assert created.status_code == 201
    assert created.json()["slug"] == "квантовые-вычисления"[:64] or created.json()["title"] == "Квантовые вычисления"
    repeated = client.post("/employer/domains", json={"title": "квантовые вычисления"}, headers=auth(token))
    assert repeated.status_code == 201
    assert repeated.json()["id"] == created.json()["id"]


def test_employer_search(client):
    candidate_token = register_and_login(client, "cand11@example.com", "candidate")
    client.put(
        "/candidates/me",
        json={
            "full_name": "Поиск Кандидатов",
            "contacts": {"email": "s@example.com"},
            "stack": ["python", "django"],
            "years_of_experience": 1,
            "soft_skills": ["коммуникация"],
            "specialization": "backend",
        },
        headers=auth(candidate_token),
    )
    client.put("/candidates/me/grade", json={"grade": "junior"}, headers=auth(candidate_token))
    frontend_token = register_and_login(client, "cand12@example.com", "candidate")
    client.put(
        "/candidates/me",
        json={"specialization": "frontend", "stack": ["react"]},
        headers=auth(frontend_token),
    )
    client.put("/candidates/me/grade", json={"grade": "middle"}, headers=auth(frontend_token))

    employer_token = register_and_login(client, "emp11@example.com", "employer")
    search = client.get("/employer/search", params={"specialization": "backend"}, headers=auth(employer_token))
    assert search.status_code == 200
    results = search.json()
    assert all(card["specialization"] == "backend" for card in results)

    filtered = client.get(
        "/employer/search",
        params={"specialization": "backend", "stack": ["python", "postgresql"]},
        headers=auth(employer_token),
    ).json()
    assert filtered[0]["match_relevance"] == 0.5
    assert all(card["specialization"] == "backend" for card in filtered)

    both = client.get("/employer/search", headers=auth(employer_token)).json()
    assert len(both) == 2
    assert both == sorted(both, key=lambda card: card["final_score"], reverse=True)


def test_resume_rejects_invalid_pdf(client):
    candidate_token = register_and_login(client, "cand13@example.com", "candidate")
    response = client.post(
        "/candidates/me/resume",
        files={"file": ("resume.pdf", b"not a pdf at all", "application/pdf")},
        headers=auth(candidate_token),
    )
    assert response.status_code == 400


def test_grade_cooldown_blocks_immediate_change(client):
    from backend.db import SessionLocal
    from backend.models import CandidateProfile
    from backend.core.categorization import assign_category

    candidate_token = register_and_login(client, "cand14@example.com", "candidate")
    client.put("/candidates/me", json={"specialization": "backend"}, headers=auth(candidate_token))

    db = SessionLocal()
    profile = db.query(CandidateProfile).filter(CandidateProfile.user_id.isnot(None)).order_by(CandidateProfile.id.desc()).first()
    profile.grade = "senior"
    assign_category(db, profile, "backend", "senior")
    db.commit()
    db.close()

    first = client.put("/candidates/me/grade", json={"grade": "middle"}, headers=auth(candidate_token))
    assert first.status_code == 200
    second = client.put("/candidates/me/grade", json={"grade": "junior"}, headers=auth(candidate_token))
    assert second.status_code == 409
    profile = client.get("/candidates/me", headers=auth(candidate_token)).json()
    assert profile["grade"] == "middle"


def test_category_counts_only_visible_candidates(client):
    from backend.db import SessionLocal
    from backend.models import CandidateProfile
    from backend.core.categorization import assign_category

    employer_token = register_and_login(client, "emp12@example.com", "employer")

    visible_token = register_and_login(client, "cand15@example.com", "candidate")
    client.put("/candidates/me", json={"specialization": "backend"}, headers=auth(visible_token))
    hidden_token = register_and_login(client, "cand16@example.com", "candidate")
    client.put("/candidates/me", json={"specialization": "backend"}, headers=auth(hidden_token))

    db = SessionLocal()
    for profile in db.query(CandidateProfile).filter(CandidateProfile.specialization == "backend").all():
        if profile.grade is None:
            profile.grade = "junior"
            assign_category(db, profile, "backend", "junior")
    db.commit()
    db.close()

    client.put("/candidates/me/visibility", json={"is_visible": False}, headers=auth(hidden_token))

    categories = client.get("/employer/categories", headers=auth(employer_token)).json()["items"]
    backend_junior = next(c for c in categories if c["specialization"] == "backend" and c["grade"] == "junior")
    assert backend_junior["candidate_count"] == 1


def test_vacancy_and_application_flow(client):
    candidate_token = register_and_login(client, "cand2@example.com", "candidate")
    employer_token = register_and_login(client, "emp2@example.com", "employer")

    vacancy = client.post(
        "/vacancies",
        json={
            "title": "Backend разработчик",
            "stack": ["python"],
            "specialization": "backend",
            "grade": "middle",
            "salary_from": 200000,
            "salary_to": 300000,
        },
        headers=auth(employer_token),
    )
    assert vacancy.status_code == 201
    vacancy_id = vacancy.json()["id"]

    application = client.post(
        "/applications",
        json={"vacancy_id": vacancy_id, "message": "Отклик"},
        headers=auth(candidate_token),
    )
    assert application.status_code == 201
    duplicate = client.post(
        "/applications",
        json={"vacancy_id": vacancy_id, "message": "Повтор"},
        headers=auth(candidate_token),
    )
    assert duplicate.status_code == 409

    mine = client.get("/applications/my", headers=auth(candidate_token))
    assert mine.status_code == 200
    my_row = next(item for item in mine.json() if item["id"] == application.json()["id"])
    assert my_row["vacancy_title"] == vacancy.json()["title"]

    updated = client.put(
        f"/applications/{application.json()['id']}/status",
        json={"status": "viewed"},
        headers=auth(employer_token),
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "viewed"


def test_interview_scheduling_persists_and_requires_accepted(client):
    candidate_token = register_and_login(client, "cand-int@example.com", "candidate")
    employer_token = register_and_login(client, "emp-int@example.com", "employer")

    vacancy = client.post(
        "/vacancies",
        json={
            "title": "Backend разработчик",
            "stack": ["python"],
            "specialization": "backend",
            "grade": "middle",
            "salary_from": 200000,
            "salary_to": 300000,
        },
        headers=auth(employer_token),
    )
    assert vacancy.status_code == 201
    application = client.post(
        "/applications",
        json={"vacancy_id": vacancy.json()["id"], "message": "Отклик"},
        headers=auth(candidate_token),
    )
    assert application.status_code == 201
    application_id = application.json()["id"]

    schedule = {
        "scheduled_at": "2030-01-15T10:00:00Z",
        "duration_minutes": 90,
        "format": "video",
        "link": "https://meet.example.com/room",
    }

    rejected = client.put(
        f"/applications/{application_id}/interview",
        json=schedule,
        headers=auth(employer_token),
    )
    assert rejected.status_code == 409

    assert client.put(
        f"/applications/{application_id}/status",
        json={"status": "accepted"},
        headers=auth(employer_token),
    ).status_code == 200

    missing_link = client.put(
        f"/applications/{application_id}/interview",
        json={**schedule, "link": ""},
        headers=auth(employer_token),
    )
    assert missing_link.status_code == 422

    past = client.put(
        f"/applications/{application_id}/interview",
        json={**schedule, "scheduled_at": "2000-01-15T10:00:00Z"},
        headers=auth(employer_token),
    )
    assert past.status_code == 422

    scheduled = client.put(
        f"/applications/{application_id}/interview",
        json=schedule,
        headers=auth(employer_token),
    )
    assert scheduled.status_code == 200
    body = scheduled.json()
    assert body["interview_duration"] == 90
    assert body["interview_format"] == "video"
    assert body["interview_link"] == "https://meet.example.com/room"
    assert body["interview_at"] is not None

    incoming = client.get("/applications/incoming", headers=auth(employer_token)).json()
    assert incoming[0]["interview_format"] == "video"

    other = register_and_login(client, "emp-int-other@example.com", "employer")
    forbidden = client.put(
        f"/applications/{application_id}/interview",
        json=schedule,
        headers=auth(other),
    )
    assert forbidden.status_code == 404


def seed_concept_bank(db) -> None:
    from backend.models import Concept, TaskContext
    from scripts.concept_bank import CONCEPTS, CONTEXT_LABELS

    for entry in CONCEPTS:
        db.add(
            Concept(
                name=entry["name"],
                domain=entry["domain"],
                grade=entry["grade"],
                difficulty_params=entry["params"],
                task_format=entry.get("format", "design_choice" if entry["domain"] == "design" else "multiple_choice"),
                question_template=entry["question"],
                correct_answer=entry["correct"],
                distractors=entry["distractors"],
            )
        )
    for label in CONTEXT_LABELS:
        db.add(TaskContext(label=label))
    db.commit()


def test_test_session_flow(client):
    from backend.db import SessionLocal

    db = SessionLocal()
    seed_concept_bank(db)
    db.close()
    candidate_token = register_and_login(client, "cand3@example.com", "candidate")
    session = client.post("/test-sessions", json={"grade": "junior"}, headers=auth(candidate_token))
    assert session.status_code == 201
    assert session.json()["grade"] == "junior"
    assert client.get("/test-sessions", headers=auth(candidate_token)).status_code == 200


def test_test_session_with_concept_bank(client):
    from backend.db import SessionLocal
    from backend.models import Task

    db = SessionLocal()
    seed_concept_bank(db)

    candidate_token = register_and_login(client, "cand4@example.com", "candidate")
    session = client.post("/test-sessions", json={"grade": "junior"}, headers=auth(candidate_token))
    assert session.status_code == 201
    tasks = session.json()["tasks"]
    assert len(tasks) == get_settings().tasks_per_session
    assert all(len(task["options"]) == 4 for task in tasks)

    db_tasks = db.query(Task).filter(Task.session_id == session.json()["id"]).all()
    submissions = [
        {"task_id": task.id, "option_index": task.reference_answer}
        for task in db_tasks
    ]
    result = client.post(
        f"/test-sessions/{session.json()['id']}/answers",
        json=submissions,
        headers=auth(candidate_token),
    )
    assert result.status_code == 200
    body = result.json()
    assert body["task_count"] == get_settings().tasks_per_session
    assert body["correct_count"] == get_settings().tasks_per_session
    assert body["result_score"] == 100
    assert body["verdict"] == "suggest_higher"
    assert body["suggested_grade"] == "middle"
    db.close()


def test_completed_session_review_is_available(client):
    from backend.db import SessionLocal
    from backend.models import Task

    db = SessionLocal()
    seed_concept_bank(db)

    candidate_token = register_and_login(client, "cand-review@example.com", "candidate")
    session = client.post("/test-sessions", json={"grade": "junior"}, headers=auth(candidate_token)).json()
    db_tasks = db.query(Task).filter(Task.session_id == session["id"]).all()
    submissions = [{"task_id": task.id, "option_index": task.reference_answer} for task in db_tasks]
    submitted = client.post(
        f"/test-sessions/{session['id']}/answers",
        json=submissions,
        headers=auth(candidate_token),
    )
    assert submitted.status_code == 200

    review = client.get(f"/test-sessions/{session['id']}/review", headers=auth(candidate_token))
    assert review.status_code == 200
    body = review.json()
    assert body["result_score"] == 100
    assert len(body["review"]) == len(db_tasks)
    assert all(item["is_correct"] for item in body["review"])
    assert all(item["selected_index"] == item["reference_answer"] for item in body["review"])
    first = body["review"][0]
    db_task = db.get(Task, first["task_id"])
    assert first["selected_index"] == db_task.reference_answer
    db.close()


def test_review_unavailable_for_pending_session(client):
    from backend.db import SessionLocal

    db = SessionLocal()
    seed_concept_bank(db)

    candidate_token = register_and_login(client, "cand-review-pending@example.com", "candidate")
    session = client.post("/test-sessions", json={"grade": "junior"}, headers=auth(candidate_token)).json()
    review = client.get(f"/test-sessions/{session['id']}/review", headers=auth(candidate_token))
    assert review.status_code == 409
    db.close()


def test_test_session_unique_formulations(client):
    from backend.db import SessionLocal

    db = SessionLocal()
    seed_concept_bank(db)

    first_token = register_and_login(client, "cand5@example.com", "candidate")
    second_token = register_and_login(client, "cand6@example.com", "candidate")
    first = client.post("/test-sessions", json={"grade": "junior"}, headers=auth(first_token)).json()
    second = client.post("/test-sessions", json={"grade": "junior"}, headers=auth(second_token)).json()
    first_statements = {t["statement"] for t in first["tasks"]}
    second_statements = {t["statement"] for t in second["tasks"]}
    shared = first_statements & second_statements
    assert len(first_statements) == len(first["tasks"])
    assert len(shared) == 0
    db.close()


def test_grade_change_requires_test_for_promotion(client):
    from backend.db import SessionLocal
    from backend.models import CandidateProfile, Task, Concept
    from backend.core.categorization import assign_category

    token = register_and_login(client, "candgrade@example.com", "candidate")
    client.put(
        "/candidates/me",
        json={"full_name": "Р“СЂРµР№д Тестов", "stack": ["python"], "specialization": "backend"},
        headers=auth(token),
    )

    db = SessionLocal()
    profile = db.query(CandidateProfile).filter(CandidateProfile.full_name == "Р“СЂРµР№д Тестов").first()
    profile.grade = "junior"
    assign_category(db, profile, "backend", "junior")
    for number in range(5):
        db.add(Concept(name=f"grade-proof-{number}", domain="backend", grade="middle",
                       question_template="Choose correct value", correct_answer="correct", distractors=["incorrect"]))
    db.commit()
    db.close()

    promote = client.put("/candidates/me/grade", json={"grade": "senior"}, headers=auth(token))
    assert promote.status_code == 409
    assert client.get("/candidates/me", headers=auth(token)).json()["grade"] == "junior"

    demote = client.put("/candidates/me/grade", json={"grade": "junior"}, headers=auth(token))
    assert demote.status_code == 200

    session = client.post("/test-sessions", json={"grade": "middle"}, headers=auth(token)).json()
    db = SessionLocal()
    references = {t["id"]: db.get(Task, t["id"]).reference_answer for t in session["tasks"]}
    db.close()
    submissions = [
        {"task_id": t["id"], "option_index": references[t["id"]] if isinstance(references[t["id"]], int) else 0}
        for t in session["tasks"]
    ]
    result = client.post(
        f"/test-sessions/{session['id']}/answers",
        json=submissions,
        headers=auth(token),
    )
    assert result.status_code == 200
    assert result.json()["grade_applied"] is True
    assert client.get("/candidates/me", headers=auth(token)).json()["grade"] == "middle"


def test_employer_profile_saves_offices_and_logo(client):
    token = register_and_login(client, "office-emp@example.com", "employer")
    tiny_png = "data:image/png;base64,iVBORw0KGgo="
    response = client.put(
        "/employers/me",
        json={
            "company_name": "ООО Офисы",
            "description": "",
            "contacts": {},
            "offices": [
                {"title": "Р“РѕР»РѕРІРЅРѕР№", "city": "Москва", "address": "ул. Первая, 1", "is_default": False},
                {"title": "Филиал", "city": "Казань", "address": "ул. Вторая, 2", "is_default": True},
            ],
            "logo_data_url": tiny_png,
        },
        headers=auth(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert [office["city"] for office in body["offices"]] == ["Москва", "Казань"]
    assert [office["is_default"] for office in body["offices"]] == [False, True]
    assert body["logo_data_url"] == tiny_png

    without_offices = client.put(
        "/employers/me",
        json={"company_name": "ООО Офисы", "description": "", "contacts": {}},
        headers=auth(token),
    ).json()
    assert len(without_offices["offices"]) == 2
    assert without_offices["logo_data_url"] == tiny_png

    cleared = client.put(
        "/employers/me",
        json={"company_name": "ООО Офисы", "description": "", "contacts": {}, "offices": [], "logo_data_url": ""},
        headers=auth(token),
    ).json()
    assert cleared["offices"] == []
    assert cleared["logo_data_url"] is None


def test_employer_logo_crop_is_saved_and_reset_with_logo(client):
    token = register_and_login(client, "crop-emp@example.com", "employer")
    png = "data:image/png;base64,iVBORw0KGgo="
    saved = client.put(
        "/employers/me",
        json={"company_name": "ООО Кроп", "description": "", "contacts": {}, "logo_data_url": png, "logo_zoom": 2.0, "logo_offset_x": 10, "logo_offset_y": -5},
        headers=auth(token),
    ).json()
    assert saved["logo_zoom"] == 2.0
    assert saved["logo_offset_x"] == 10
    assert saved["logo_offset_y"] == -5

    out_of_range = client.put(
        "/employers/me",
        json={"company_name": "ООО Кроп", "description": "", "contacts": {}, "logo_zoom": 5},
        headers=auth(token),
    )
    assert out_of_range.status_code == 422

    removed = client.put(
        "/employers/me",
        json={"company_name": "ООО Кроп", "description": "", "contacts": {}, "logo_data_url": ""},
        headers=auth(token),
    ).json()
    assert removed["logo_data_url"] is None
    assert removed["logo_zoom"] == 1.0
    assert removed["logo_offset_x"] == 0.0


def test_employer_profile_first_office_becomes_default_when_none_marked(client):
    token = register_and_login(client, "office-default@example.com", "employer")
    body = client.put(
        "/employers/me",
        json={
            "company_name": "ООО Дефолт",
            "description": "",
            "contacts": {},
            "offices": [
                {"title": "А", "city": "Самара", "address": "ул. А, 1", "is_default": False},
                {"title": "Б", "city": "Пермь", "address": "ул. Б, 2", "is_default": False},
            ],
        },
        headers=auth(token),
    ).json()
    assert [office["is_default"] for office in body["offices"]] == [True, False]


def test_employer_profile_rejects_bad_logo(client):
    import base64

    token = register_and_login(client, "logo-bad@example.com", "employer")
    svg = "data:image/svg+xml;base64," + base64.b64encode(b"<svg/>").decode()
    wrong_mime = client.put(
        "/employers/me",
        json={"company_name": "X", "description": "", "contacts": {}, "logo_data_url": svg},
        headers=auth(token),
    )
    assert wrong_mime.status_code == 422

    big = "data:image/png;base64," + base64.b64encode(b"\x00" * (512 * 1024 + 1)).decode()
    too_big = client.put(
        "/employers/me",
        json={"company_name": "X", "description": "", "contacts": {}, "logo_data_url": big},
        headers=auth(token),
    )
    assert too_big.status_code == 422


def create_invitation_for_candidate(client, employer_token, candidate_token, suffix: str) -> dict:
    client.put(
        "/candidates/me",
        json={
            "full_name": f"Отзыв {suffix}",
            "contacts": {"email": f"w{suffix}@example.com"},
            "stack": ["python"],
            "specialization": "backend",
        },
        headers=auth(candidate_token),
    )
    from backend.db import SessionLocal
    from backend.models import CandidateProfile
    from backend.core.categorization import assign_category

    db = SessionLocal()
    profile = db.query(CandidateProfile).filter(CandidateProfile.full_name == f"Отзыв {suffix}").first()
    profile.grade = "junior"
    assign_category(db, profile, "backend", "junior")
    candidate_id = profile.id
    db.commit()
    db.close()
    response = client.post(
        "/invitations",
        json={
            "candidate_profile_id": candidate_id,
            "message": "Рсходное сообщение",
            "salary_from": 100000,
            "salary_to": 150000,
            "company_name": "ООО Отзыв",
            "contact_method": "hr@example.com",
        },
        headers=auth(employer_token),
    )
    assert response.status_code == 201
    return response.json()


INVITATION_EDIT_PAYLOAD = {
    "message": "Новое сообщение",
    "salary_from": 120000,
    "salary_to": 170000,
    "company_name": "ООО Отзыв 2",
    "contact_method": "hr2@example.com",
}


def test_employer_edits_sent_invitation_and_withdraws_it(client):
    candidate_token = register_and_login(client, "wd-cand@example.com", "candidate")
    employer_token = register_and_login(client, "wd-emp@example.com", "employer")
    invitation = create_invitation_for_candidate(client, employer_token, candidate_token, "a")

    edited = client.patch(f"/invitations/{invitation['id']}", json=INVITATION_EDIT_PAYLOAD, headers=auth(employer_token))
    assert edited.status_code == 200
    assert edited.json()["message"] == "Новое сообщение"
    assert edited.json()["salary_from"] == 120000
    assert edited.json()["status"] == "sent"

    withdrawn = client.post(f"/invitations/{invitation['id']}/withdraw", headers=auth(employer_token))
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "withdrawn"

    assert client.post(f"/invitations/{invitation['id']}/withdraw", headers=auth(employer_token)).status_code == 409
    assert client.patch(f"/invitations/{invitation['id']}", json=INVITATION_EDIT_PAYLOAD, headers=auth(employer_token)).status_code == 409
    assert client.post(f"/invitations/{invitation['id']}/accept", headers=auth(candidate_token)).status_code == 409


def test_viewed_invitation_cannot_be_edited_but_can_be_withdrawn(client):
    candidate_token = register_and_login(client, "wv-cand@example.com", "candidate")
    employer_token = register_and_login(client, "wv-emp@example.com", "employer")
    invitation = create_invitation_for_candidate(client, employer_token, candidate_token, "b")

    assert client.post(f"/invitations/{invitation['id']}/view", headers=auth(candidate_token)).status_code == 200
    assert client.patch(f"/invitations/{invitation['id']}", json=INVITATION_EDIT_PAYLOAD, headers=auth(employer_token)).status_code == 409

    withdrawn = client.post(f"/invitations/{invitation['id']}/withdraw", headers=auth(employer_token))
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "withdrawn"

