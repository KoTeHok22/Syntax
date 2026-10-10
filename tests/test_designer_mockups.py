import asyncio
import base64
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
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
from backend.services import designer_mockups
from backend.services.designer_audit import reference_task_image
from backend.services.designer_mockups import (
    ALLOWED_HEURISTICS,
    MAX_DEFECTS,
    MAX_HTML_BYTES,
    GeneratedMockup,
    clean_defects,
    mockup_data_url,
    parse_generation,
    strip_html,
)
from backend.services.llm import StubLLMClient


def valid_payload(html="<html><body>ok</body></html>", scenario="Оформите заказ на телефоне одной рукой без потерь.", defects=None):
    if defects is None:
        defects = [{"heuristic_id": "contrast", "description": "Бледный текст итоговой суммы.", "severity": "high"}]
    return {"html": html, "scenario": scenario, "defects": defects}


def json_llm(payload):
    class Client:
        async def complete(self, prompt):
            return json.dumps(payload)

    return Client()


@pytest.fixture()
def audit_client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        for id, role in ((1, "candidate"), (2, "candidate"), (3, "employer")):
            db.add(User(id=id, email=f"mockup{id}@example.com", password_hash="unused", role=role, consent_accepted=True, is_email_confirmed=True))
        db.flush()
        db.add_all([CandidateProfile(id=1, user_id=1), CandidateProfile(id=2, user_id=2)])
        db.commit()
    app = FastAPI()
    app.include_router(router)

    def database():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        yield client, sessions
    engine.dispose()


def auth(id=1):
    settings = get_settings()
    token = create_access_token(
        id, f"mockup{id}@example.com", "employer" if id == 3 else "candidate", None,
        settings.jwt_secret, settings.jwt_algorithm, settings.jwt_expires_minutes, settings.jwt_issuer,
    )
    return {"Authorization": f"Bearer {token}"}


def test_parse_generation_accepts_strict_json():
    html, scenario, defects = parse_generation(json.dumps(valid_payload()))
    assert html == "<html><body>ok</body></html>"
    assert scenario.startswith("Оформите заказ")
    assert defects[0]["heuristic_id"] == "contrast"


def test_parse_generation_strips_json_fences():
    fenced = "```json\n" + json.dumps(valid_payload()) + "\n```"
    html, scenario, defects = parse_generation(fenced)
    assert html == "<html><body>ok</body></html>"
    assert defects[0]["severity"] == "high"


def test_parse_generation_rejects_empty_html():
    with pytest.raises(ValueError):
        parse_generation(json.dumps(valid_payload(html="")))


def test_parse_generation_rejects_oversized_html():
    oversized = "a" * (MAX_HTML_BYTES + 1)
    with pytest.raises(ValueError):
        parse_generation(json.dumps(valid_payload(html=oversized)))


def test_parse_generation_rejects_short_scenario():
    with pytest.raises(ValueError):
        parse_generation(json.dumps(valid_payload(scenario="short")))


def test_parse_generation_rejects_all_invalid_defects():
    payload = valid_payload(defects=[{"heuristic_id": "made_up", "description": "unknown"}, {"heuristic_id": "", "description": "blank"}])
    with pytest.raises(ValueError):
        parse_generation(json.dumps(payload))


def test_parse_generation_rejects_non_json():
    with pytest.raises(json.JSONDecodeError):
        parse_generation("bad JSON")


def test_clean_defects_drops_unknown_and_non_dict_and_dedupes():
    items = [
        {"heuristic_id": "made_up", "description": "unknown id"},
        "not a dict",
        {"heuristic_id": "contrast", "description": "первый"},
        {"heuristic_id": "contrast", "description": "дубликат"},
        {"heuristic_id": "hierarchy", "description": "второй"},
    ]
    defects = clean_defects(items)
    assert [item["heuristic_id"] for item in defects] == ["contrast", "hierarchy"]


def test_clean_defects_caps_at_max_defects():
    items = [{"heuristic_id": "contrast", "description": f"описание {index}", "severity": "low"} for index in range(MAX_DEFECTS + 5)]
    items = [{**item, "heuristic_id": f"unknown_{index}"} for index, item in enumerate(items)]
    defects = clean_defects(items)
    assert defects == []

    allowed = list(ALLOWED_HEURISTICS)
    repeated = [{"heuristic_id": allowed[index % len(allowed)], "description": f"{allowed[index % len(allowed)]} {index}"} for index in range(MAX_DEFECTS + 5)]
    capped = clean_defects(repeated)
    assert len(capped) == min(MAX_DEFECTS, len(ALLOWED_HEURISTICS))


def test_clean_defects_normalizes_severity_and_truncates_description():
    items = [
        {"heuristic_id": "contrast", "description": "x" * 500, "severity": "critical"},
        {"heuristic_id": "hierarchy", "description": "ok", "severity": "low"},
    ]
    defects = clean_defects(items)
    by_id = {item["heuristic_id"]: item for item in defects}
    assert by_id["contrast"]["severity"] == "medium"
    assert len(by_id["contrast"]["description"]) == 300
    assert by_id["hierarchy"]["severity"] == "low"


