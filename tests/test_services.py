import smtplib
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate

from backend.db import Base, engine
from backend.core.labels import SPECIALIZATION_LABELS, grade_label, specialization_label
from backend.main import app
from backend.services.profile_pdf import FONT_PATH
from tests.test_api import register_and_login, seed_concept_bank


class FakeLLMClient:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.calls: list[str] = []

    async def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.responses.pop(0)


def test_ensure_vector_extension_is_noop_on_non_postgres():
    from backend.db import ensure_vector_extension

    assert ensure_vector_extension(engine) is False


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_simple_pdf(text: str) -> bytes:
    pdfmetrics.registerFont(TTFont("TestFont", str(FONT_PATH)))
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4)
    document.build(
        [Paragraph(text, ParagraphStyle(name="body", fontName="TestFont", fontSize=10))]
    )
    return buffer.getvalue()


def test_parse_llm_response_formats():
    from backend.services.task_generation import parse_llm_response

    plain = parse_llm_response(
        '{"statement": "Задача", "options": ["a", "b"], "reference_answer": 1}',
        "multiple_choice",
    )
    assert plain is not None
    assert plain.reference_answer == 1

    wrapped = parse_llm_response(
        '```json\n{"statement": "x", "options": [], "reference_answer": 0}\n```',
        "multiple_choice",
    )
    assert wrapped is not None
    assert wrapped.reference_answer == 0

    assert parse_llm_response("не json вообще", "multiple_choice") is None


def test_llm_task_generation(monkeypatch):
    import asyncio

    from backend.services import task_generation
    from backend.services.task_generation import llm_task

    monkeypatch.setattr(
        task_generation,
        "get_llm_client",
        lambda: FakeLLMClient(
            ['{"statement": "Задача от LLM", "options": ["a", "b"], "reference_answer": 1}']
        ),
    )

    concept = SimpleNamespace(
        id=1, name="Тестовый концепт", grade="middle", difficulty_params={}, task_format="multiple_choice"
    )

    draft = asyncio.run(llm_task(concept, "middle"))
    assert draft is not None
    assert draft.statement == "Задача от LLM"
    assert draft.reference_answer == 1


def test_llm_task_skipped_for_stub():
    import asyncio

    from backend.services.task_generation import llm_task

    concept = SimpleNamespace(
        id=1, name="Тестовый концепт", grade="middle", difficulty_params={}, task_format="multiple_choice"
    )

    assert asyncio.run(llm_task(concept, "middle")) is None


def test_session_uses_llm_draft(monkeypatch, client):
    from backend.api.routes import test_sessions
    from backend.db import SessionLocal

    class Draft:
        statement = "LLM-задача про концепт"
        task_format = "multiple_choice"
        options = ["верно", "неверно", "тоже нет", "мимо"]
        reference_answer = 0

    async def fake_llm_task(concept, grade):
        return Draft()

    monkeypatch.setattr(test_sessions, "llm_task", fake_llm_task)

    db = SessionLocal()
    seed_concept_bank(db)
    db.close()

    candidate_token = register_and_login(client, "llm-cand@example.com", "candidate")
    session = client.post("/test-sessions", json={"grade": "junior"}, headers=auth(candidate_token))
    assert session.status_code == 201
    tasks = session.json()["tasks"]
    assert len(tasks) == 5
    assert all(task["statement"] == "LLM-задача про концепт" for task in tasks)


def test_resume_parsing_applies_profile(monkeypatch, client):
    from backend.services import pdf_parser

    llm_response = (
        '{"full_name": "Парсер Резюмов", "contacts": {"email": "p@ex.com"}, '
        '"stack": ["go", "grpc"], "years_of_experience": 4, "soft_skills": ["пунктуальность"], '
        '"specialization": "backend"}'
    )
    monkeypatch.setattr(pdf_parser, "get_llm_client", lambda: FakeLLMClient([llm_response]))

    candidate_token = register_and_login(client, "resume-cand@example.com", "candidate")
    pdf_bytes = make_simple_pdf("Парсер Резюмов, go, grpc, 4 года")
    response = client.post(
        "/candidates/me/resume",
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
        headers=auth(candidate_token),
    )
    assert response.status_code == 200
    assert response.json()["applied"]["full_name"] == "Парсер Резюмов"

    profile = client.get("/candidates/me", headers=auth(candidate_token)).json()
    assert profile["full_name"] == "Парсер Резюмов"
    assert profile["stack"] == ["go", "grpc"]
    assert profile["specialization"] == "backend"


