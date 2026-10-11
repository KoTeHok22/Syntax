import io
import json
import re

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from backend.core.domain_seed import CURATED_DOMAINS
from backend.core.labels import SPECIALIZATION_LABELS
from backend.services.llm import StubLLMClient, get_llm_client
from backend.services.prompts import get_prompt, render

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

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(
    r"(?:\+7|8|7)[\s\-().]*\d{3}[\s\-().]*\d{3}[\s\-().]*\d{2}[\s\-().]*\d{2}\b"
)
PHONE_FALLBACK_RE = re.compile(r"\+?\d[\d\s\-().]{9,}\d")
NAME_LINE_RE = re.compile(r"^[А-ЯЁA-Z][а-яёa-z\-]+(?:\s+[А-ЯЁA-Z][а-яёa-z\-]+){1,2}$")
EXPERIENCE_RE = re.compile(
    r"(?P<years>\d{1,2})\s*(?:\+)?\s*(?:года|год|лет|years?|yrs?)\b", re.IGNORECASE
)
EXPERIENCE_LABEL_RE = re.compile(
    r"опыт[^\n]{0,40}?(?P<years>\d{1,2})", re.IGNORECASE
)

TECH_ALIASES: dict[str, tuple[str, ...]] = {
    "python": ("python", "питон", "пайтон"),
    "django": ("django", "джанго"),
    "fastapi": ("fastapi", "фастапи"),
    "flask": ("flask",),
    "pytest": ("pytest", "питест"),
    "javascript": ("javascript", "js", "джаваскрипт"),
    "typescript": ("typescript", "ts", "тайпскрипт"),
    "react": ("react", "react.js", "reactjs", "реакт"),
    "vue": ("vue", "vue.js", "vuejs", "вью"),
    "angular": ("angular", "ангуляр"),
    "node.js": ("node.js", "nodejs", "node js", "нода"),
    "java": ("java", "джава"),
    "kotlin": ("kotlin", "котлин"),
    "swift": ("swift", "свифт"),
    "go": ("golang", "go"),
    "rust": ("rust", "раст"),
    "c#": ("c#", "csharp", ".net"),
    "c++": ("c++", "cpp"),
    "php": ("php",),
    "1c": ("1с", "1c"),
    "sql": ("sql", "скл"),
    "postgresql": ("postgresql", "postgres", "постгрес"),
    "mysql": ("mysql", "майсиквел"),
    "mongodb": ("mongodb", "mongo"),
    "clickhouse": ("clickhouse", "кликхаус"),
    "redis": ("redis", "редис"),
    "docker": ("docker", "докер"),
    "kubernetes": ("kubernetes", "k8s", "кубернетес"),
    "git": ("git", "гит"),
    "linux": ("linux", "линукс", "unix"),
    "ci/cd": ("ci/cd", "ci cd", "cicd"),
    "terraform": ("terraform", "терраформ"),
    "kafka": ("kafka", "кафка"),
    "spark": ("spark", "спарк"),
    "airflow": ("airflow",),
    "pandas": ("pandas", "пандас"),
    "numpy": ("numpy", "намп"),
    "pytorch": ("pytorch", "пайторч"),
    "tensorflow": ("tensorflow", "тензорфлоу"),
    "figma": ("figma", "фигма"),
    "sketch": ("sketch",),
    "photoshop": ("photoshop", "фотошоп"),
    "selenium": ("selenium", "селениум"),
}

SPECIALIZATION_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("devops", ("devops", "девопс", "sre", "kubernetes", "docker", "ci/cd", "инфраструктура")),
    ("mobile", ("android", "ios", "kotlin", "swift", "мобильн", "мобильная разработка")),
    ("frontend", ("frontend", "фронтенд", "верстка", "react", "vue", "angular", "javascript", "typescript")),
    ("data", ("data scientist", "дата саентист", "машинное обучение", "ml engineer", "аналитик данных", "data analyst")),
    ("qa", ("qa", "тестировщик", "тестирование", "автотесты", "quality assurance")),
    ("design", ("дизайнер", "designer", "ux", "ui дизайн", "продуктовый дизайн", "figma")),
    ("backend", ("backend", "бэкенд", "серверн", "api", "django", "fastapi", "spring")),
)

SOFT_SKILL_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("командная работа", ("командная работа", "работа в команде", "команде", "teamwork", "командный")),
    ("коммуникабельность", ("коммуникабельн", "коммуникац", "communication")),
    ("ответственность", ("ответственн", "responsib")),
    ("пунктуальность", ("пунктуальн", "punctual")),
    ("инициативность", ("инициативн", "проактивн", "proactiv", "initiative")),
    ("самостоятельность", ("самостоятельн", "self-motivated", "самообуч")),
    ("стрессоустойчивость", ("стрессоустойчив", "стрессоустойч")),
    ("аналитическое мышление", ("аналитическое мышление", "аналитич", "analytical")),
    ("креативность", ("креативн", "creativ")),
    ("обучаемость", ("обучаем", "быстро обуча", "fast learner")),
    ("лидерство", ("лидерств", "leadership")),
    ("наставничество", ("наставнич", "менторств", "mentor")),
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


