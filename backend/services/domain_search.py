import json

from openai import OpenAIError
from sqlalchemy.orm import Session

from backend.core.domain_matching import canonical_key, nearest_domain, normalize, rank_domains
from backend.models import Domain
from backend.services.llm import StubLLMClient, get_llm_client
from backend.services.prompts import get_prompt, render

QUERY_EXPANSION_PROMPT = """Ты помогаешь искать специалистов по направлениям в IT.
Запрос работодателя: "{query}".
Верни JSON-массив из 5–10 коротких терминов на русском и английском, которые описывают
то же направление или близкие технологии и синонимы (например: "база данных" → "СУБД", "postgres",
"sql", "хранилище данных", "информационная система"). Только термины, без пояснений.
Ответ — строго валидный JSON-массив строк."""


async def expand_query_terms(query: str) -> list[str]:
    client = get_llm_client()
    if isinstance(client, StubLLMClient):
        return []
    try:
        raw = await client.complete(render(get_prompt("query_expansion", QUERY_EXPANSION_PROMPT), query=query))
    except OpenAIError:
        return []
    except Exception:
        return []
    if not raw:
        return []
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    return [str(item).strip() for item in data if isinstance(item, str) and item.strip()]


def all_domains(db: Session) -> list[Domain]:
    return db.query(Domain).order_by(Domain.slug).all()


def ensure_domain(db: Session, value: str, title: str | None = None) -> Domain | None:
    label = (title or value or "").strip()
    if label == "":
        return None
    existing = nearest_domain(label, all_domains(db), threshold=0.62)
    if existing is not None:
        return existing
    slug = canonical_key(label)
    if slug == "":
        return None
    found = db.query(Domain).filter(Domain.slug == slug).first()
    if found is not None:
        return found
    domain = Domain(slug=slug, title=label[:128], aliases=[], is_curated=False)
    db.add(domain)
    db.flush()
    return domain


async def search_domains(db: Session, query: str, limit: int = 12) -> list[tuple[Domain, float]]:
    from backend.services.domain_index import hybrid_domains

    clean = query.strip()
    if clean == "":
        return [(domain, 1.0) for domain in all_domains(db)[:limit]]
    hybrid = await hybrid_domains(db, clean, limit=limit)
    if hybrid:
        return hybrid
    domains = all_domains(db)
    ranked = rank_domains(clean, domains)
    if ranked:
        return ranked[:limit]
    expanded = await expand_query_terms(clean)
    if not expanded:
        return []
    combined: dict[int, tuple[Domain, float]] = {}
    for term in [clean, *expanded]:
        for domain, score in rank_domains(term, domains, threshold=0.55):
            previous = combined.get(domain.id)
            if previous is None or score > previous[1]:
                combined[domain.id] = (domain, score)
    ordered = sorted(combined.values(), key=lambda item: item[1], reverse=True)
    return ordered[:limit]


def normalize_text(value: str) -> str:
    return normalize(value)