def test_confirmation_email_via_smtp(monkeypatch):
    import smtplib as smtplib_module

    from backend.services import email as email_service
    from backend.services.email import send_confirmation_email

    captured = {}

    class FakeSMTP:
        def __init__(self, host, port):
            captured["host"] = host

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            pass

        def login(self, user, password):
            captured["user"] = user

        def send_message(self, message):
            captured["subject"] = message["Subject"]

    monkeypatch.setattr(
        email_service,
        "get_settings",
        lambda: SimpleNamespace(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="noreply@example.com",
            smtp_password="secret",
            app_base_url="https://syntax.example.com",
        ),
    )
    monkeypatch.setattr(smtplib_module, "SMTP", FakeSMTP)

    assert send_confirmation_email("user@example.com", "token123") is True
    assert captured["host"] == "smtp.example.com"
    assert captured["user"] == "noreply@example.com"
    assert captured["subject"] == "Подтверждение регистрации syntax"


def test_profile_pdf_download(client):
    candidate_token = register_and_login(client, "pdf-cand@example.com", "candidate")
    client.put(
        "/candidates/me",
        json={"full_name": "Пдф Кандидатов", "specialization": "backend", "stack": ["python"]},
        headers=auth(candidate_token),
    )
    client.put("/candidates/me/grade", json={"grade": "junior"}, headers=auth(candidate_token))
    response = client.get("/candidates/me/profile.pdf", headers=auth(candidate_token))
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:5] == b"%PDF-"

    from pypdf import PdfReader

    reader = PdfReader(BytesIO(response.content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Пдф Кандидатов" in text
    assert "Специализация: Backend" in text
    assert "Грейд: не подтверждён" in text
    assert "Специализация: backend" not in text
    assert "Грейд: junior" not in text


def test_label_helpers_localize_enums_and_keep_unknown_values():
    assert specialization_label("backend") == "Backend"
    assert specialization_label("DEVOPS") == "DevOps"
    assert specialization_label(None) == ""
    assert specialization_label("mobile") == "Mobile"
    assert specialization_label("embedded") == "embedded"
    assert grade_label("junior") == "Junior"
    assert grade_label("SENIOR") == "Senior"
    assert grade_label(None) == ""
    assert grade_label("lead") == "lead"


def test_specialization_enum_matches_label_map():
    from typing import get_args

    from backend.core.labels import SPECIALIZATIONS, Specialization

    assert set(get_args(Specialization)) == set(SPECIALIZATIONS)
    assert set(SPECIALIZATION_LABELS) == set(SPECIALIZATIONS)


def test_profile_pdf_localizes_enums_and_does_not_duplicate_grade():
    from pypdf import PdfReader

    from backend.services.profile_pdf import build_profile_pdf

    profile = SimpleNamespace(
        id=7,
        full_name="Иван Тестов",
        specialization="frontend",
        grade="junior",
        stack=["vue"],
        years_of_experience=3,
        soft_skills=["командность"],
    )
    session = SimpleNamespace(
        grade="junior",
        correct_count=3,
        task_count=5,
        result_score=60,
        verdict="confirmed",
        completed_at=None,
    )
    pdf = build_profile_pdf(profile, [session], [])
    text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)
    assert "Специализация: Frontend" in text
    assert "Грейд: Junior" in text
    assert "Junior: 3/5 верно" in text
    assert "Грейд: junior" not in text
    assert "Грейд junior" not in text
