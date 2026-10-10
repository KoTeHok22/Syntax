import io
import json

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from backend.services.llm import StubLLMClient, get_llm_client

RESUME_PARSE_PROMPT = """Извлеки из резюме данные и верни строго JSON с ключами:
full_name (строка), contacts (объект с любыми найденными контактами),
stack (массив строк — технологии), years_of_experience (число),
soft_skills (массив строк), specialization (строка с профессиональным направлением, включая design).
Значение — null, если данных нет. Без markdown и пояснений.

Резюме:
{resume_text}"""

PROFILE_FIELDS = (
    "full_name",
    "contacts",
    "stack",
    "years_of_experience",
    "soft_skills",
    "specialization",
)


def extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parse_llm_fields(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return {key: data[key] for key in PROFILE_FIELDS if data.get(key) not in (None, "", [], {})}


async def parse_resume(file_bytes: bytes) -> dict:
    try:
        text = extract_pdf_text(file_bytes)
    except (PdfReadError, ValueError):
        return {"invalid_pdf": True}
    if not text.strip():
        return {"invalid_pdf": True}
    client = get_llm_client()
    if isinstance(client, StubLLMClient):
        return {"resume_chars": len(text), "resume_text": text[:12000]}
    try:
        raw = await client.complete(RESUME_PARSE_PROMPT.format(resume_text=text[:6000]))
    except Exception:
        raw = ""
    if not raw:
        return {"resume_chars": len(text), "resume_text": text[:12000]}
    return {**parse_llm_fields(raw), "resume_text": text[:12000]}
