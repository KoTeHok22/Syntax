from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.deps import get_db, require_employer
from backend.core.config import get_settings
from backend.core.demo_filter import is_demo_visible
from backend.core.scoring import (
    ScoreComponents,
    compute_score,
    has_pvn_history,
    profile_completeness,
)
from backend.models import (
    CandidateProfile,
    PvnAchievement,
    TestSession,
    User,
    Vacancy,
    EmployerProfile,
)
from backend.schemas.matching import CandidateCardResponse
from backend.services.reranking import rerank_enabled
from backend.services.semantic_matching import relevance_breakdown, stack_intersection, vacancy_similarities

router = APIRouter()


def visible_candidates(db: Session) -> list[CandidateProfile]:
    rows = (
        db.query(CandidateProfile, User)
        .join(User, CandidateProfile.user_id == User.id)
        .filter(CandidateProfile.is_visible == True)
        .all()
    )
    return [profile for profile, user in rows if is_demo_visible(user.email)]


def build_components(candidate: CandidateProfile, achievements, latest_session) -> ScoreComponents:
    pvn_score = None
    if achievements:
        pvn_score = min(100.0, sum(a.score for a in achievements))
    test_score = latest_session.result_score if latest_session else 0.0
    return ScoreComponents(
        test_score=test_score,
        pvn_achievements=pvn_score,
        profile_completeness=profile_completeness(candidate),
    )


def match_relevance(candidate_stack: list, required_stack: list) -> float:
    return stack_intersection(candidate_stack, required_stack)


def verified_pvn_ids(db: Session, candidates: list[CandidateProfile]) -> dict[int, str]:
    user_ids = {candidate.user_id for candidate in candidates}
    if not user_ids:
        return {}
    rows = db.query(User.id, User.pvn_id).filter(User.id.in_(user_ids), User.pvn_id.isnot(None)).all()
    return {user_id: pvn_id for user_id, pvn_id in rows if pvn_id}


def build_card(
    db: Session,
    candidate: CandidateProfile,
    required_stack: list,
    semantic_similarity: float | None = None,
    pvn_id: str | None = None,
) -> CandidateCardResponse:
    achievements = (
        db.query(PvnAchievement)
        .filter(PvnAchievement.candidate_profile_id == candidate.id)
        .all()
    )
    latest_session = (
        db.query(TestSession)
        .filter(
            TestSession.candidate_profile_id == candidate.id,
            TestSession.status == "completed",
        )
        .order_by(TestSession.completed_at.desc())
        .first()
    )
    components = build_components(candidate, achievements, latest_session)
    score, breakdown = compute_score(components)
    match = relevance_breakdown(candidate.stack, required_stack, semantic_similarity)
    relevance = match["relevance"]
    return CandidateCardResponse(
        candidate_profile_id=candidate.id,
        grade=candidate.grade,
        specialization=candidate.specialization,
        stack=candidate.stack,
        score=score,
        score_breakdown=breakdown,
        has_pvn_history=has_pvn_history(components),
        is_pvn_verified=pvn_id is not None,
        pvn_achievements=[
            {"type": a.achievement_type, "level": a.level, "date": a.achieved_at.isoformat(), "score": a.score}
            for a in achievements
        ],
        match_relevance=round(relevance, 4),
        final_score=round(score * relevance, 2),
        match_breakdown=match,
    )


def domain_candidate_counts(db: Session) -> dict[int, int]:
    from backend.core.domain_matching import domain_matches_candidate
    from backend.models import Domain

    domains = db.query(Domain).all()
    counts: dict[int, int] = {}
    for domain in domains:
        counts[domain.id] = 0
    for candidate in visible_candidates(db):
        for domain in domains:
            if domain_matches_candidate(domain, candidate.specialization, candidate.stack):
                counts[domain.id] = counts.get(domain.id, 0) + 1
    return counts


async def apply_rerank(query: str, candidates: list) -> list:
    from backend.services.reranking import rerank
    from backend.services.semantic_matching import normalize_rerank_scores, rerank_documents

    if not rerank_enabled():
        return candidates
    top_n = get_settings().rerank_top_n
    head = list(candidates[:top_n])
    tail = list(candidates[top_n:])
    documents = [" \n".join(part for part in rerank_documents(candidate) if part) for candidate in head]
    ranked = await rerank(query, documents, top_n=len(head))
    if not ranked:
        return None
    order = {index: score for index, score in ranked}
    indexed = list(enumerate(head))
    indexed.sort(key=lambda item: order.get(item[0], 0.0), reverse=True)
    return [candidate for _, candidate in indexed] + tail


def apply_card_filters(cards: list, has_pvn: bool | None, min_score: float | None, verified_only: bool | None = None) -> list:
    filtered = cards
    if has_pvn is not None:
        filtered = [c for c in filtered if c.has_pvn_history == has_pvn]
    if verified_only is not None:
        filtered = [c for c in filtered if c.is_pvn_verified == verified_only]
    if min_score is not None:
        filtered = [c for c in filtered if c.score >= min_score]
    return filtered


