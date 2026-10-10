import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from backend.services import ats, vacancy_moderation


def vacancy(title: str, description: str, stack=None):
    return SimpleNamespace(
        title=title,
        description=description,
        stack=stack or [],
        specialization="backend",
        salary_from=100000,
        salary_to=200000,
    )


def test_deterministic_moderation_blocks_upfront_fee_with_actionable_reason():
    result = vacancy_moderation.deterministic_moderation(
        "Оплатите регистрацию и обучение до трудоустройства."
    )
    assert result.blocked
    assert "оплат" in result.reason.lower()


def test_deterministic_moderation_allows_legitimate_crypto_work():
    result = vacancy_moderation.deterministic_moderation(
        "Разрабатываем кошелек и криптографические протоколы. Оплата от компании."
    )
    assert not result.blocked


@pytest.mark.parametrize(
    "description, blocked",
    [
        ("Never share passwords, but pay registration/training fee before employment.", True),
        ("Никогда не сообщайте пароли, но оплатите регистрацию и обучение до трудоустройства.", True),
        ("Never pay registration fees, but pay training fees before employment.", True),
        ("Не нужно оплатить регистрацию, но нужно оплатить обучение до трудоустройства.", True),
        ("Do not share passwords and pay registration fees before employment.", True),
        ("Не нужно сообщать пароли; оплатите регистрацию до трудоустройства.", True),
        ("Pay registration fees, but never share passwords.", True),
        ("Оплатите обучение, но никогда не сообщайте пароли.", True),
        ("Never pay registration or training fees before employment; the company covers them.", False),
        ("Не нужно оплатить регистрацию или обучение: расходы покрывает компания.", False),
        ("Do not pay training fees, and never pay registration fees.", False),
        ("Не требуется оплатить регистрацию, а обучение оплачивает компания.", False),
        ("Never share passwords, and do not pay registration fees.", False),
        ("Никогда не сообщайте пароли, но не нужно оплатить регистрацию.", False),
        ("No payment is required for registration or training.", False),
        ("Don't pay registration fees before employment.", False),
        ("You do not need to pay registration or training fees.", False),
        ("Candidates are not required to pay training fees.", False),
        ("You must not pay registration fees.", False),
        ("Do not pay registration fees, but send money for equipment.", True),
        ("Никогда не оплатите регистрацию, а переведите депозит до трудоустройства.", True),
    ],
)
def test_moderation_scopes_negation_to_local_action_when_llm_unavailable(monkeypatch, description, blocked):
    class Client:
        async def complete(self, prompt):
            raise RuntimeError("offline")

    monkeypatch.setattr(vacancy_moderation, "get_llm_client", lambda: Client())
    result = asyncio.run(vacancy_moderation.moderate_vacancy(vacancy("Engineer", description)))
    assert result.source == "rules"
    assert result.blocked is blocked
    assert bool(result.reason) is blocked


def test_llm_moderation_accepts_valid_low_risk_json(monkeypatch):
    class Client:
        async def complete(self, prompt):
            assert "Scam Detector" in prompt
            return '{"risk_score": 0.12, "reason": ""}'

    monkeypatch.setattr(vacancy_moderation, "get_llm_client", lambda: Client())
    result = asyncio.run(vacancy_moderation.moderate_vacancy(vacancy("Python developer", "Работа в команде.")))
    assert result.source == "llm"
    assert not result.blocked


@pytest.mark.parametrize("response", ["not json", '{"risk_score": "high", "reason": "bad"}', "{}",
                                     '{"risk_score": NaN, "reason": "bad"}',
                                     '{"risk_score": 1.1, "reason": "bad"}',
                                     '{"risk_score": true, "reason": "bad"}',
                                     '{"risk_score": 0.9, "reason": ""}'])
def test_malformed_llm_result_uses_deterministic_fallback(monkeypatch, response):
    class Client:
        async def complete(self, prompt):
            return response

    monkeypatch.setattr(vacancy_moderation, "get_llm_client", lambda: Client())
    result = asyncio.run(vacancy_moderation.moderate_vacancy(vacancy("Engineer", "Криптография и блокчейн.")))
    assert result.source == "rules"
    assert not result.blocked


def test_llm_error_uses_deterministic_scam_fallback(monkeypatch):
    class Client:
        async def complete(self, prompt):
            raise RuntimeError("offline")

    monkeypatch.setattr(vacancy_moderation, "get_llm_client", lambda: Client())
    result = asyncio.run(vacancy_moderation.moderate_vacancy(vacancy("Operator", "Переведите депозит до выхода на работу.")))
    assert result.source == "rules"
    assert result.blocked


