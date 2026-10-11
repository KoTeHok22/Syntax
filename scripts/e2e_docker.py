import os
import subprocess
import sys
import time

import httpx

BASE_URL = "http://localhost:8000"
HEALTH_TIMEOUT_SECONDS = 300


def run(command: list[str]) -> subprocess.CompletedProcess:
    env = {**os.environ, "LLM_BASE_URL": "", "LLM_API_KEY": "", "LLM_MODEL": ""}
    return subprocess.run(command, capture_output=True, text=True, env=env)


def wait_for_health() -> None:
    deadline = time.monotonic() + HEALTH_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{BASE_URL}/health", timeout=3)
            if response.status_code == 200:
                return
        except httpx.TransportError:
            pass
        time.sleep(2)
    raise RuntimeError("API не поднялся в течение отведённого времени")


def register_and_login(client: httpx.Client, email: str, role: str) -> str:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "e2e-password", "role": role, "consent_accepted": True},
    )
    assert response.status_code == 201, response.text
    confirmation_url = response.json()["confirmation_url"]
    confirmed = client.get(confirmation_url)
    assert confirmed.status_code == 200, confirmed.text
    login = client.post("/auth/login", data={"username": email, "password": "e2e-password"})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def main() -> None:
    compose = run(["docker", "compose", "up", "-d", "--build"])
    if compose.returncode != 0:
        print(compose.stderr)
        raise SystemExit("docker compose up failed")
    try:
        wait_for_health()
        print("health: OK")

        for script in ["scripts.seed", "scripts.generate_task_pool"]:
            seeded = run(["docker", "compose", "exec", "-T", "api", "python", "-m", script])
            if seeded.returncode != 0:
                print(seeded.stdout, seeded.stderr)
                raise SystemExit(f"{script} failed")
        print("seed: OK")

        with httpx.Client(base_url=BASE_URL, timeout=30) as client:
            candidate_token = register_and_login(client, "e2e-candidate@example.com", "candidate")
            employer_token = register_and_login(client, "e2e-employer@example.com", "employer")

            updated = client.put(
                "/candidates/me",
                json={
                    "full_name": "Сквозной Кандидат",
                    "contacts": {"email": "e2e-candidate@example.com"},
                    "stack": ["python"],
                    "years_of_experience": 2,
                    "soft_skills": ["коммуникация"],
                    "specialization": "backend",
                },
                headers=auth(candidate_token),
            )
            assert updated.status_code == 200, updated.text
            graded = client.put("/candidates/me/grade", json={"grade": "junior"}, headers=auth(candidate_token))
            assert graded.status_code == 200, graded.text

            session = client.post("/test-sessions", json={"grade": "junior"}, headers=auth(candidate_token))
            assert session.status_code == 201, session.text
            assert session.json()["task_count"] == 5, session.text

            answers = client.post(
                f"/test-sessions/{session.json()['id']}/answers",
                json=[{"task_id": task["id"], "option_index": 0} for task in session.json()["tasks"]],
                headers=auth(candidate_token),
            )
            assert answers.status_code == 200, answers.text
            print(f"test-session: OK ({answers.json()['task_count']} задач, вердикт {answers.json()['verdict']})")

            categories = client.get("/employer/categories", headers=auth(employer_token))
            assert categories.status_code == 200, categories.text
            category = next(c for c in categories.json() if c["specialization"] == "backend")
            cards = client.get(f"/employer/categories/{category['id']}/cards", headers=auth(employer_token))
            assert cards.status_code == 200, cards.text
            card = cards.json()[0]
            assert "full_name" not in card
            print(f"cards: OK (score={card['score']}, компонентов={len(card['score_breakdown'])})")

            invitation = client.post(
                "/invitations",
                json={
                    "candidate_profile_id": card["candidate_profile_id"],
                    "message": "Приглашаем в команду",
                    "salary_from": 150000,
                    "salary_to": 200000,
                    "company_name": "ООО Сквозной Тест",
                    "contact_method": "hr@example.com",
                },
                headers=auth(employer_token),
            )
            assert invitation.status_code == 201, invitation.text
            invitation_id = invitation.json()["id"]

            sent = client.get("/invitations/sent", headers=auth(employer_token))
            assert sent.json()[0]["candidate_contacts"] is None

            client.post(f"/invitations/{invitation_id}/view", headers=auth(candidate_token))
            accepted = client.post(f"/invitations/{invitation_id}/accept", headers=auth(candidate_token))
            assert accepted.json()["status"] == "accepted"

            revealed = client.get("/invitations/sent", headers=auth(employer_token))
            assert revealed.json()[0]["candidate_contacts"] is not None
            print("invitations: OK (контакты раскрыты после принятия)")

            vacancy = client.post(
                "/vacancies",
                json={
                    "title": "E2E Backend",
                    "stack": ["python"],
                    "specialization": "backend",
                    "grade": "junior",
                    "salary_from": 100000,
                    "salary_to": 150000,
                },
                headers=auth(employer_token),
            )
            assert vacancy.status_code == 201, vacancy.text
            application = client.post(
                "/applications",
                json={"vacancy_id": vacancy.json()["id"], "message": "Отклик из e2e"},
                headers=auth(candidate_token),
            )
            assert application.status_code == 201, application.text

            regular = client.post(
                "/regular-tasks",
                json={"vacancy_id": vacancy.json()["id"], "statement": "E2E вопрос", "options": ["да", "нет"], "correct_index": 0},
                headers=auth(employer_token),
            )
            assert regular.status_code == 201, regular.text
            regular_session = client.post(
                f"/regular-tasks/vacancy/{vacancy.json()['id']}/session",
                headers=auth(candidate_token),
            )
            assert regular_session.status_code == 201, regular_session.text
            session_body = regular_session.json()
            answers = [
                {"regular_task_id": item["id"], "option_index": 0}
                for item in session_body["tasks"]
            ]
            regular_answer = client.post(
                f"/regular-tasks/sessions/{session_body['id']}/answers",
                json=answers,
                headers=auth(candidate_token),
            )
            assert regular_answer.status_code == 200, regular_answer.text
            print("vacancies/applications/regular-tasks: OK")

            pdf = client.get("/candidates/me/profile.pdf", headers=auth(candidate_token))
            assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"
            print("profile.pdf: OK")

        print("E2E OK: сквозной сценарий прошёл против PostgreSQL + uvicorn в docker compose")
    finally:
        run(["docker", "compose", "down", "-v"])


if __name__ == "__main__":
    main()
