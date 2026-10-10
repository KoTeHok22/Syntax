import asyncio
import base64
import io
import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.deps import get_db
from backend.api.routes import designer_audits
from backend.api.routes.designer_audits import router
from backend.auth.security import create_access_token
from backend.core.config import get_settings
from backend.db import Base
from backend.models.designer_audit import DesignerAudit
from backend.models.profiles import CandidateProfile
from backend.models.user import User
from backend.schemas.designer_audit import DesignerAuditSubmit
from backend.services import designer_audit
from backend.services.llm import StubLLMClient


def image_bytes():
    return base64.b64decode(designer_audit.reference_task_image().split(",", 1)[1])


def violation(heuristic_id="contrast"):
    return {
        "heuristic_id": heuristic_id,
        "rationale": "The checkout total is hard to distinguish from the background, so a shopper cannot confirm the cost before placing the order.",
        "evidence": "The total and shipping labels use pale gray text on a white background; the ratio has not been measured.",
        "severity": "high",
        "recommendation": "Use darker text for the total and verify the normal-text contrast ratio is at least 4.5:1 before testing checkout.",
    }


def assessment_json(score=3):
    return json.dumps({
        "criteria": [{"id": id, "score": score, "feedback": "Concrete evidence with a useful recommendation."} for id in ("evidence", "reasoning", "prioritization", "actionability")],
        "summary": "The reasoning is specific; a reviewer should check the screenshot and context.",
    })


@pytest.fixture()
def audit_client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        for id, role in ((1, "candidate"), (2, "candidate"), (3, "employer")):
            db.add(User(id=id, email=f"audit{id}@example.com", password_hash="unused", role=role, consent_accepted=True, is_email_confirmed=True))
        db.flush()
        db.add_all([CandidateProfile(id=1, user_id=1), CandidateProfile(id=2, user_id=2)])
        db.commit()
    app = FastAPI()
    app.include_router(router)
    def database():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = database
    monkeypatch.setattr(designer_audit, "get_llm_client", lambda: StubLLMClient())
    with TestClient(app) as client:
        yield client, sessions
    engine.dispose()


def auth(id=1):
    settings = get_settings()
    token = create_access_token(
        id, f"audit{id}@example.com", "employer" if id == 3 else "candidate", None,
        settings.jwt_secret, settings.jwt_algorithm, settings.jwt_expires_minutes, settings.jwt_issuer,
    )
    return {"Authorization": f"Bearer {token}"}


def create_audit(client):
    return client.post("/designer-audits", headers=auth(), json={
        "scenario": "Review the cart and place an order on a phone.",
        "screenshot_data_url": "data:image/png;base64," + base64.b64encode(image_bytes()).decode(),
    })


def test_audit_checklist_requires_candidate(audit_client):
    client, _ = audit_client
    assert client.get("/designer-audits/checklist").status_code == 401
    assert client.get("/designer-audits/checklist", headers=auth(3)).status_code == 403
    checklist = client.get("/designer-audits/checklist", headers=auth()).json()
    assert {item["id"] for item in checklist} == {
        "nielsen_visibility", "nielsen_consistency", "nielsen_error_prevention", "nielsen_user_control", "fitts_targets", "contrast", "hierarchy",
    }


def test_audit_json_create_submit_persists_and_is_owner_scoped(audit_client):
    client, sessions = audit_client
    created = create_audit(client)
    assert created.status_code == 201
    audit = created.json()
    assert audit["status"] == "pending"
    assert audit["task_key"] is None
    assert client.get(f"/designer-audits/{audit['id']}", headers=auth(2)).status_code == 404
    assert client.post(f"/designer-audits/{audit['id']}/submit", headers=auth(2), json={"violations": [violation()]}).status_code == 404
    response = client.post(f"/designer-audits/{audit['id']}/submit", headers=auth(), json={"violations": [violation()]})
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "submitted"
    assert result["evaluation"]["source"] == "deterministic"
    assert result["evaluation"]["testing_score"] is None
    assert "не подтверждённые выводы" in result["evaluation"]["limitation"]
    assert client.post(f"/designer-audits/{audit['id']}/submit", headers=auth(), json={"violations": [violation()]}).status_code == 409
    with sessions() as db:
        record = db.get(DesignerAudit, audit["id"])
        assert record.violations[0]["heuristic_id"] == "contrast"
        assert record.submitted_at is not None
        assert db.get(CandidateProfile, 1).grade is None