def test_llm_error_allows_legitimate_vacancy(monkeypatch):
    class Client:
        async def complete(self, prompt):
            raise RuntimeError("offline")

    monkeypatch.setattr(vacancy_moderation, "get_llm_client", lambda: Client())
    result = asyncio.run(vacancy_moderation.moderate_vacancy(vacancy("Engineer", "Криптографические протоколы.")))
    assert result.source == "rules"
    assert not result.blocked


@pytest.mark.parametrize("score,blocked", [(0.7, False), (0.71, True)])
def test_llm_threshold_blocks_only_above_point_seven(monkeypatch, score, blocked):
    class Client:
        async def complete(self, prompt):
            return f'{{"risk_score": {score}, "reason": "Уберите предложение переводить чужие деньги."}}'

    monkeypatch.setattr(vacancy_moderation, "get_llm_client", lambda: Client())
    result = asyncio.run(vacancy_moderation.moderate_vacancy(vacancy("Operator", "Управление переводами.")))
    assert result.blocked is blocked


def test_webhook_url_requires_admin_allowlist_and_public_https(monkeypatch):
    settings = SimpleNamespace(ats_allowed_webhook_urls=["https://ats.example.test/hook"])
    monkeypatch.setattr(ats, "get_settings", lambda: settings)
    assert ats.validate_webhook_url("https://ats.example.test/hook")
    with pytest.raises(HTTPException):
        ats.validate_webhook_url("http://ats.example.test/hook")
    with pytest.raises(HTTPException):
        ats.validate_webhook_url("https://127.0.0.1/hook")
    with pytest.raises(HTTPException):
        ats.validate_webhook_url("https://other.example.test/hook")


def test_delivery_rejects_non_owned_application_before_network(monkeypatch):
    class Query:
        def join(self, *args):
            return self

        def filter(self, *args):
            return self

        def with_for_update(self, **kwargs):
            return self

        def populate_existing(self):
            return self

        def first(self):
            return None

    class DB:
        def query(self, *args):
            return Query()

    with pytest.raises(HTTPException) as error:
        ats.deliver_application(DB(), 99, 7)
    assert error.value.status_code == 404


def test_delivery_rejects_unaccepted_application_without_network():
    application = SimpleNamespace(status="new", id=1)

    class Query:
        def join(self, *args):
            return self

        def filter(self, *args):
            return self

        def with_for_update(self, **kwargs):
            return self

        def populate_existing(self):
            return self

        def order_by(self, *args):
            return self

        def limit(self, *args):
            return self

        def all(self):
            return []

        def first(self):
            return application

    class DB:
        def query(self, *args):
            return Query()

    with pytest.raises(HTTPException) as error:
        ats.deliver_application(DB(), 1, 7)
    assert error.value.status_code == 409


def test_delivery_failure_is_recorded_and_can_be_retried(monkeypatch):
    application = SimpleNamespace(
        id=1, status="accepted", ats_delivery_status="pending", ats_delivery_attempts=0,
        ats_delivery_error=None, ats_delivered_at=None,
        vacancy_id=3, message="Interested",
        candidate_profile=SimpleNamespace(id=4, full_name="Candidate", contacts={}, grade="middle",
                                          specialization="backend", stack=[]),
        vacancy=SimpleNamespace(id=3, title="Engineer", stack=[]),
    )
    employer = SimpleNamespace(ats_webhook_url="https://ats.example.test/hook")

    class Query:
        def join(self, *args):
            return self

        def filter(self, *args):
            return self

        def with_for_update(self, **kwargs):
            return self

        def populate_existing(self):
            return self

        def first(self):
            return application

    class DB:
        def query(self, *args):
            return Query()

        def get(self, model, key):
            return employer

        def commit(self):
            return None

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, *args, **kwargs):
            request = httpx.Request("POST", args[0])
            response = httpx.Response(503, request=request)
            raise httpx.HTTPStatusError("failed", request=request, response=response)

    settings = SimpleNamespace(
        ats_allowed_webhook_urls=[employer.ats_webhook_url], ats_timeout_seconds=5, ats_webhook_secret="",
    )
    monkeypatch.setattr(ats, "get_settings", lambda: settings)
    monkeypatch.setattr(ats.httpx, "Client", Client)
    monkeypatch.setattr(ats, "embedding_is_current", lambda *args: False)
    monkeypatch.setattr(ats, "candidate_embedding_text", lambda *args: "candidate")
    monkeypatch.setattr("backend.api.routes.candidates.build_card", lambda *args: SimpleNamespace(
        score=0, score_breakdown={}, match_relevance=0, final_score=0, match_breakdown={},
    ))
    first = ats.deliver_application(DB(), 1, 7)
    second = ats.deliver_application(DB(), 1, 7)
    assert first["status"] == "failed"
    assert second["status"] == "failed"
    assert second["attempts"] == 2


