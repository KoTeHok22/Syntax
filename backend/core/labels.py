from typing import Literal

VERDICT_LABELS = {
    "confirmed": "Грейд подтверждён",
    "suggest_higher": "Рекомендован грейд выше",
    "suggest_lower": "Рекомендован грейд ниже",
}

SPECIALIZATION_LABELS = {
    "backend": "Backend",
    "frontend": "Frontend",
    "data": "Data",
    "devops": "DevOps",
    "mobile": "Mobile",
    "qa": "QA",
    "design": "Дизайн",
}

SPECIALIZATIONS = tuple(SPECIALIZATION_LABELS)
Specialization = Literal["backend", "frontend", "data", "devops", "mobile", "qa", "design"]

SPECIALIZATION_DOMAINS: dict[str, tuple[str, ...]] = {
    "backend": ("backend", "databases", "algorithms"),
    "frontend": ("frontend", "algorithms"),
    "data": ("databases", "algorithms"),
    "devops": ("devops", "algorithms"),
    "mobile": ("algorithms", "frontend"),
    "qa": ("algorithms", "backend"),
    "design": ("design",),
}


def concept_domains_for_specialization(specialization: str | None) -> tuple[str, ...]:
    if not specialization:
        return ()
    return SPECIALIZATION_DOMAINS.get(specialization.strip().lower(), ())

GRADE_LABELS = {
    "junior": "Junior",
    "middle": "Middle",
    "senior": "Senior",
}


def verdict_label(verdict: str | None) -> str:
    if verdict is None:
        return "нет"
    return VERDICT_LABELS.get(verdict, verdict)


def specialization_label(value: str | None) -> str:
    if not value:
        return ""
    return SPECIALIZATION_LABELS.get(value.lower(), value)


def grade_label(value: str | None) -> str:
    if not value:
        return ""
    return GRADE_LABELS.get(value.lower(), value)


def pluralize_years(value: float) -> str:
    count = abs(value)
    if count != int(count):
        return "года"
    number = int(count)
    mod100 = number % 100
    mod10 = number % 10
    if 11 <= mod100 <= 14:
        return "лет"
    if mod10 == 1:
        return "год"
    if 2 <= mod10 <= 4:
        return "года"
    return "лет"


def format_years(value: float) -> str:
    if value == int(value):
        return f"{int(value)} {pluralize_years(value)}"
    return f"{value:g} {pluralize_years(value)}"


def format_date(value) -> str:
    if value is None:
        return "—"
    return value.strftime("%d.%m.%Y")