def test_audit_multipart_and_bad_image(audit_client):
    client, _ = audit_client
    response = client.post("/designer-audits/upload", headers=auth(), data={"scenario": "Complete checkout and confirm the total."}, files={"file": ("screenshot.png", image_bytes(), "image/png")})
    assert response.status_code == 201
    for data, mime in ((b"not an image", "image/png"), (image_bytes(), "image/jpeg"), (b"\x89PNG\r\n\x1a\n", "image/png"), (b"x" * (designer_audit.MAX_SCREENSHOT_BYTES + 1), "image/png")):
        response = client.post("/designer-audits/upload", headers=auth(), data={"scenario": "Complete checkout and confirm the total."}, files={"file": ("bad.png", data, mime)})
        assert response.status_code == 400
    assert client.post("/designer-audits/upload", headers=auth(), data={"scenario": " " * 10}, files={"file": ("screenshot.png", image_bytes(), "image/png")}).status_code == 422


@pytest.mark.parametrize("data_url", ["https://example.com/screen.png", "data:image/svg+xml;base64,PHN2Zz4=", "data:image/png;base64,a===", "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n").decode()])
def test_audit_invalid_data_url(audit_client, data_url):
    client, _ = audit_client
    response = client.post("/designer-audits", headers=auth(), json={"scenario": "Complete checkout on a phone.", "screenshot_data_url": data_url})
    assert response.status_code == 400


@pytest.mark.parametrize("violations", [[], [violation(), violation()], [violation("made_up")], [{**violation(), "rationale": " " * 10}]])
def test_audit_rejects_invalid_submission(audit_client, violations):
    client, _ = audit_client
    audit_id = create_audit(client).json()["id"]
    assert client.post(f"/designer-audits/{audit_id}/submit", headers=auth(), json={"violations": violations}).status_code == 422


def test_llm_rubric_and_reference_task_are_not_self_scored(audit_client, monkeypatch):
    client, _ = audit_client
    prompts = []
    class Client:
        async def complete(self, prompt):
            prompts.append(prompt)
            return assessment_json()
    monkeypatch.setattr(designer_audit, "get_llm_client", lambda: Client())
    task = client.post("/designer-audits/task", headers=auth()).json()
    assert task["task_key"] == "checkout-v1"
    assert client.post("/designer-audits/task", headers=auth()).json()["id"] == task["id"]
    selected = [violation(id) for id in designer_audit.REFERENCE_HEURISTICS]
    result = client.post(f"/designer-audits/{task['id']}/submit", headers=auth(), json={"violations": selected}).json()
    assert result["evaluation"]["score"] == 75
    assert result["evaluation"]["testing_score"] == 0.75
    assert result["evaluation"]["source"] == "llm"
    assert "cannot see the screenshot" in prompts[0]
    assert "data:image" not in prompts[0]
    audit_id = create_audit(client).json()["id"]
    result = client.post(f"/designer-audits/{audit_id}/submit", headers=auth(), json={"violations": selected}).json()
    assert result["evaluation"]["testing_score"] is None


def test_llm_prompt_uses_human_labels_and_result_strips_ids(audit_client, monkeypatch):
    client, _ = audit_client
    prompts = []

    class Client:
        async def complete(self, prompt):
            prompts.append(prompt)
            return json.dumps({
                "criteria": [{"id": id, "score": 3, "feedback": "Проверьте (contrast) и nielsen_visibility в этом сценарии."} for id in ("evidence", "reasoning", "prioritization", "actionability")],
                "summary": "Обратите внимание на fitts_targets (contrast).",
            })

    monkeypatch.setattr(designer_audit, "get_llm_client", lambda: Client())
    selected = [violation(id) for id in designer_audit.REFERENCE_HEURISTICS]
    task = client.post("/designer-audits/task", headers=auth()).json()
    result = client.post(f"/designer-audits/{task['id']}/submit", headers=auth(), json={"violations": selected}).json()

    assert '"heuristic_id"' not in prompts[0]
    assert "nielsen_visibility" not in prompts[0]
    assert '"principle"' in prompts[0]
    evaluation = result["evaluation"]
    assert "contrast" not in evaluation["summary"]
    assert "fitts_targets" not in evaluation["summary"]
    for criterion in evaluation["criteria"]:
        assert "contrast" not in criterion["feedback"]
        assert "nielsen_visibility" not in criterion["feedback"]


