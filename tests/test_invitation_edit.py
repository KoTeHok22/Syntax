from pathlib import Path

from tests.test_api import auth, register_and_login
from tests.test_invitation_contacts import (
    CANDIDATE_CONTACTS,
    EMPLOYER_CONTACT,
    find,
    invite_one_candidate,
)

FRONTEND_PAGE = (
    Path(__file__).resolve().parents[1]
    / "frontend"
    / "src"
    / "pages"
    / "employer"
    / "EmployerInvitationsPage.tsx"
)


def test_employer_sees_contact_method_in_sent_viewed_and_accepted(client):
    employer_token, candidate_token, invitation = invite_one_candidate(client)

    sent = client.get("/invitations/sent", headers=auth(employer_token)).json()
    assert find(sent, invitation["id"])["status"] == "sent"
    assert find(sent, invitation["id"])["contact_method"] == EMPLOYER_CONTACT

    viewed = client.post(f"/invitations/{invitation['id']}/view", headers=auth(candidate_token))
    assert viewed.status_code == 200
    viewed_sent = client.get("/invitations/sent", headers=auth(employer_token)).json()
    assert find(viewed_sent, invitation["id"])["status"] == "viewed"
    assert find(viewed_sent, invitation["id"])["contact_method"] == EMPLOYER_CONTACT

    accepted = client.post(f"/invitations/{invitation['id']}/accept", headers=auth(candidate_token))
    assert accepted.status_code == 200
    accepted_sent = client.get("/invitations/sent", headers=auth(employer_token)).json()
    assert find(accepted_sent, invitation["id"])["status"] == "accepted"
    assert find(accepted_sent, invitation["id"])["contact_method"] == EMPLOYER_CONTACT


def test_employer_sees_contact_method_on_create_response(client):
    employer_token, candidate_token, invitation = invite_one_candidate(client)
    assert invitation["contact_method"] == EMPLOYER_CONTACT
    assert invitation["candidate_contacts"] is None


def test_candidate_sees_contact_method_only_after_accept(client):
    _, candidate_token, invitation = invite_one_candidate(client)

    before = find(client.get("/invitations/incoming", headers=auth(candidate_token)).json(), invitation["id"])
    assert before["status"] == "sent"
    assert before["contact_method"] is None

    client.post(f"/invitations/{invitation['id']}/view", headers=auth(candidate_token))
    viewed = find(client.get("/invitations/incoming", headers=auth(candidate_token)).json(), invitation["id"])
    assert viewed["status"] == "viewed"
    assert viewed["contact_method"] is None

    accepted = client.post(f"/invitations/{invitation['id']}/accept", headers=auth(candidate_token))
    assert accepted.status_code == 200
    assert accepted.json()["contact_method"] == EMPLOYER_CONTACT
    after = find(client.get("/invitations/incoming", headers=auth(candidate_token)).json(), invitation["id"])
    assert after["contact_method"] == EMPLOYER_CONTACT
    assert after["candidate_contacts"] is None


def test_candidate_never_sees_own_contacts_and_employer_sees_them_after_accept(client):
    employer_token, candidate_token, invitation = invite_one_candidate(client)
    client.post(f"/invitations/{invitation['id']}/view", headers=auth(candidate_token))
    client.post(f"/invitations/{invitation['id']}/accept", headers=auth(candidate_token))

    incoming = find(client.get("/invitations/incoming", headers=auth(candidate_token)).json(), invitation["id"])
    assert incoming["contact_method"] == EMPLOYER_CONTACT
    assert incoming["candidate_contacts"] is None

    sent = find(client.get("/invitations/sent", headers=auth(employer_token)).json(), invitation["id"])
    assert sent["candidate_contacts"] == CANDIDATE_CONTACTS
    assert sent["contact_method"] == EMPLOYER_CONTACT


def test_withdraw_from_viewed_succeeds_and_blocks_editing(client):
    employer_token, candidate_token, invitation = invite_one_candidate(client)
    assert client.post(f"/invitations/{invitation['id']}/view", headers=auth(candidate_token)).status_code == 200

    withdrawn = client.post(f"/invitations/{invitation['id']}/withdraw", headers=auth(employer_token))
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "withdrawn"

    repeated = client.post(f"/invitations/{invitation['id']}/withdraw", headers=auth(employer_token))
    assert repeated.status_code == 409


def test_editing_stays_available_in_sent_and_blocked_in_viewed(client):
    employer_token, candidate_token, invitation = invite_one_candidate(client)
    payload = {
        "message": "Обновлённое сообщение",
        "salary_from": 120000,
        "salary_to": 170000,
        "company_name": "ООО Обновлено",
        "contact_method": EMPLOYER_CONTACT,
    }

    edited = client.patch(f"/invitations/{invitation['id']}", json=payload, headers=auth(employer_token))
    assert edited.status_code == 200
    assert edited.json()["status"] == "sent"
    assert edited.json()["contact_method"] == EMPLOYER_CONTACT

    client.post(f"/invitations/{invitation['id']}/view", headers=auth(candidate_token))
    viewed_edit = client.patch(f"/invitations/{invitation['id']}", json=payload, headers=auth(employer_token))
    assert viewed_edit.status_code == 409


def test_actions_are_available_for_viewed_and_hidden_after_response():
    source = FRONTEND_PAGE.read_text(encoding="utf-8")

    actions_gate = "invitation.status === 'sent' || invitation.status === 'viewed'"
    assert actions_gate in source

    edit_gate = "invitation.status === 'sent' ? ("
    assert edit_gate in source

    assert "invitation.status !== 'rejected' && invitation.status !== 'withdrawn'" in source
