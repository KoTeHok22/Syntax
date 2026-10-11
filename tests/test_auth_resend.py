from fastapi.testclient import TestClient


def register_unconfirmed(client: TestClient, email: str) -> None:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "password123", "role": "candidate", "consent_accepted": True},
    )
    assert response.status_code == 201
    assert response.json()["is_email_confirmed"] is False


def test_resend_returns_confirmation_url_for_unconfirmed(client):
    register_unconfirmed(client, "resend-pending@example.com")
    response = client.post("/auth/resend-confirmation", json={"email": "resend-pending@example.com"})
    assert response.status_code == 200
    body = response.json()
    assert body["confirmation_url"] is not None
    assert "resend-pending@example.com" not in body["confirmation_url"]


def test_resend_unknown_email_is_neutral(client):
    register_unconfirmed(client, "resend-known@example.com")
    known = client.post("/auth/resend-confirmation", json={"email": "resend-known@example.com"}).json()
    response = client.post("/auth/resend-confirmation", json={"email": "ghost@example.com"})
    assert response.status_code == 200
    body = response.json()
    assert body["confirmation_url"] is None
    assert body["message"] == known["message"]


def test_resend_confirmed_user_is_neutral(client):
    created = client.post(
        "/auth/register",
        json={"email": "resend-confirmed@example.com", "password": "password123", "role": "candidate", "consent_accepted": True},
    )
    assert created.status_code == 201
    confirmation_url = created.json()["confirmation_url"]
    assert confirmation_url is not None
    assert client.get(confirmation_url).status_code == 200

    response = client.post("/auth/resend-confirmation", json={"email": "resend-confirmed@example.com"})
    assert response.status_code == 200
    assert response.json()["confirmation_url"] is None


def test_resend_unknown_and_confirmed_share_same_message(client):
    register_unconfirmed(client, "resend-shape@example.com")
    pending = client.post("/auth/resend-confirmation", json={"email": "resend-shape@example.com"}).json()
    unknown = client.post("/auth/resend-confirmation", json={"email": "nobody@example.com"}).json()
    assert pending["message"] == unknown["message"]


def test_login_succeeds_after_resend_confirmation(client):
    register_unconfirmed(client, "resend-login@example.com")
    resend = client.post("/auth/resend-confirmation", json={"email": "resend-login@example.com"})
    assert resend.status_code == 200
    confirmation_url = resend.json()["confirmation_url"]
    assert confirmation_url is not None

    blocked = client.post("/auth/login", data={"username": "resend-login@example.com", "password": "password123"})
    assert blocked.status_code == 403

    assert client.get(confirmation_url).status_code == 200

    allowed = client.post("/auth/login", data={"username": "resend-login@example.com", "password": "password123"})
    assert allowed.status_code == 200
    assert allowed.json()["access_token"]