def test_humanize_heuristic_ids_removes_parenthetical_and_inline_codes():
    assert designer_audit.humanize_heuristic_ids("Проверьте (contrast) в этом сценарии.") == "Проверьте в этом сценарии."
    assert designer_audit.humanize_heuristic_ids("Обратите внимание на fitts_targets и nielsen_user_control.") == "Обратите внимание на и ."
    assert designer_audit.humanize_heuristic_ids("Обычный текст без идентификаторов.") == "Обычный текст без идентификаторов."


@pytest.mark.parametrize("raw", ["bad JSON", "[]", "null", '{"criteria": [], "summary": "x"}', assessment_json(5), assessment_json(True)])
def test_invalid_llm_returns_deterministic_fallback(monkeypatch, raw):
    class Client:
        async def complete(self, prompt):
            return raw
    monkeypatch.setattr(designer_audit, "get_llm_client", lambda: Client())
    submission = DesignerAuditSubmit(violations=[violation()])
    first = asyncio.run(designer_audit.evaluate_audit("Checkout", submission, "checkout-v1"))
    second = asyncio.run(designer_audit.evaluate_audit("Checkout", submission, "checkout-v1"))
    assert first == second
    assert first.source == "deterministic"
    assert first.testing_score is None


def test_llm_failure_returns_fallback(monkeypatch):
    class Client:
        async def complete(self, prompt):
            raise RuntimeError("provider failed")
    monkeypatch.setattr(designer_audit, "get_llm_client", lambda: Client())
    evaluation = asyncio.run(designer_audit.evaluate_audit("Checkout", DesignerAuditSubmit(violations=[violation()])))
    assert evaluation.source == "deterministic"


@pytest.mark.parametrize("failure", [RuntimeError("provider failed"), asyncio.TimeoutError(), "invalid JSON"])
def test_reference_task_can_retry_after_provider_failure(audit_client, monkeypatch, failure):
    client, sessions = audit_client
    responses = [failure, assessment_json()]

    class Client:
        async def complete(self, prompt):
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

    monkeypatch.setattr(designer_audit, "get_llm_client", lambda: Client())
    task = client.post("/designer-audits/task", headers=auth()).json()
    selected = [violation(id) for id in designer_audit.REFERENCE_HEURISTICS]
    first = client.post(f"/designer-audits/{task['id']}/submit", headers=auth(), json={"violations": selected})
    assert first.status_code == 200
    assert first.json()["evaluation"]["testing_score"] is None
    assert first.json()["evaluation"]["source"] == "deterministic"
    with sessions() as db:
        record = db.get(DesignerAudit, task["id"])
        assert record.violations == selected
        assert record.submitted_at is not None
    changed = [{**selected[0], "rationale": "Changed rationale after receiving feedback."}, *selected[1:]]
    assert client.post(f"/designer-audits/{task['id']}/submit", headers=auth(), json={"violations": changed}).status_code == 409
    second = client.post(f"/designer-audits/{task['id']}/submit", headers=auth(), json={"violations": selected})
    assert second.status_code == 200
    assert second.json()["evaluation"]["testing_score"] == 0.75
    assert second.json()["evaluation"]["source"] == "llm"
    assert client.post(f"/designer-audits/{task['id']}/submit", headers=auth(), json={"violations": selected}).status_code == 409
    with sessions() as db:
        assert db.get(DesignerAudit, task["id"]).evaluation["testing_score"] == 0.75


@pytest.mark.parametrize("retry", [False, True])
def test_reference_task_competing_submissions_do_not_overwrite(audit_client, monkeypatch, retry):
    client, sessions = audit_client
    task = client.post("/designer-audits/task", headers=auth()).json()
    if retry:
        response = client.post(f"/designer-audits/{task['id']}/submit", headers=auth(), json={"violations": [violation()]})
        assert response.status_code == 200
    evaluation = asyncio.run(designer_audit.evaluate_audit("Checkout", DesignerAuditSubmit(violations=[violation()])))

    async def race():
        first_waiting = asyncio.Event()
        second_finished = asyncio.Event()
        calls = 0

        async def evaluate(*args):
            nonlocal calls
            calls += 1
            if calls == 1:
                first_waiting.set()
                await second_finished.wait()
            return evaluation

        monkeypatch.setattr(designer_audits, "evaluate_audit", evaluate)
        with sessions() as first_db, sessions() as second_db:
            first = asyncio.create_task(designer_audits.submit_audit(
                task["id"], DesignerAuditSubmit(violations=[violation("contrast")]),
                first_db.get(CandidateProfile, 1), first_db,
            ))
            await first_waiting.wait()
            second_heuristic = "contrast" if retry else "hierarchy"
            second = await designer_audits.submit_audit(
                task["id"], DesignerAuditSubmit(violations=[violation(second_heuristic)]),
                second_db.get(CandidateProfile, 1), second_db,
            )
            assert second.violations[0].heuristic_id == second_heuristic
            second_finished.set()
            with pytest.raises(HTTPException) as error:
                await first
            assert error.value.status_code == 409

    asyncio.run(race())
    with sessions() as db:
        record = db.get(DesignerAudit, task["id"])
        assert record.violations[0]["heuristic_id"] == ("contrast" if retry else "hierarchy")
        assert record.evaluation["testing_score"] is None


