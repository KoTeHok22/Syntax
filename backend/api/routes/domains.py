from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.deps import get_db, require_employer
from backend.api.routes.candidates import domain_candidate_counts, visible_candidates
from backend.core.domain_matching import canonical_key, nearest_domain
from backend.models import Domain
from backend.schemas.matching import DomainCreate, DomainPage, DomainResponse
from backend.services.domain_search import all_domains, search_domains

router = APIRouter()


def to_response(domain: Domain, count: int, score: float = 1.0) -> DomainResponse:
    return DomainResponse(
        id=domain.id,
        slug=domain.slug,
        title=domain.title,
        aliases=list(domain.aliases or []),
        candidate_count=count,
        score=round(score, 3),
    )


@router.get("/domains", response_model=DomainPage)
async def list_domains(
    q: str | None = Query(default=None, max_length=64),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(require_employer),
):
    counts = domain_candidate_counts(db)
    if q is not None and q.strip():
        ranked = await search_domains(db, q.strip(), limit=skip + limit)
        window = ranked[skip : skip + limit]
        return DomainPage(
            total=len(ranked),
            items=[to_response(domain, counts.get(domain.id, 0), score) for domain, score in window],
        )
    domains = [domain for domain in all_domains(db) if counts.get(domain.id, 0) > 0 or domain.is_curated]
    domains.sort(key=lambda domain: (counts.get(domain.id, 0) == 0, domain.title.lower()))
    window = domains[skip : skip + limit]
    return DomainPage(
        total=len(domains),
        items=[to_response(domain, counts.get(domain.id, 0)) for domain in window],
    )


@router.post("/domains", response_model=DomainResponse, status_code=status.HTTP_201_CREATED)
async def create_domain(
    request: DomainCreate,
    db: Session = Depends(get_db),
    user=Depends(require_employer),
):
    title = request.title.strip()
    if title == "":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Укажите название направления")
    domain = nearest_domain(title, all_domains(db), threshold=0.72)
    if domain is None:
        slug = canonical_key(title)
        domain = db.query(Domain).filter(Domain.slug == slug).first()
        if domain is None:
            domain = Domain(slug=slug, title=title[:128], aliases=[], is_curated=False)
            db.add(domain)
            db.flush()
    aliases = list(domain.aliases or [])
    for alias in request.aliases:
        cleaned = alias.strip()
        if cleaned and cleaned not in aliases:
            aliases.append(cleaned)
    domain.aliases = aliases
    db.flush()
    from backend.services.domain_index import index_domain

    await index_domain(domain)
    db.commit()
    db.refresh(domain)
    counts = domain_candidate_counts(db)
    return to_response(domain, counts.get(domain.id, 0))