def stack_matches(candidate_stack: list, required_stack: list) -> bool:
    if not required_stack:
        return True
    candidate = [s.strip().lower() for s in (candidate_stack or []) if s and s.strip()]
    for required in required_stack:
        for token in str(required).replace(",", " ").split():
            token = token.strip().lower()
            if token == '':
                continue
            if any(token in skill or skill in token for skill in candidate):
                return True
    return False


@router.get("/categories/{category_id}/cards", response_model=list[CandidateCardResponse])
def list_category_cards(
    category_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_employer),
    stack: list[str] | None = Query(default=None),
    has_pvn: bool | None = Query(default=None),
    verified_only: bool | None = Query(default=None),
    min_score: float | None = Query(default=None, ge=0, le=100),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    from backend.models import Category

    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Категория не найдена")
    candidates = [c for c in visible_candidates(db) if c.category_id == category_id]
    if stack:
        candidates = [c for c in candidates if stack_matches(c.stack, stack)]
    verified = verified_pvn_ids(db, candidates)
    cards = apply_card_filters(
        [build_card(db, c, stack or [], pvn_id=verified.get(c.user_id)) for c in candidates],
        has_pvn,
        min_score,
        verified_only,
    )
    cards.sort(key=lambda card: (card.final_score, card.score), reverse=True)
    return cards[skip : skip + limit]


@router.get("/search", response_model=list[CandidateCardResponse])
async def search_candidates(
    db: Session = Depends(get_db),
    user: User = Depends(require_employer),
    q: str | None = Query(default=None, max_length=128),
    vacancy_id: int | None = Query(default=None, ge=1),
    specialization: str | None = Query(default=None),
    grade: str | None = Query(default=None),
    stack: list[str] | None = Query(default=None),
    has_pvn: bool | None = Query(default=None),
    verified_only: bool | None = Query(default=None),
    min_score: float | None = Query(default=None, ge=0, le=100),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    from backend.core.domain_matching import domain_matches_candidate, nearest_domain
    from backend.models import Domain
    from backend.services.domain_search import search_domains

    candidates = visible_candidates(db)
    vacancy = None
    similarities = {}
    if vacancy_id is not None:
        vacancy = db.get(Vacancy, vacancy_id)
        employer = db.query(EmployerProfile).filter(EmployerProfile.user_id == user.id).first()
        if vacancy is None or employer is None or vacancy.employer_profile_id != employer.id:
            raise HTTPException(status_code=404, detail="Вакансия не найдена")
    if specialization is not None:
        token = specialization.strip()
        matched = nearest_domain(token, db.query(Domain).all(), threshold=0.9)
        if matched is not None:
            candidates = [c for c in candidates if domain_matches_candidate(matched, c.specialization, c.stack)]
        else:
            lowered = token.lower()
            candidates = [c for c in candidates if lowered in (c.specialization or "").lower()]
    if grade is not None:
        token = grade.strip().lower()
        candidates = [c for c in candidates if (c.grade or "").lower() == token]
    if q is not None and q.strip():
        from backend.core.domain_matching import domain_matches_candidate, terms_match_query

        ranked = await search_domains(db, q.strip(), limit=5)
        best = ranked[0][1] if ranked else 0.0
        cutoff = max(best - 0.2, 0.45)
        strong = [domain for domain, score in ranked if score >= cutoff]
        terms = [q.strip()]
        for domain in strong:
            terms.extend(alias for alias in (domain.aliases or []) if len(alias.strip()) >= 4)
            terms.append(domain.title)
        if strong:
            candidates = [c for c in candidates if any(domain_matches_candidate(domain, c.specialization, c.stack) for domain in strong)]
        else:
            candidates = [
                c
                for c in candidates
                if terms_match_query(c.specialization or "", terms, threshold=0.62)
                or any(terms_match_query(skill, terms, threshold=0.7) for skill in (c.stack or []))
            ]

    reranked = False
    if stack:
        candidates = [c for c in candidates if stack_matches(c.stack, stack)]
    if vacancy is not None:
        similarities = await vacancy_similarities(db, vacancy, candidates)
        db.commit()
    if q is not None and q.strip() and candidates:
        reranked_order = await apply_rerank(q.strip(), candidates)
        reranked = reranked_order is not None
        if reranked_order is not None:
            candidates = reranked_order
    verified = verified_pvn_ids(db, candidates)
    cards = apply_card_filters(
        [build_card(db, c, vacancy.stack if vacancy is not None else stack or [], similarities.get(c.id), verified.get(c.user_id)) for c in candidates],
        has_pvn,
        min_score,
        verified_only,
    )
    if not reranked:
        cards.sort(key=lambda card: (card.final_score, card.score), reverse=True)
    return cards[skip : skip + limit]
