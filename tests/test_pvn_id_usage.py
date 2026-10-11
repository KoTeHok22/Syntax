from tests.test_api import auth, register_and_login
from tests.conftest import seed_grade


def test_pvn_id_is_optional_and_unique(client):
    first = client.post(
        "/auth/register",
        json={
            "email": "pvn-a@example.com",
            "password": "password123",
            "role": "candidate",
            "consent_accepted": True,
            "pvn_id": "PVN-777001",
        },
    )
    assert first.status_code == 201, first.text

    duplicate = client.post(
        "/auth/register",
        json={
            "email": "pvn-b@example.com",
            "password": "password123",
            "role": "candidate",
            "consent_accepted": True,
            "pvn_id": "PVN-777001",
        },
    )
    assert duplicate.status_code == 409
    assert "ПВН ID" in duplicate.json()["detail"]

    without = client.post(
        "/auth/register",
        json={
            "email": "pvn-c@example.com",
            "password": "password123",
            "role": "candidate",
            "consent_accepted": True,
        },
    )
    assert without.status_code == 201, without.text


def test_pvn_id_flows_to_profile_and_employer_card(client):
    token = register_and_login(client, "pvn-card@example.com", "candidate")
    updated = client.put(
        "/candidates/me",
        json={"full_name": "Тест", "contacts": {}, "stack": ["python"], "years_of_experience": 1, "soft_skills": [], "specialization": "backend", "pvn_id": "PVN-777002"},
        headers=auth(token),
    )
    assert updated.status_code == 200, updated.text
    profile = updated.json()
    assert profile["pvn_id"] == "PVN-777002"
    assert profile["is_pvn_verified"] is True
    client.put("/candidates/me/visibility", json={"is_visible": True}, headers=auth(token))
    seed_grade("pvn-card@example.com", "junior", "backend")

    employer_token = register_and_login(client, "pvn-emp@example.com", "employer")
    categories = client.get("/employer/categories", headers=auth(employer_token)).json()["items"]
    category_id = next(c for c in categories if c["specialization"] == "backend")["id"]

    verified = client.get(
        f"/employer/categories/{category_id}/cards",
        params={"verified_only": "true"},
        headers=auth(employer_token),
    ).json()
    assert any(card["candidate_profile_id"] == profile["id"] and card["is_pvn_verified"] for card in verified)

    unverified = client.get(
        f"/employer/categories/{category_id}/cards",
        params={"verified_only": "false"},
        headers=auth(employer_token),
    ).json()
    assert all(card["is_pvn_verified"] is False for card in unverified)


def test_candidate_can_clear_and_set_pvn_id_after_registration(client):
    token = register_and_login(client, "pvn-edit@example.com", "candidate")

    updated = client.put(
        "/candidates/me",
        json={"full_name": "Тест", "contacts": {}, "stack": [], "years_of_experience": 0, "soft_skills": [], "specialization": "", "pvn_id": "PVN-777003"},
        headers=auth(token),
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["pvn_id"] == "PVN-777003"
    assert updated.json()["is_pvn_verified"] is True

    cleared = client.put(
        "/candidates/me",
        json={"full_name": "Тест", "contacts": {}, "stack": [], "years_of_experience": 0, "soft_skills": [], "specialization": "", "pvn_id": ""},
        headers=auth(token),
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["pvn_id"] is None
    assert cleared.json()["is_pvn_verified"] is False
