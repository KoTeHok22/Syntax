import sys

from tests.test_api import auth, register_and_login


def test_profile_update_accepts_null_full_name(client):
    token = register_and_login(client, "nullname@example.com", "candidate")
    response = client.put(
        "/candidates/me",
        json={
            "full_name": None,
            "contacts": {"email": "nullname@example.com"},
            "stack": ["python"],
            "years_of_experience": 0,
            "soft_skills": [],
            "specialization": "",
        },
        headers=auth(token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["full_name"] == ""
    assert response.json()["contacts"]["email"] == "nullname@example.com"