def test_successful_delivery_is_idempotent_and_sends_contacts_only_after_acceptance(monkeypatch):
    application = SimpleNamespace(
        id=2, status="accepted", ats_delivery_status="pending", ats_delivery_attempts=0,
        ats_delivery_error=None, ats_delivered_at=None, vacancy_id=4,
        message="Interested", vacancy=SimpleNamespace(id=4, title="Backend", stack=["python"]),
        candidate_profile=SimpleNamespace(
            id=5, full_name="Candidate", contacts={"email": "candidate@example.com"},
            grade="middle", specialization="backend", stack=["python"],
        ),
    )
    employer = SimpleNamespace(ats_webhook_url="https://ats.example.test/hook")
    sent = []

    class Query:
        def join(self, *args):
            return self

        def filter(self, *args):
            return self

        def with_for_update(self, **kwargs):
            return self

        def populate_existing(self):
            return self

        def order_by(self, *args):
            return self

        def limit(self, *args):
            return self

        def all(self):
            return []

        def first(self):
            return application

    class DB:
        def query(self, *args):
            return Query()

        def get(self, model, key):
            return employer

        def commit(self):
            return None

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, content, headers):
            sent.append((url, content, headers))
            request = httpx.Request("POST", url)
            return httpx.Response(204, request=request)

    settings = SimpleNamespace(
        ats_allowed_webhook_urls=[employer.ats_webhook_url], ats_timeout_seconds=5, ats_webhook_secret="secret",
    )
    monkeypatch.setattr(ats, "get_settings", lambda: settings)
    monkeypatch.setattr(ats.httpx, "Client", Client)
    monkeypatch.setattr(ats, "embedding_is_current", lambda *args: False)
    monkeypatch.setattr(ats, "candidate_embedding_text", lambda *args: "candidate")
    monkeypatch.setattr("backend.api.routes.candidates.build_card", lambda *args: SimpleNamespace(
        score=0.8, score_breakdown={}, match_relevance=0.9, final_score=0.72, match_breakdown={},
    ))
    result = ats.deliver_application(DB(), 2, 7)
    assert result["status"] == "delivered"
    assert len(sent) == 1
    assert 'candidate@example.com' in sent[0][1].decode()
    assert sent[0][2]["Idempotency-Key"] == "syntax.application.accepted:2"
    assert sent[0][2]["X-Syntax-Signature"].startswith("sha256=")
    result = ats.deliver_application(DB(), 2, 7)
    assert result["status"] == "delivered"
    assert len(sent) == 1


