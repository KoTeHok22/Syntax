import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.models import CandidateProfile, Vacancy
from backend.services.embeddings import cosine_similarity, embed_texts


def _skill_tokens(stack: list) -> set[str]:
    tokens: set[str] = set()
    for skill in stack or []:
        if not skill:
            continue
        for token in str(skill).replace(",", " ").split():
            cleaned = token.strip().casefold()
            if cleaned:
                tokens.add(cleaned)
    return tokens


def stack_intersection(candidate_stack: list, required_stack: list) -> float:
    required = _skill_tokens(required_stack)
    candidate = _skill_tokens(candidate_stack)
    return len(required & candidate) / len(required) if required else 1.0


def candidate_embedding_text(candidate: CandidateProfile) -> str:
    parts = [candidate.specialization or "", " ".join(candidate.stack or []),
             " ".join(candidate.soft_skills or []), candidate.resume_text or "", candidate.assessment_text or ""]
    return "\n".join(part.strip() for part in parts if part.strip())[:16000]


def vacancy_embedding_text(vacancy: Vacancy) -> str:
    return "\n".join([vacancy.title, vacancy.description or "", vacancy.specialization or "",
                      " ".join(vacancy.stack or [])]).strip()[:16000]


def rerank_documents(candidate: CandidateProfile) -> list[str]:
    return [candidate.specialization or "", " ".join(candidate.stack or []), " ".join(candidate.soft_skills or []),
            (candidate.resume_text or "")[:2000], (candidate.assessment_text or "")[:1200]]


def normalize_rerank_scores(scores: list[float]) -> list[float]:
    if not scores:
        return []
    lowest = min(scores)
    highest = max(scores)
    if highest - lowest < 1e-9:
        return [1.0 if highest > 0 else 0.0 for _ in scores]
    return [(score - lowest) / (highest - lowest) for score in scores]


def valid_vector(vector) -> bool:
    try:
        return len(vector) == 1024 and all(math.isfinite(float(value)) for value in vector) and any(vector)
    except (TypeError, ValueError, OverflowError):
        return False


def embedding_is_current(entity, text: str) -> bool:
    settings = get_settings()
    return (settings.embeddings_enabled and entity.embedding_model == settings.embedding_model
            and entity.embedding_text == text and valid_vector(entity.embedding))


async def index_entities(entities: list, texts: list[str]) -> int:
    settings = get_settings()
    pending = []
    for entity, text in zip(entities, texts):
        if embedding_is_current(entity, text):
            continue
        entity.embedding = None
        entity.embedding_text = None
        entity.embedding_model = None
        if text and settings.embeddings_enabled and settings.embedding_dimensions == 1024:
            pending.append((entity, text))
    if not pending:
        return 0
    vectors = await embed_texts([text for _, text in pending])
    if len(vectors) != len(pending) or not all(valid_vector(vector) for vector in vectors):
        return 0
    for (entity, text), vector in zip(pending, vectors):
        entity.embedding = vector
        entity.embedding_text = text
        entity.embedding_model = settings.embedding_model
    return len(pending)


async def index_vacancy(vacancy: Vacancy) -> bool:
    return bool(await index_entities([vacancy], [vacancy_embedding_text(vacancy)]))


async def index_candidate(candidate: CandidateProfile) -> bool:
    return bool(await index_entities([candidate], [candidate_embedding_text(candidate)]))


async def vacancy_similarities(db: Session, vacancy: Vacancy, candidates: list[CandidateProfile]) -> dict[int, float]:
    await index_vacancy(vacancy)
    await index_entities(candidates, [candidate_embedding_text(candidate) for candidate in candidates])
    db.flush()
    if not embedding_is_current(vacancy, vacancy_embedding_text(vacancy)):
        return {}
    eligible = [candidate for candidate in candidates if embedding_is_current(candidate, candidate_embedding_text(candidate))]
    if not eligible:
        return {}
    if db.bind.dialect.name == "postgresql":
        similarity = (1 - CandidateProfile.embedding.cosine_distance(list(vacancy.embedding))).label("similarity")
        rows = db.execute(select(CandidateProfile.id, similarity).where(
            CandidateProfile.id.in_([candidate.id for candidate in eligible])))
        return {candidate_id: max(0.0, min(1.0, float(score))) for candidate_id, score in rows if score is not None}
    return {candidate.id: max(0.0, min(1.0, cosine_similarity(list(vacancy.embedding), list(candidate.embedding))))
            for candidate in eligible}


def rerank_documents(candidate: CandidateProfile) -> list[str]:
    return [candidate.specialization or "", " ".join(candidate.stack or []), " ".join(candidate.soft_skills or []),
            (candidate.resume_text or "")[:2000], (candidate.assessment_text or "")[:1200]]


def normalize_rerank_scores(scores: list[float]) -> list[float]:
    if not scores:
        return []
    lowest = min(scores)
    highest = max(scores)
    if highest - lowest < 1e-9:
        return [1.0 if highest > 0 else 0.0 for _ in scores]
    return [(score - lowest) / (highest - lowest) for score in scores]


def relevance_breakdown(candidate_stack: list, required_stack: list, semantic_similarity: float | None = None) -> dict:
    stack = stack_intersection(candidate_stack, required_stack)
    semantic = semantic_similarity if semantic_similarity is not None and math.isfinite(semantic_similarity) else None
    if semantic is not None:
        semantic = max(0.0, min(1.0, semantic))
    relevance = 0.3 * stack + 0.7 * semantic if semantic is not None else stack
    return {"stack": stack, "semantic": semantic, "mode": "semantic" if semantic is not None else "lexical",
            "stack_weight": 0.3 if semantic is not None else 1.0,
            "semantic_weight": 0.7 if semantic is not None else 0.0, "relevance": relevance}
