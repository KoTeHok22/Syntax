from tests.test_api import auth, register_and_login
from tests.conftest import seed_grade


def invite_one_candidate(client):
    employer_token = register_and_login(client, "tl-emp@example.com", "employer")
    candidate_token = register_and_login(client, "tl-cand@example.com", "candidate")
    client.put(
        "/candidates/me",
        json={"full_name": "Timeline", "contacts": {"telegram": "@timeline"}, "stack": ["python"], "years_of_experience": 1, "soft_skills": [], "specialization": "backend"},
        headers=auth(candidate_token),
    )
    client.put("/candidates/me/visibility", json={"is_visible": True}, headers=auth(candidate_token))
    seed_grade("tl-cand@example.com", "junior", "backend")

    categories = client.get("/employer/categories", headers=auth(employer_token)).json()["items"]
    category_id = next(c for c in categories if c["specialization"] == "backend")["id"]
    card = client.get(f"/employer/categories/{category_id}/cards", headers=auth(employer_token)).json()[0]

    invitation = client.post(
        "/invitations",
        json={
            "candidate_profile_id": card["candidate_profile_id"],
            "message": "Приглашение в команду",
            "salary_from": 100000,
            "salary_to": 150000,
            "company_name": "ООО Пример",
            "contact_method": "hr@example.com",
        },
        headers=auth(employer_token),
    )
    assert invitation.status_code == 201, invitation.text
    return employer_token, candidate_token, invitation.json()


def test_invitation_timeline_records_real_transition_timestamps(client):
    _, candidate_token, invitation = invite_one_candidate(client)
    body = invitation
    assert body["created_at"] is not None
    assert body["viewed_at"] is None
    assert body["responded_at"] is None

    viewed = client.post(f"/invitations/{body['id']}/view", headers=auth(candidate_token))
    assert viewed.status_code == 200
    assert viewed.json()["status"] == "viewed"
    assert viewed.json()["viewed_at"] is not None
    assert viewed.json()["responded_at"] is None

    accepted = client.post(f"/invitations/{body['id']}/accept", headers=auth(candidate_token))
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    assert accepted.json()["responded_at"] is not None
    assert accepted.json()["viewed_at"] is not None


def test_accept_requires_prior_view(client):
    _, candidate_token, invitation = invite_one_candidate(client)
    direct = client.post(f"/invitations/{invitation['id']}/accept", headers=auth(candidate_token))
    assert direct.status_code == 409

    client.post(f"/invitations/{invitation['id']}/view", headers=auth(candidate_token))
    accepted = client.post(f"/invitations/{invitation['id']}/accept", headers=auth(candidate_token))
    assert accepted.status_code == 200
    assert accepted.json()["viewed_at"] is not None
    assert accepted.json()["responded_at"] is not None


def test_reject_records_responded_at(client):
    _, candidate_token, invitation = invite_one_candidate(client)
    rejected = client.post(f"/invitations/{invitation['id']}/reject", headers=auth(candidate_token))
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["responded_at"] is not None


def test_contacts_open_only_after_accept(client):
    employer_token, candidate_token, invitation = invite_one_candidate(client)
    sent_list = client.get("/invitations/sent", headers=auth(employer_token)).json()
    sent_item = next(item for item in sent_list if item["id"] == invitation["id"])
    assert sent_item["status"] == "sent"
    assert sent_item["candidate_contacts"] is None

    incoming = client.get("/invitations/incoming", headers=auth(candidate_token)).json()
    own = next(item for item in incoming if item["id"] == invitation["id"])
    assert own["candidate_contacts"] == {"telegram": "@timeline"}

    client.post(f"/invitations/{invitation['id']}/view", headers=auth(candidate_token))
    client.post(f"/invitations/{invitation['id']}/accept", headers=auth(candidate_token))
    accepted_list = client.get("/invitations/sent", headers=auth(employer_token)).json()
    accepted_item = next(item for item in accepted_list if item["id"] == invitation["id"])
    assert accepted_item["candidate_contacts"] == {"telegram": "@timeline"}