@pytest.fixture
def isolated_api(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from backend.api.deps import get_db
    from backend.api.routes import applications, vacancies
    from backend.api.routes import ats as ats_routes
    from backend.auth.security import create_access_token
    from backend.core.config import get_settings
    from backend.db import Base
    from backend.models import CandidateProfile, EmployerProfile, User

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    app = FastAPI()
    for router in [applications.router, vacancies.router, ats_routes.router]:
        app.include_router(router)

    def database():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = database
    settings = get_settings()
    headers = []
    with sessions() as session:
        for index, role in enumerate(["employer", "employer", "candidate"], start=1):
            user = User(email=f"isolated{index}@example.com", password_hash="unused", role=role,
                        consent_accepted=True, is_email_confirmed=True)
            session.add(user)
            session.flush()
            if role == "employer":
                session.add(EmployerProfile(user_id=user.id))
            else:
                session.add(CandidateProfile(user_id=user.id, full_name="Accepted Candidate",
                                             contacts={"email": "private@example.com"}, stack=["python"]))
            token = create_access_token(user.id, user.email, role, None, settings.jwt_secret,
                                        settings.jwt_algorithm, 60, settings.jwt_issuer)
            headers.append({"Authorization": f"Bearer {token}"})
        session.commit()

    class LLM:
        async def complete(self, prompt):
            return '{"risk_score": 0.1, "reason": ""}'

    monkeypatch.setattr(vacancy_moderation, "get_llm_client", lambda: LLM())
    async def no_embedding(entity):
        return False
    monkeypatch.setattr(vacancies, "index_vacancy", no_embedding)
    with TestClient(app) as client:
        yield client, headers, sessions
    engine.dispose()


def test_api_moderates_create_and_update_without_mutating_existing_vacancy(isolated_api):
    from backend.models import Vacancy

    client, headers, sessions = isolated_api
    payload = {"title": "Crypto engineer", "description": "Build cryptographic protocols",
               "stack": ["python"], "salary_from": 100000, "salary_to": 200000}
    created = client.post("/vacancies", json=payload, headers=headers[0])
    assert created.status_code == 201
    vacancy_id = created.json()["id"]
    scam = {**payload, "description": "Оплатите регистрацию до выхода на работу."}
    blocked = client.post("/vacancies", json=scam, headers=headers[0])
    assert blocked.status_code == 422
    assert "оплат" in blocked.json()["detail"].lower()
    blocked_update = client.put(f"/vacancies/{vacancy_id}", json=scam, headers=headers[0])
    assert blocked_update.status_code == 422
    assert client.put(f"/vacancies/{vacancy_id}", json=payload, headers=headers[1]).status_code == 404
    with sessions() as session:
        assert session.get(Vacancy, vacancy_id).description == payload["description"]
        assert session.query(Vacancy).count() == 1


def test_api_ats_auth_ownership_accepted_only_failure_retry_and_duplicate(isolated_api, monkeypatch):
    import json
    from datetime import datetime, timezone

    from backend.models import Application, TestSession

    client, headers, sessions = isolated_api
    settings = SimpleNamespace(ats_allowed_webhook_urls=["https://ats.example.test/hook"],
                               ats_timeout_seconds=5, ats_webhook_secret="secret")
    monkeypatch.setattr(ats, "get_settings", lambda: settings)
    assert client.get("/ats/config").status_code == 401
    assert client.get("/ats/config", headers=headers[2]).status_code == 403
    assert client.put("/ats/config", json={"webhook_url": "https://other.example.test/hook"},
                      headers=headers[0]).status_code == 422
    assert client.put("/ats/config", json={"webhook_url": settings.ats_allowed_webhook_urls[0]},
                      headers=headers[0]).status_code == 200
    assert client.get("/ats/config", headers=headers[1]).json()["webhook_url"] is None
    vacancy_id = client.post("/vacancies", json={"title": "Engineer", "stack": ["python"],
                                               "salary_from": 100000, "salary_to": 200000},
                             headers=headers[0]).json()["id"]
    application_id = client.post("/applications", json={"vacancy_id": vacancy_id},
                                 headers=headers[2]).json()["id"]
    with sessions() as session:
        candidate_id = session.get(Application, application_id).candidate_profile_id
        session.add(TestSession(candidate_profile_id=candidate_id, grade="middle", result_score=80,
                                verdict="confirmed", status="completed", completed_at=datetime.now(timezone.utc)))
        session.commit()
    calls = []

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False
            assert kwargs["trust_env"] is False
            assert kwargs["timeout"] <= 10

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, content, headers):
            calls.append((content, headers))
            return httpx.Response(503 if len(calls) == 1 else 204, request=httpx.Request("POST", url))

    monkeypatch.setattr(ats.httpx, "Client", Client)
    retry = {"application_id": application_id}
    assert client.post("/ats/webhook", json=retry, headers=headers[0]).status_code == 409
    assert client.post("/ats/webhook", json=retry, headers=headers[1]).status_code == 404
    assert not calls
    accepted = client.put(f"/applications/{application_id}/status", json={"status": "accepted"},
                          headers=headers[0])
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    assert len(calls) == 1
    assert b"private@example.com" in calls[0][0]
    payload = json.loads(calls[0][0])
    assert payload["candidate"]["completed_tests"][0]["result_score"] == 80
    assert payload["candidate"]["completed_tests"][0]["verdict"] == "confirmed"
    assert payload["candidate"]["match_breakdown"]["mode"] == "lexical"
    retried = client.post("/ats/webhook", json=retry, headers=headers[0])
    assert retried.json()["status"] == "delivered"
    assert retried.json()["attempts"] == 2
    assert client.post("/ats/webhook", json=retry, headers=headers[0]).json()["status"] == "delivered"
    assert len(calls) == 2
    assert calls[0][1]["Idempotency-Key"] == calls[1][1]["Idempotency-Key"]
