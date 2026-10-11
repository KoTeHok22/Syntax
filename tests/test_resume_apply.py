import asyncio

from backend.services import pdf_parser
from backend.services.pdf_parser import (
    SPECIALIZATIONS,
    canonical_enum_value,
    parse_resume,
    sanitize_parsed_fields,
)

from tests.test_api import auth, register_and_login

PROFILE_FIELD_NAMES = {
    "full_name",
    "contacts",
    "stack",
    "years_of_experience",
    "soft_skills",
    "specialization",
}

FRONTEND_RESUME = """Анна Смирнова
Frontend Developer

Контакты: anna.smirnova@example.com, +7 (999) 111-22-33

Опыт работы в разработке 4 года.

Навыки: React, TypeScript, Figma
"""


class _ScriptedLLMClient:
    def __init__(self, payload: str) -> None:
        self.payload = payload

    async def complete(self, prompt: str) -> str:
        return self.payload


def test_human_readable_specialization_is_canonical(monkeypatch):
    monkeypatch.setattr(pdf_parser, "get_llm_client", lambda: _ScriptedLLMClient('{"specialization": "Frontend"}'))
    monkeypatch.setattr(pdf_parser, "extract_pdf_text", lambda data: FRONTEND_RESUME)

    parsed = asyncio.run(parse_resume(b"pdf"))

    assert parsed["specialization"] == "frontend"


def test_specialization_labels_map_to_slugs():
    mapping = {
        "Frontend": "frontend",
        "Backend": "backend",
        "Data Science": "data",
        "Data": "data",
        "DevOps": "devops",
        "Mobile": "mobile",
        "QA": "qa",
        "Design": "design",
    }
    for raw, expected in mapping.items():
        assert canonical_enum_value("specialization", raw) == expected
        assert expected in SPECIALIZATIONS


def test_grade_labels_map_to_slugs():
    assert canonical_enum_value("grade", "Junior") == "junior"
    assert canonical_enum_value("grade", "Middle") == "middle"
    assert canonical_enum_value("grade", "Senior") == "senior"


def test_unrecognized_specialization_is_skipped():
    applied, skipped = sanitize_parsed_fields({"specialization": "Космический инженер"})

    assert "specialization" not in applied
    assert skipped["specialization"] == "не распознано значение"


def test_empty_values_do_not_overwrite():
    payload = {
        "full_name": "",
        "contacts": {},
        "stack": [],
        "years_of_experience": None,
        "soft_skills": [],
        "specialization": "",
    }
    applied, skipped = sanitize_parsed_fields(payload)

    assert applied == {}
    assert skipped == {}


def test_valid_fields_pass_through_sanitizer():
    payload = {
        "full_name": "Иван Петров",
        "contacts": {"email": "ivan@example.com"},
        "stack": ["python"],
        "years_of_experience": 6.0,
        "soft_skills": ["командная работа"],
        "specialization": "backend",
    }
    applied, skipped = sanitize_parsed_fields(payload)

    assert applied["full_name"] == "Иван Петров"
    assert applied["specialization"] == "backend"
    assert applied["years_of_experience"] == 6.0
    assert skipped == {}


def _upload_resume(client, headers, monkeypatch, payload: str):
    monkeypatch.setattr(pdf_parser, "get_llm_client", lambda: _ScriptedLLMClient(payload))
    monkeypatch.setattr(pdf_parser, "extract_pdf_text", lambda data: FRONTEND_RESUME)
    return client.post(
        "/candidates/me/resume",
        files={"file": ("resume.pdf", b"pdf", "application/pdf")},
        headers=headers,
    )


def test_resume_upload_keeps_profile_savable(client, monkeypatch):
    token = register_and_login(client, "resume-apply@example.com", "candidate")
    headers = auth(token)

    seeded = client.put(
        "/candidates/me",
        json={"full_name": "Анна Смирнова", "specialization": "frontend", "stack": ["react"]},
        headers=headers,
    )
    assert seeded.status_code == 200

    upload = _upload_resume(client, headers, monkeypatch, '{"specialization": "Frontend"}')
    assert upload.status_code == 200

    profile = client.get("/candidates/me", headers=headers).json()
    assert profile["specialization"] == "frontend"

    saved = client.put(
        "/candidates/me",
        json={"full_name": "Анна Смирнова", "specialization": profile["specialization"]},
        headers=headers,
    )
    assert saved.status_code == 200


def test_resume_upload_reports_applied_and_skipped(client, monkeypatch):
    token = register_and_login(client, "resume-report@example.com", "candidate")
    headers = auth(token)

    upload = _upload_resume(
        client,
        headers,
        monkeypatch,
        '{"specialization": "Frontend", "stack": ["react", "typescript"]}',
    )
    assert upload.status_code == 200
    body = upload.json()

    assert body["applied"]["specialization"] == "frontend"
    assert "react" in body["applied"]["stack"]
    assert set(body["applied"]).issubset(PROFILE_FIELD_NAMES)
    assert body["skipped"] == {}

    second = _upload_resume(
        client,
        headers,
        monkeypatch,
        '{"specialization": "Frontend", "stack": ["react", "typescript"]}',
    )
    assert second.status_code == 200
    assert second.json()["skipped"]["stack"] == "поле уже заполнено"


def test_fresh_profile_accepts_years_from_resume(client, monkeypatch):
    token = register_and_login(client, "resume-years@example.com", "candidate")
    headers = auth(token)

    upload = _upload_resume(client, headers, monkeypatch, '{"specialization": "Frontend"}')
    assert upload.status_code == 200

    profile = client.get("/candidates/me", headers=headers).json()
    assert profile["years_of_experience"] == 4.0


def test_unrecognized_specialization_never_reaches_profile(client, monkeypatch):
    token = register_and_login(client, "resume-unknown@example.com", "candidate")
    headers = auth(token)

    upload = _upload_resume(
        client,
        headers,
        monkeypatch,
        '{"specialization": "Космический инженер", "full_name": "Борис Годунов"}',
    )
    assert upload.status_code == 200
    body = upload.json()

    assert body["applied"].get("specialization") is None
    assert body["skipped"]["specialization"] == "не распознано значение"

    profile = client.get("/candidates/me", headers=headers).json()
    assert not profile["specialization"]

    saved = client.put(
        "/candidates/me",
        json={"full_name": profile["full_name"], "specialization": profile["specialization"]},
        headers=headers,
    )
    assert saved.status_code == 200