def test_portfolio_metrics_are_extracted_and_persisted(audit_client):
    client, sessions = audit_client
    buffer = io.BytesIO()
    document = canvas.Canvas(buffer)
    document.drawString(40, 700, "Conversion increased to 24%; completion took 35 seconds. Interviewed 12 participants.")
    document.save()
    response = client.post("/designer-audits/portfolio", headers=auth(), files={"file": ("portfolio.pdf", buffer.getvalue(), "application/pdf")})
    assert response.status_code == 200
    evidence = response.json()
    assert {item["value"] for item in evidence["metrics"]} == {"24%", "35 seconds", "12 participants"}
    assert "не проверенные результаты" in evidence["limitation"]
    with sessions() as db:
        assert db.get(CandidateProfile, 1).portfolio_evidence == evidence
    assert client.post("/designer-audits/portfolio", headers=auth(), files={"file": ("bad.pdf", b"invalid", "application/pdf")}).status_code == 400


def test_empty_pdf_and_oversized_portfolio_rejected():
    with pytest.raises(ValueError):
        designer_audit.extract_portfolio_metrics(b"x" * (designer_audit.MAX_PORTFOLIO_BYTES + 1))
    buffer = io.BytesIO()
    document = canvas.Canvas(buffer)
    document.showPage()
    document.save()
    with pytest.raises(ValueError, match="не содержит выделяемого текста"):
        designer_audit.extract_portfolio_metrics(buffer.getvalue())


def test_portfolio_decimal_metrics_are_preserved():
    buffer = io.BytesIO()
    document = canvas.Canvas(buffer)
    document.drawString(40, 700, "Conversion increased to 24.5%. Completion took 3.5 seconds.")
    document.save()
    response = designer_audit.extract_portfolio_metrics(buffer.getvalue())
    assert {item.value for item in response.metrics} == {"24.5%", "3.5 seconds"}


def test_russian_portfolio_metrics(monkeypatch):
    monkeypatch.setattr(designer_audit, "extract_pdf_text", lambda data: "Конверсия онбординга выросла до 24,5%. Время выполнения снизилось до 35 секунд. Опросили 12 участников.")
    response = designer_audit.extract_portfolio_metrics(b"%PDF-test")
    assert {item.value for item in response.metrics} == {"24,5%", "35 секунд", "12 участников"}


def test_reference_penalizes_unrelated_selections(monkeypatch):
    class Client:
        async def complete(self, prompt):
            return assessment_json(4)
    monkeypatch.setattr(designer_audit, "get_llm_client", lambda: Client())
    reference = [
        {"heuristic_id": "fitts_targets", "description": "Мелкая кнопка оплаты"},
        {"heuristic_id": "contrast", "description": "Бледный текст итога"},
        {"heuristic_id": "hierarchy", "description": "Баннер подписки спорит с оплатой"},
        {"heuristic_id": "nielsen_user_control", "description": "Удаление без отмены"},
    ]
    selected = [violation(id) for id in ("fitts_targets", "contrast", "hierarchy", "nielsen_consistency")]
    result = asyncio.run(designer_audit.evaluate_audit(
        "Checkout", DesignerAuditSubmit(violations=selected), "checkout-v1", None, reference,
    ))
    assert result.reference_coverage == 0.75
    assert result.testing_score == 0.75
    assert "Удаление без отмены" in result.missed_defects


def test_llm_timeout_returns_fallback(monkeypatch):
    class Client:
        async def complete(self, prompt):
            raise asyncio.TimeoutError()
    monkeypatch.setattr(designer_audit, "get_llm_client", lambda: Client())
    result = asyncio.run(designer_audit.evaluate_audit("Checkout", DesignerAuditSubmit(violations=[violation()])))
    assert result.source == "deterministic"