def _extract_email(text: str) -> str | None:
    match = EMAIL_RE.search(text)
    return match.group(0) if match else None


def _extract_phone(text: str) -> str | None:
    match = PHONE_RE.search(text)
    if match:
        return match.group(0).strip()
    match = PHONE_FALLBACK_RE.search(text)
    if match:
        digits = re.sub(r"\D", "", match.group(0))
        if 10 <= len(digits) <= 12:
            return match.group(0).strip()
    return None


def _extract_full_name(text: str, lines: list[str], email: str | None) -> str | None:
    for line in lines[:6]:
        candidate = line.strip()
        if not candidate or "@" in candidate or any(char.isdigit() for char in candidate):
            continue
        words = candidate.split()
        if 2 <= len(words) <= 3 and NAME_LINE_RE.match(candidate):
            return candidate
    match = re.search(r"(?:ФИО|Имя)[:\s]+([А-ЯЁ][а-яё\-]+(?:\s+[А-ЯЁ][а-яё\-]+){1,2})", text)
    if match:
        return match.group(1).strip()
    if email:
        local = re.split(r"[._\-+]", email.split("@", 1)[0])[0]
        if local.isalpha() and len(local) >= 3:
            return local.capitalize()
    return None


def _extract_years(text: str) -> float | None:
    for regex in (EXPERIENCE_LABEL_RE, EXPERIENCE_RE):
        match = regex.search(text)
        if match:
            years = float(match.group("years"))
            if 0 < years <= 50:
                return years
    return None


def _normalize_for_match(text: str) -> str:
    lowered = text.lower().replace("ё", "е")
    return re.sub(r"[^a-zа-я0-9+#./\s]", " ", lowered)


def _has_alias(haystack: str, alias: str) -> bool:
    alias = alias.lower().replace("ё", "е")
    if alias and re.search(r"[\w]", alias[0]):
        pattern = r"(?<![\w])" + re.escape(alias) + r"(?![\w])"
    else:
        pattern = r"(?<![\w])" + re.escape(alias)
    return re.search(pattern, haystack) is not None


def _extract_stack(normalized: str) -> list[str]:
    domains = {
        alias.lower()
        for _, _, aliases in CURATED_DOMAINS
        for alias in aliases
    }
    found: list[str] = []
    for canonical, aliases in TECH_ALIASES.items():
        for alias in aliases:
            if _has_alias(normalized, alias) or (alias in domains and _has_alias(normalized, alias)):
                found.append(canonical)
                break
    for _, _, aliases in CURATED_DOMAINS:
        for alias in aliases:
            if _has_alias(normalized, alias) and alias not in found:
                found.append(alias)
    return found


def _extract_specialization(normalized: str, stack: list[str]) -> str | None:
    role_haystack = " ".join(normalized.split()[:12])
    for slug, keywords in SPECIALIZATION_KEYWORDS:
        if any(_has_alias(role_haystack, keyword) for keyword in keywords):
            return slug
    stack_haystack = " ".join(stack).lower()
    for slug, keywords in SPECIALIZATION_KEYWORDS:
        if any(_has_alias(stack_haystack, keyword) for keyword in keywords):
            return slug
    for slug, label in SPECIALIZATION_LABELS.items():
        if _has_alias(normalized, label.lower()):
            return slug
    return None


def _extract_soft_skills(normalized: str) -> list[str]:
    found: list[str] = []
    for canonical, keywords in SOFT_SKILL_KEYWORDS:
        if any(_has_alias(normalized, keyword) for keyword in keywords):
            found.append(canonical)
    return found


def parse_text_fields(text: str) -> dict:
    lines = [line for line in text.splitlines() if line.strip()]
    normalized = _normalize_for_match(text)
    email = _extract_email(text)
    phone = _extract_phone(text)
    contacts = {}
    if email:
        contacts["email"] = email
    if phone:
        contacts["phone"] = phone
    full_name = _extract_full_name(text, lines, email)
    stack = _extract_stack(normalized)
    years = _extract_years(text)
    soft_skills = _extract_soft_skills(normalized)
    specialization = _extract_specialization(normalized, stack)
    fields = {
        "full_name": full_name,
        "contacts": contacts,
        "stack": stack,
        "years_of_experience": years,
        "soft_skills": soft_skills,
        "specialization": specialization,
    }
    return {key: value for key, value in fields.items() if value not in (None, "", [], {})}


async def parse_resume(file_bytes: bytes) -> dict:
    try:
        text = extract_pdf_text(file_bytes)
    except (PdfReadError, ValueError):
        return {"invalid_pdf": True}
    if not text.strip():
        return {"invalid_pdf": True}
    client = get_llm_client()
    fallback = parse_text_fields(text)
    if isinstance(client, StubLLMClient):
        return {**fallback, "resume_chars": len(text), "resume_text": text[:12000]}
    try:
        raw = await client.complete(render(get_prompt("resume_parse", RESUME_PARSE_PROMPT), resume_text=text[:6000]))
    except Exception:
        raw = ""
    if not raw:
        return {**fallback, "resume_chars": len(text), "resume_text": text[:12000]}
    return {**fallback, **parse_llm_fields(raw), "resume_text": text[:12000]}
