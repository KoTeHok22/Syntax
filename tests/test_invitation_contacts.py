from tests.test_api import auth, register_and_login
from tests.conftest import seed_grade

EMPLOYER_CONTACT = "hr@example.com"
CANDIDATE_CONTACTS = {"telegram": "@cand-contact"}


def invite_one_candidate(client):
    employer_token = register_and_login(client, "ic-emp@example.com", "employer")
    candidate_token = register_and_login(client, "ic-cand@example.com", "candidate")
    client.put(
        "/candidates/me",
        json={
            "full_name": "Contacts",
            "contacts": CANDIDATE_CONTACTS,
            "stack": ["python"],
            "years_of_experience": 1,
            "soft_skills": [],
            "specialization": "backend",
        },
        headers=auth(candidate_token),
    )
    client.put("/candidates/me/visibility", json={"is_visible": True}, headers=auth(candidate_token))
    seed_grade("ic-cand@example.com", "junior", "backend")

    categories = client.get("/employer/categories", headers=auth(employer_token)).json()["items"]
    category_id = next(c for c in categories if c["specialization"] == "backend")["id"]
    card = client.get(f"/employer/categories/{category_id}/cards", headers=auth(employer_token)).json()[0]

    created = client.post(
        "/invitations",
        json={
            "candidate_profile_id": card["candidate_profile_id"],
            "message": "Приглашение в команду",
            "salary_from": 100000,
            "salary_to": 150000,
            "company_name": "ООО Пример",
            "contact_method": EMPLOYER_CONTACT,
        },
        headers=auth(employer_token),
    )
    assert created.status_code == 201, created.text
    return employer_token, candidate_token, created.json()


def find(items, invitation_id):
    return next(item for item in items if item["id"] == invitation_id)


def test_candidate_before_accept_gets_no_contacts(client):
    _, candidate_token, invitation = invite_one_candidate(client)
    incoming = client.get("/invitations/incoming", headers=auth(candidate_token)).json()
    own = find(incoming, invitation["id"])
    assert own["contact_method"] is None
    assert own["candidate_contacts"] is None


def test_candidate_after_accept_sees_employer_contact_only(client):
    _, candidate_token, invitation = invite_one_candidate(client)
    client.post(f"/invitations/{invitation['id']}/view", headers=auth(candidate_token))
    accepted = client.post(f"/invitations/{invitation['id']}/accept", headers=auth(candidate_token))
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["status"] == "accepted"
    assert body["contact_method"] == EMPLOYER_CONTACT
    assert body["candidate_contacts"] is None


def test_employer_before_accept_gets_no_candidate_contacts(client):
    employer_token, candidate_token, invitation = invite_one_candidate(client)
    sent = client.get("/invitations/sent", headers=auth(employer_token)).json()
    item = find(sent, invitation["id"])
    assert item["status"] == "sent"
    assert item["candidate_contacts"] is None


def test_employer_after_accept_sees_candidate_contacts(client):
    employer_token, candidate_token, invitation = invite_one_candidate(client)
    client.post(f"/invitations/{invitation['id']}/view", headers=auth(candidate_token))
    client.post(f"/invitations/{invitation['id']}/accept", headers=auth(candidate_token))
    sent = client.get("/invitations/sent", headers=auth(employer_token)).json()
    item = find(sent, invitation["id"])
    assert item["status"] == "accepted"
    assert item["candidate_contacts"] == CANDIDATE_CONTACTS
    assert item["contact_method"] == EMPLOYER_CONTACT


def test_candidate_and_employer_never_receive_each_others_duplicate_payload(client):
    employer_token, candidate_token, invitation = invite_one_candidate(client)
    client.post(f"/invitations/{invitation['id']}/view", headers=auth(candidate_token))
    client.post(f"/invitations/{invitation['id']}/accept", headers=auth(candidate_token))

    incoming = client.get("/invitations/incoming", headers=auth(candidate_token)).json()
    candidate_view = find(incoming, invitation["id"])
    assert candidate_view["contact_method"] == EMPLOYER_CONTACT
    assert candidate_view["candidate_contacts"] is None

    sent = client.get("/invitations/sent", headers=auth(employer_token)).json()
    employer_view = find(sent, invitation["id"])
    assert employer_view["candidate_contacts"] == CANDIDATE_CONTACTS
