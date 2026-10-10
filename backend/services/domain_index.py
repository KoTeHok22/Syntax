from sqlalchemy.orm import Session

from backend.core.domain_matching import rank_domains
from backend.models import Domain
from backend.services.embeddings import cosine_similarity, embed_texts, get_embedding_client
from backend.services.embeddings import StubEmbeddingClient

LEXICAL_WEIGHT = 0.6
VECTOR_WEIGHT = 0.4
VECTOR_THRESHOLD = 0.35


def domain_embedding_text(domain: Domain) -> str:
    parts = [domain.title, domain.slug.replace("-", " "), *list(domain.aliases or [])]
    return ". ".join(part for part in parts if part).strip()[:2000]


async def index_domain(domain: Domain) -> bool:
    text = domain_embedding_text(domain)
    if text == "":
        domain.embedding = None
        domain.embedding_text = None
        return False
    vectors = await embed_texts([text])
    if not vectors:
        return False
    domain.embedding = vectors[0]
    domain.embedding_text = text[:512]
    return True


async def index_domains(db: Session, domains: list[Domain]) -> int:
    if isinstance(get_embedding_client(), StubEmbeddingClient):
        return 0
    pending = [domain for domain in domains if domain.embedding is None or domain.embedding_text != domain_embedding_text(domain)[:512]]
    if not pending:
        return 0
    vectors = await embed_texts([domain_embedding_text(domain) for domain in pending])
    if not vectors:
        return 0
    for domain, vector in zip(pending, vectors):
        domain.embedding = vector
        domain.embedding_text = domain_embedding_text(domain)[:512]
    db.flush()
    return len(pending)


async def hybrid_domains(db: Session, query: str, limit: int = 12) -> list[tuple[Domain, float]]:
    domains = db.query(Domain).all()
    lexical = {domain.id: score for domain, score in rank_domains(query, domains)}
    client = get_embedding_client()
    if isinstance(client, StubEmbeddingClient):
        return [(domain, lexical.get(domain.id, 0.0)) for domain in domains if domain.id in lexical]
    query_vectors = await embed_texts([query])
    if not query_vectors:
        return [(domain, lexical.get(domain.id, 0.0)) for domain in domains if domain.id in lexical]
    query_vector = query_vectors[0]
    combined: dict[int, float] = {}
    for domain in domains:
        lexical_score = lexical.get(domain.id, 0.0)
        vector_score = 0.0
        embedding = domain.embedding
        if embedding is not None:
            raw = cosine_similarity(query_vector, list(embedding))
            vector_score = max(0.0, raw)
        if lexical_score == 0.0 and vector_score < VECTOR_THRESHOLD:
            continue
        combined[domain.id] = LEXICAL_WEIGHT * lexical_score + VECTOR_WEIGHT * vector_score
    if not combined:
        return [(domain, lexical.get(domain.id, 0.0)) for domain in domains if domain.id in lexical]
    by_id = {domain.id: domain for domain in domains}
    ranked = sorted(combined.items(), key=lambda item: item[1], reverse=True)
    return [(by_id[domain_id], score) for domain_id, score in ranked[:limit]]
