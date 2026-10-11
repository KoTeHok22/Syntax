import asyncio

import pytest

from backend.services import pdf_parser
from backend.services.llm import StubLLMClient
from backend.services.pdf_parser import (
    PROFILE_FIELDS,
    parse_resume,
    parse_text_fields,
)

RESUME_TEXT = """Иван Петров
Python Backend Developer

Контакты: ivan.petrov@example.com, +7 (912) 345-67-89, Москва
Telegram: @ivan_dev

Опыт работы
Опыт работы в разработке 6 лет.

Навыки: Python, Django, FastAPI, PostgreSQL, Docker, Kubernetes, Git, Linux, Redis

Личные качества: командная работа, ответственность, самостоятельность, быстро обучаюсь.
"""


class _FailLLMClient:
    async def complete(self, prompt: str) -> str:
        raise RuntimeError("llm недоступен")


def test_fallback_extracts_core_fields_without_llm(monkeypatch):
    monkeypatch.setattr(pdf_parser, "get_llm_client", lambda: StubLLMClient())
    monkeypatch.setattr(pdf_parser, "extract_pdf_text", lambda data: RESUME_TEXT)

    parsed = asyncio.run(parse_resume(b"pdf"))

    assert parsed.get("invalid_pdf") is not True
    assert parsed.get("stack")


def test_parse_text_fields_extracts_email_stack_years():
    fields = parse_text_fields(RESUME_TEXT)

    assert fields["contacts"]["email"] == "ivan.petrov@example.com"
    assert "python" in fields["stack"]
    assert "django" in fields["stack"]
    assert "postgresql" in fields["stack"]
    assert "docker" in fields["stack"]
    assert fields["years_of_experience"] == 6
    assert fields["full_name"] == "Иван Петров"
    assert "командная работа" in fields["soft_skills"]


def test_all_applied_fields_are_known_profile_fields():
    fields = parse_text_fields(RESUME_TEXT)
    assert set(fields).issubset(set(PROFILE_FIELDS))


def test_parse_resume_fallback_used_when_llm_raises(monkeypatch):
    monkeypatch.setattr(pdf_parser, "get_llm_client", lambda: _FailLLMClient())
    monkeypatch.setattr(pdf_parser, "extract_pdf_text", lambda data: RESUME_TEXT)

    parsed = asyncio.run(parse_resume(b"pdf"))

    applied = {key: value for key, value in parsed.items() if key in PROFILE_FIELDS}
    assert applied
    assert applied["contacts"]["email"] == "ivan.petrov@example.com"
    assert "python" in applied["stack"]
    assert applied["years_of_experience"] == 6
    assert applied["specialization"] == "backend"
    assert parsed["resume_text"] == RESUME_TEXT[:12000]


def test_parse_resume_fallback_used_when_llm_returns_empty(monkeypatch):
    monkeypatch.setattr(pdf_parser, "get_llm_client", lambda: StubLLMClient())
    monkeypatch.setattr(pdf_parser, "extract_pdf_text", lambda data: RESUME_TEXT)

    parsed = asyncio.run(parse_resume(b"pdf"))

    applied = {key: value for key, value in parsed.items() if key in PROFILE_FIELDS}
    assert applied.get("stack")
    assert applied.get("years_of_experience") == 6


def test_empty_pdf_still_invalid():
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(pdf_parser, "extract_pdf_text", lambda data: "   ")
    try:
        assert asyncio.run(parse_resume(b"pdf")) == {"invalid_pdf": True}
    finally:
        monkeypatch.undo()