def test_clean_defects_returns_empty_for_non_list():
    assert clean_defects(None) == []
    assert clean_defects({"heuristic_id": "contrast"}) == []


def test_strip_html_raises_on_oversized_input():
    with pytest.raises(ValueError):
        strip_html("b" * (MAX_HTML_BYTES + 1))


def test_strip_html_accepts_small_input():
    assert strip_html("<p>ok</p>") == "<p>ok</p>"


def test_mockup_data_url_returns_png_data_url():
    url = mockup_data_url(b"\x89PNG\r\n\x1a\n")
    assert url.startswith("data:image/png;base64,")
    assert base64.b64decode(url.split(",", 1)[1]) == b"\x89PNG\r\n\x1a\n"


def test_mockup_data_url_rejects_over_two_megabytes():
    with pytest.raises(ValueError):
        mockup_data_url(b"x" * (2 * 1024 * 1024 + 1))


def test_generate_mockup_returns_none_when_renderer_unavailable(monkeypatch):
    monkeypatch.setattr(designer_mockups, "renderer_available", lambda: False)
    assert asyncio.run(designer_mockups.generate_mockup()) is None


def test_generate_mockup_returns_none_for_stub_client(monkeypatch):
    monkeypatch.setattr(designer_mockups, "renderer_available", lambda: True)
    monkeypatch.setattr(designer_mockups, "get_llm_client", lambda: StubLLMClient())
    assert asyncio.run(designer_mockups.generate_mockup()) is None


def test_generate_mockup_returns_generated_mockup(monkeypatch):
    monkeypatch.setattr(designer_mockups, "renderer_available", lambda: True)
    monkeypatch.setattr(designer_mockups, "get_llm_client", lambda: json_llm(valid_payload()))
    result = asyncio.run(designer_mockups.generate_mockup())
    assert isinstance(result, GeneratedMockup)
    assert result.source == "llm"
    assert result.html == "<html><body>ok</body></html>"
    assert result.defects[0]["heuristic_id"] == "contrast"


def test_generate_mockup_returns_none_on_invalid_json(monkeypatch):
    class Client:
        async def complete(self, prompt):
            return "not json"

    monkeypatch.setattr(designer_mockups, "renderer_available", lambda: True)
    monkeypatch.setattr(designer_mockups, "get_llm_client", lambda: Client())
    assert asyncio.run(designer_mockups.generate_mockup()) is None


def test_renderer_available_is_safe_without_playwright(monkeypatch):
    monkeypatch.setattr(designer_mockups.importlib.util, "find_spec", lambda name: None)
    monkeypatch.setattr(designer_mockups, "get_settings", lambda: type("S", (), {"html_render_enabled": True})())
    assert designer_mockups.renderer_available() is False


def test_create_reference_task_persists_generated_defects(audit_client, monkeypatch):
    client, sessions = audit_client
    generated = GeneratedMockup(
        html="<html><body>generated</body></html>",
        scenario="Сгенерированный сценарий оформления заказа на телефоне.",
        defects=[{"heuristic_id": "contrast", "description": "Бледная сумма", "severity": "high"}],
        source="llm",
    )

    async def fake_generate():
        return generated

    monkeypatch.setattr(designer_audits, "generate_mockup", fake_generate)

    async def fake_render(html):
        return b"\x89PNG\r\n\x1a\n"

    monkeypatch.setattr(designer_audits, "render_html_to_png", fake_render)
    response = client.post("/designer-audits/task", headers=auth())
    assert response.status_code == 201
    body = response.json()
    assert body["task_key"] == "checkout-v1"
    assert body["scenario"] == generated.scenario
    assert body["screenshot_data_url"].startswith("data:image/png;base64,")
    with sessions() as db:
        record = db.get(DesignerAudit, body["id"])
        assert record.reference_defects == generated.defects


def test_create_reference_task_falls_back_when_render_fails(audit_client, monkeypatch):
    client, sessions = audit_client
    generated = GeneratedMockup(
        html="<html><body>generated</body></html>",
        scenario="Сгенерированный сценарий оформления заказа на телефоне.",
        defects=[{"heuristic_id": "contrast", "description": "Бледная сумма", "severity": "high"}],
        source="llm",
    )

    async def fake_generate():
        return generated

    def failing_render(html):
        raise ValueError("HTML-рендерер недоступен")

    monkeypatch.setattr(designer_audits, "generate_mockup", fake_generate)
    monkeypatch.setattr(designer_audits, "render_html_to_png", failing_render)
    response = client.post("/designer-audits/task", headers=auth())
    assert response.status_code == 201
    body = response.json()
    assert body["task_key"] == "checkout-v1"
    assert body["screenshot_data_url"] == reference_task_image()
    with sessions() as db:
        record = db.get(DesignerAudit, body["id"])
        assert record.reference_defects == []
